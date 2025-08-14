# gestao/services/indices/providers.py

# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
import json
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

import requests  # Dependência para chamadas de API
from dateutil.relativedelta import relativedelta

# Configuração do Logger para depuração
logger = logging.getLogger(__name__)


# ===========================================================================
# Funções Utilitárias de Conversão e Manipulação de Dados
# ===========================================================================

def _safe_decimal(value: Any) -> Decimal:
    """
    Converte de forma robusta vários formatos de string, float ou int para Decimal.
    Trata formatos brasileiros ("1.234,56") e americanos ("1,234.56").
    """
    if value is None:
        raise InvalidOperation("O valor não pode ser nulo.")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))  # Converte para string primeiro para evitar imprecisão de float

    s = str(value).strip()
    if not s:
        raise InvalidOperation("O valor não pode ser uma string vazia.")

    # Normaliza separadores: remove milhares e usa ponto para decimal
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", ".")

    try:
        return Decimal(s)
    except InvalidOperation as e:
        raise InvalidOperation(f"Valor inválido para conversão para Decimal: '{value}'") from e


def _month_key(dt: date | datetime | str) -> str:
    """Normaliza qualquer formato de data para a chave 'YYYY-MM'."""
    if isinstance(dt, (date, datetime)):
        return f"{dt.year:04d}-{dt.month:02d}"
    s = str(dt).strip()
    try:
        # Tenta múltiplos formatos de data
        if len(s) == 7 and s[4] == "-": return s  # 'YYYY-MM'
        d = datetime.fromisoformat(s).date()  # 'YYYY-MM-DD'
        return f"{d.year:04d}-{d.month:02d}"
    except Exception:
        pass
    try:
        d = datetime.strptime(s, "%d/%m/%Y").date()  # 'DD/MM/YYYY'
        return f"{d.year:04d}-{d.month:02d}"
    except Exception as e:
        raise ValueError(f"Formato de data inválido para chave mensal: '{dt}'") from e


def _between_months(table: Mapping[str, Decimal], inicio: date, fim: date) -> Dict[str, Decimal]:
    """Filtra um dicionário {'YYYY-MM': Decimal} dentro de um período, incluindo as bordas."""
    m0, m1 = _month_key(inicio), _month_key(fim)
    return {k: v for k, v in table.items() if m0 <= k <= m1}


def _project_data_dir() -> Path:
    """Resolve o caminho para o diretório de dados estáticos (data/)."""
    return Path(__file__).resolve().parent / "data"


@lru_cache(maxsize=32)
def _load_table_from_file(filename: str) -> Dict[str, Decimal]:
    """
    Carrega uma tabela de um arquivo (CSV ou JSON) do diretório 'data'.
    O resultado é cacheado para evitar leituras repetidas do disco.
    """
    path = _project_data_dir() / filename
    if not path.exists():
        raise FileNotFoundError(
            f"Arquivo de dados estáticos não encontrado. Verifique se '{filename}' existe em '{_project_data_dir()}'.")

    table: Dict[str, Decimal] = {}
    try:
        if path.suffix.lower() == ".csv":
            with path.open("r", encoding="utf-8-sig") as f:
                # Detecta o delimitador (ponto e vírgula ou vírgula)
                delimiter = ';' if ';' in f.readline() else ','
                f.seek(0)
                reader = csv.DictReader(f, delimiter=delimiter)
                for row in reader:
                    data_col = next((k for k in row if k.lower() in ['data', 'competencia', 'mes']), None)
                    valor_col = next((k for k in row if k.lower() in ['valor', 'indice', 'fator', 'numero_indice']),
                                     None)
                    if data_col and valor_col and row[data_col] and row[valor_col]:
                        table[_month_key(row[data_col])] = _safe_decimal(row[valor_col])
        elif path.suffix.lower() == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
            for k, v in data.items():
                if k and v is not None:
                    table[_month_key(k)] = _safe_decimal(v)
    except Exception as e:
        raise IOError(f"Erro ao ler ou processar o arquivo {filename}: {e}") from e

    return dict(sorted(table.items()))


# ===========================================================================
# Classes de Provedores de Índices
# ===========================================================================

class BaseProvider:
    """Classe base para todos os provedores de índices."""

    def get_indices(self, inicio: date, fim: date, **kwargs: Any) -> Dict[str, Decimal]:
        raise NotImplementedError


class BacenSGSProvider(BaseProvider):
    """Provider que busca séries temporais da API do Banco Central (SGS)."""
    BASE_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie_id}/dados"

    @lru_cache(maxsize=64)  # Cache para otimizar chamadas repetidas
    def _fetch_from_api(self, serie_id: int, inicio: date, fim: date) -> Dict[str, Decimal]:
        """Faz a chamada HTTP para a API do Bacen e retorna um dicionário de dados."""
        url = self.BASE_URL.format(serie_id=serie_id)
        params = {'formato': 'json', 'dataInicial': inicio.strftime('%d/%m/%Y'), 'dataFinal': fim.strftime('%d/%m/%Y')}
        logger.info(f"Buscando série SGS {serie_id} do Bacen de {params['dataInicial']} a {params['dataFinal']}")
        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            table = {}
            for item in data:
                data_item = datetime.strptime(item['data'], '%d/%m/%Y').date()
                chave = data_item.isoformat()  # Chave 'YYYY-MM-DD'
                table[chave] = _safe_decimal(item['valor'])
            return table
        except requests.Timeout:
            raise ConnectionError(f"Tempo esgotado ao buscar a série {serie_id} do Bacen.")
        except requests.RequestException as e:
            raise ConnectionError(f"Falha de comunicação com a API do Bacen para a série {serie_id}: {e}")
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            raise ValueError(f"Resposta inválida da API do Bacen para a série {serie_id}: {e}")

    def get_indices(self, inicio: date, fim: date, **kwargs: Any) -> Dict[str, Decimal]:
        params = kwargs.get('params', {})
        serie_id = params.get('serie_id')
        index_type = kwargs.get('index_type', 'monthly_variation')

        if not serie_id:
            raise ValueError("BacenSGSProvider requer o 'serie_id' (código SGS).")

        # Ajusta período da busca para garantir que as bordas sejam incluídas em índices mensais
        api_inicio = inicio.replace(day=1) if index_type == 'monthly_variation' else inicio
        api_fim = (fim + relativedelta(months=1, day=1) - timedelta(
            days=1)) if index_type == 'monthly_variation' else fim

        api_data = self._fetch_from_api(serie_id, api_inicio, api_fim)

        if index_type == 'daily_rate':
            return {k: v for k, v in api_data.items() if inicio.isoformat() <= k <= fim.isoformat()}
        else:  # monthly_variation
            monthly_table = {}
            for iso_date, value in api_data.items():
                chave_mes = iso_date[:7]  # Extrai 'YYYY-MM'
                monthly_table[chave_mes] = value
            return _between_months(monthly_table, inicio, fim)


class StaticTableProvider(BaseProvider):
    """Provider para índices baseados em arquivos locais (CSV ou JSON)."""

    def get_indices(self, inicio: date, fim: date, **kwargs: Any) -> Dict[str, Decimal]:
        params = kwargs.get('params', {})
        filename = params.get('filename')
        if not filename:
            raise ValueError("StaticTableProvider requer o parâmetro 'filename'.")

        full_table = _load_table_from_file(filename)
        return _between_months(full_table, inicio, fim)


# ===========================================================================
# Serviço de Alto Nível (Ponto de Entrada Único)
# ===========================================================================
try:
    from .catalog import INDICE_CATALOG
except ImportError:
    INDICE_CATALOG = {}

PROVIDERS_MAP = {
    "BacenSGSProvider": BacenSGSProvider,
    "StaticTableProvider": StaticTableProvider,
}


class ServicoIndices:
    """Ponto de entrada único para o sistema. Resolve qual provider usar e obtém os dados."""

    def __init__(self) -> None:
        self._catalog = INDICE_CATALOG

    def get_meta(self, chave: str) -> Dict[str, Any]:
        """Retorna os metadados de um índice do catálogo."""
        meta = self._catalog.get(chave)
        if not meta:
            raise KeyError(f"Índice '{chave}' não encontrado no catálogo.")
        return meta

    def get_indices_por_periodo(self, chave: str, inicio: date, fim: date) -> Dict[str, Decimal]:
        """Método principal. Obtém os valores de um índice para um determinado período."""
        meta = self.get_meta(chave)
        provider_name = meta.get("provider")
        ProviderClass = PROVIDERS_MAP.get(provider_name)

        if not ProviderClass:
            raise ValueError(f"Provider '{provider_name}' não está mapeado.")

        provider_instance = ProviderClass()
        return provider_instance.get_indices(
            inicio=inicio,
            fim=fim,
            params=meta.get("params", {}),
            index_type=meta.get("type", "monthly_variation")
        )