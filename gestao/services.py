# gestao/services.py

import requests
from datetime import datetime
from decimal import Decimal

INDICES_BCB = {
    'SELIC': 1178, # Diário
    'IGP-M': 189,  # Mensal
    'IGP-DI': 190, # Mensal
    'TR': 226,     # Diário
}

# Mapeamento de índices para os códigos das séries no SGS do Banco Central
# Documentação: https://dadosabertos.bcb.gov.br/dataset/254-taxa-de-juros---selic
INDICES_BCB = {
    # Para Selic, usamos a taxa diária (código 1178) para maior precisão.
    # A taxa mensal (código 4390) só é divulgada no mês seguinte.
    'SELIC': 1178,
    'IGP-M': 189,  # Fonte: FGV. Disponibilizado pelo BCB.
    'IGP-DI': 190,  # Fonte: FGV. Disponibilizado pelo BCB.
    'TR': 226,  # Taxa Referencial
}

# Mapeamento de índices para os parâmetros da API do IBGE (SIDRA)
# Documentação: https://apisidra.ibge.gov.br/home/ajuda
INDICES_IBGE = {
    # Tabela 1737: Variação mensal do IPCA e INPC para o índice geral
    'IPCA': {'tabela': '1737', 'variavel': '63', 'classificacao': '1/all'},
    'INPC': {'tabela': '1737', 'variavel': '69', 'classificacao': '1/all'},
}


class ServicoIndices:
    """
    Classe de serviço para buscar e gerenciar dados de índices econômicos.
    Inclui um cache simples em memória para otimizar requisições repetidas na mesma sessão.
    """

    def __init__(self):
        self._cache = {}

    def _get_from_cache(self, key):
        return self._cache.get(key)

    def _set_to_cache(self, key, value):
        self._cache[key] = value

    def get_indices_por_periodo(self, indice_nome, data_inicio, data_fim):
        """
        Busca uma série de valores de um índice para um dado período.
        Retorna um dicionário no formato {chave_periodo: valor_percentual}.
        A chave do período é 'AAAA-MM-DD' para índices diários e 'AAAA-MM' para mensais.
        """
        cache_key = f"{indice_nome}_{data_inicio.isoformat()}_{data_fim.isoformat()}"
        cached_value = self._get_from_cache(cache_key)
        if cached_value:
            return cached_value

        if indice_nome in INDICES_BCB:
            dados = self._get_dados_bcb(indice_nome, data_inicio, data_fim)
        elif indice_nome in INDICES_IBGE:
            dados = self._get_dados_ibge(indice_nome, data_inicio, data_fim)
        else:
            raise ValueError(f"Índice '{indice_nome}' não suportado")

        self._set_to_cache(cache_key, dados)
        return dados

    def _get_dados_bcb(self, indice_nome, data_inicio, data_fim):
        """
        Busca dados da API SGS do Banco Central, agora diferenciando
        índices mensais e diários para padronizar a chave de retorno.
        """
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

                # Para índices mensais como IGP-M e IGP-DI, a chave será 'AAAA-MM'
                if indice_nome in ['IGP-M', 'IGP-DI']:
                    chave = data_obj.strftime('%Y-%m')
                # Para índices diários como SELIC e TR, a chave será 'AAAA-MM-DD'
                else:
                    chave = data_obj.isoformat()

                indices_formatados[chave] = valor

            return indices_formatados
        except requests.RequestException as e:
            raise ConnectionError(f"Erro ao conectar com a API do Banco Central: {e}")
        except (ValueError, KeyError) as e:
            raise ValueError(f"Erro ao processar a resposta da API do Banco Central: {e}")

    def _get_dados_ibge(self, indice_nome, data_inicio, data_fim):
        """
        Busca dados da API SIDRA do IBGE.
        """
        params = INDICES_IBGE[indice_nome]
        periodo_inicial = data_inicio.strftime('%Y%m')
        periodo_final = data_fim.strftime('%Y%m')

        # Monta a URL da API do SIDRA
        url = (
            f"https://apisidra.ibge.gov.br/values/t/{params['tabela']}/n1/all"
            f"/v/{params['variavel']}/p/{periodo_inicial}-{periodo_final}"
            f"/d/{params['classificacao']}"
        )
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            dados_api = response.json()

            # O primeiro item do JSON do IBGE é o cabeçalho, então o ignoramos.
            if len(dados_api) <= 1:
                return {}

            indices_formatados = {}
            for registro in dados_api[1:]:
                # A API do IBGE retorna o período no formato 'YYYYMM'
                periodo_str = registro['P']
                valor = Decimal(str(registro['V']))
                # Usamos a chave no formato 'AAAA-MM' para índices mensais
                chave = f"{periodo_str[:4]}-{periodo_str[4:]}"
                indices_formatados[chave] = valor

            return indices_formatados
        except requests.RequestException as e:
            raise ConnectionError(f"Erro ao conectar com a API do IBGE: {e}")
        except (ValueError, KeyError) as e:
            raise ValueError(f"Erro ao processar a resposta da API do IBGE: {e}")