# gestao/services.py

import requests
from datetime import datetime
from decimal import Decimal
from dateutil.relativedelta import relativedelta

# Mapeamento de índices para os códigos das séries no SGS do Banco Central
INDICES_BCB = {
    # --- CORREÇÃO APLICADA: O código para a SELIC DIÁRIA é 11, não 1178 (que é mensal).
    'SELIC': 11,
    'IGP-M': 189,  # Mensal
    'IGP-DI': 190,  # Mensal
    'TR': 226,  # Diário
}

# Mapeamento de índices para os parâmetros da API do IBGE (SIDRA)
INDICES_IBGE = {
    'IPCA': {'tabela': '1737', 'variavel': '63'},
    'INPC': {'tabela': '1737', 'variavel': '69'},
}


class ServicoIndices:
    """
    Classe de serviço para buscar e gerenciar dados de índices econômicos.
    """

    def __init__(self):
        self._cache = {}

    def _get_from_cache(self, key):
        return self._cache.get(key)

    def _set_to_cache(self, key, value):
        self._cache[key] = value

    def get_indices_por_periodo(self, indice_nome, data_inicio, data_fim):
        cache_key = f"{indice_nome}_{data_inicio.isoformat()}_{data_fim.isoformat()}"
        cached_value = self._get_from_cache(cache_key)
        if cached_value:
            return cached_value

        if indice_nome in INDICES_BCB:
            dados = self._get_dados_bcb(indice_nome, data_inicio, data_fim)
        elif indice_nome in INDICES_IBGE:
            start_of_month = data_inicio.replace(day=1)
            dados = self._get_dados_ibge(indice_nome, start_of_month, data_fim)
        else:
            raise ValueError(f"Índice '{indice_nome}' não suportado")

        self._set_to_cache(cache_key, dados)
        return dados

    def _get_dados_bcb(self, indice_nome, data_inicio, data_fim):
        codigo_serie = INDICES_BCB[indice_nome]
        url = (
            f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo_serie}/dados?"
            f"formato=json&dataInicial={data_inicio.strftime('%d/%m/%Y')}&dataFinal={data_fim.strftime('%d/%m/%Y')}"
        )
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            dados_api = response.json()
            indices_formatados = {}
            if not dados_api: return indices_formatados
            for registro in dados_api:
                data_obj = datetime.strptime(registro['data'], '%d/%m/%Y').date()
                valor = Decimal(str(registro['valor']))
                chave = data_obj.strftime('%Y-%m') if indice_nome in ['IGP-M', 'IGP-DI'] else data_obj.isoformat()
                indices_formatados[chave] = valor
            return indices_formatados
        except requests.RequestException as e:
            raise ConnectionError(f"Erro ao conectar com a API do Banco Central: {e}")
        except (ValueError, KeyError) as e:
            raise ValueError(f"Erro ao processar a resposta da API do Banco Central: {e}")

    def _get_dados_ibge(self, indice_nome, data_inicio, data_fim):
        params = INDICES_IBGE[indice_nome]
        # Formato de período para a API SIDRA v3
        periodo_formatado = f"{data_inicio.strftime('%Y%m')}-{data_fim.strftime('%Y%m')}"

        # --- LÓGICA APRIMORADA: Usando a API SIDRA via POST, que é mais estável
        url = "https://apisidra.ibge.gov.br/geratabela"
        payload = {
            'tabela': params['tabela'],
            'variavel': params['variavel'],
            'formato': 'json',
            'classific': 'c315',
            'categorias': '7169',  # Nível Geral do índice
            'periodo': periodo_formatado,
            'localidades': 'N1[all]'  # Nível Nacional
        }

        try:
            response = requests.post(url, data=payload, timeout=20)
            response.raise_for_status()
            dados_api = response.json()

            if not isinstance(dados_api, list) or len(dados_api) <= 1:
                return {}

            indices_formatados = {}
            # O primeiro item é o cabeçalho, então pulamos
            for registro in dados_api[1:]:
                periodo_str = registro.get('D3N')  # Ex: "202003"
                valor_str = registro.get('V')

                if periodo_str and valor_str and valor_str != '...':
                    chave = f"{periodo_str[:4]}-{periodo_str[4:]}"  # Transforma "202003" em "2020-03"
                    indices_formatados[chave] = Decimal(valor_str)
            return indices_formatados
        except requests.RequestException as e:
            raise ConnectionError(f"Erro ao conectar com a API do IBGE: {e}")
        except (ValueError, KeyError, TypeError, IndexError) as e:
            raise ValueError(f"Erro ao processar a resposta da API do IBGE: {e}")