# gestao/services/indices/providers.py

import os
import requests
import pandas as pd
from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from dateutil.relativedelta import relativedelta
import logging

from django.conf import settings
from django.core.cache import cache

# Configura um logger para este módulo para facilitar a depuração
logger = logging.getLogger(__name__)


# ==============================================================================
# SEÇÃO 1: ARQUITETURA DE PROVEDORES DE ÍNDICES
# ==============================================================================

class BaseProvider(ABC):
    """
    Classe base abstrata para todos os provedores de índices.
    Define a interface comum e a lógica de cache.
    """

    def __init__(self, cache_ttl=86400):  # Cache de 24 horas por padrão
        self.cache_ttl = cache_ttl

    @abstractmethod
    def get_indices(self, data_inicio, data_fim, **kwargs):
        """
        Método abstrato que as classes filhas devem implementar.
        Busca, formata e retorna os índices para um período.
        """
        pass

    def _get_from_cache(self, key):
        return cache.get(key)

    def _set_to_cache(self, key, value):
        cache.set(key, value, self.cache_ttl)


class BacenSGSProvider(BaseProvider):
    """Busca séries temporais da API do Banco Central (SGS)."""

    def get_indices(self, data_inicio, data_fim, serie_id, index_type):
        cache_key = f"bcb_sgs_{serie_id}_{index_type}_{data_inicio.year}_{data_fim.year}"
        cached_data = self._get_from_cache(cache_key)
        if cached_data:
            return self._filter_cached_data(cached_data, data_inicio, data_fim, index_type)

        start_date = data_inicio - relativedelta(days=5)
        end_date = data_fim + relativedelta(days=5)

        url = (
            f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie_id}/dados?"
            f"formato=json&dataInicial={start_date.strftime('%d/%m/%Y')}&dataFinal={end_date.strftime('%d/%m/%Y')}"
        )
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            data = response.json()

            indices = {}
            for item in data:
                if item.get('valor') and str(item.get('valor')).strip():
                    data_obj = datetime.strptime(item['data'], '%d/%m/%Y').date()
                    valor = Decimal(str(item['valor']))

                    # CORREÇÃO FINAL: Formata a chave com base no tipo de índice (mensal ou diário)
                    # Isso garante que a CalculoEngine encontre o valor correto.
                    if index_type == 'monthly_variation':
                        chave = data_obj.strftime('%Y-%m')
                    else:  # 'daily_rate'
                        chave = data_obj.isoformat()

                    indices[chave] = valor

            self._set_to_cache(cache_key, indices)
            return self._filter_cached_data(indices, data_inicio, data_fim, index_type)
        except requests.RequestException as e:
            logger.error(f"BacenSGSProvider falhou para série {serie_id}: {e}")
            return {}

    def _filter_cached_data(self, cached_data, data_inicio, data_fim, index_type):
        """Filtra dados do cache para o período exato solicitado."""
        if index_type == 'monthly_variation':
            start_key = data_inicio.strftime('%Y-%m')
            end_key = data_fim.strftime('%Y-%m')
            return {k: v for k, v in cached_data.items() if start_key <= k <= end_key}
        else:  # daily_rate
            start_key = data_inicio.isoformat()
            end_key = data_fim.isoformat()
            return {k: v for k, v in cached_data.items() if start_key <= k <= end_key}


class IBGEProvider(BaseProvider):
    """Busca séries da API do IBGE (SIDRA)."""

    def get_indices(self, data_inicio, data_fim, tabela, variavel, index_type):
        periodo_str = f"{data_inicio.strftime('%Y%m')}-{data_fim.strftime('%Y%m')}"
        cache_key = f"ibge_sidra_{tabela}_{variavel}_{periodo_str}"
        cached_data = self._get_from_cache(cache_key)
        if cached_data:
            return cached_data

        url = f"https://apisidra.ibge.gov.br/values/t/{tabela}/n1/all/v/{variavel}/p/{periodo_str}/c315/7169"
        try:
            response = requests.get(url, timeout=20)
            response.raise_for_status()
            data = response.json()
            if not data or len(data) <= 1:
                return {}

            # A API SIDRA para variação mensal sempre retorna a chave no formato "YYYYMM"
            indices = {
                f"{item['D3C'][:4]}-{item['D3C'][4:]}": Decimal(item['V'])
                for item in data[1:] if item.get('V') and item['V'] != '...'
            }
            self._set_to_cache(cache_key, indices)
            return indices
        except requests.RequestException as e:
            logger.error(f"IBGEProvider falhou para tabela {tabela}: {e}")
            return {}


class StaticTableProvider(BaseProvider):
    """Lê índices de arquivos estáticos (CSV)."""

    def get_indices(self, data_inicio, data_fim, filename, index_type):
        cache_key = f"static_table_{filename}"
        cached_data = self._get_from_cache(cache_key)
        if not cached_data:
            try:
                filepath = os.path.join(settings.BASE_DIR, 'gestao', 'static', 'data', 'indices', filename)
                df = pd.read_csv(filepath, sep=';', decimal=',', parse_dates=['data'], dayfirst=True)
                df.set_index('data', inplace=True)

                # Suporta arquivos com 'fator' (acumulado) ou 'variacao' (%)
                if 'fator' in df.columns:
                    df_to_store = df['fator'].to_dict()
                elif 'variacao' in df.columns:
                    df_to_store = (df['variacao'] / Decimal(100)).to_dict()
                else:
                    return {}
                cached_data = df_to_store
                self._set_to_cache(cache_key, cached_data)
            except Exception as e:
                logger.error(f"StaticTableProvider falhou para arquivo {filename}: {e}")
                return {}

        # Formata a chave como "AAAA-MM" para consistência com outros provedores mensais
        return {
            dt.strftime('%Y-%m'): Decimal(str(val))
            for dt, val in cached_data.items()
            if data_inicio.replace(day=1) <= dt.date() <= data_fim
        }


# ==============================================================================
# SEÇÃO 2: CLASSE DE SERVIÇO DE FACHADA
# ==============================================================================

class ServicoIndices:
    """
    Classe de serviço que atua como uma fachada (Facade) para o novo sistema
    de Provedores. Garante compatibilidade com código legado e resolve importações circulares.
    """

    def get_indices_por_periodo(self, indice_nome, data_inicio, data_fim):
        # A importação é feita aqui dentro para quebrar o ciclo de dependência
        from .catalog import get_indice_info

        try:
            info_indice = get_indice_info(indice_nome)
            provider = info_indice['provider']
            params = info_indice['params']
            index_type = info_indice.get('type', 'daily_rate')

            # Passa todos os parâmetros necessários para o provedor correto
            return provider.get_indices(
                data_inicio=data_inicio,
                data_fim=data_fim,
                index_type=index_type,
                **params
            )
        except (ValueError, NotImplementedError) as e:
            logger.error(f"Erro ao buscar índice '{indice_nome}': {e}")
            return {}