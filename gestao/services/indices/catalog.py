# gestao/services/indices/catalog.py

from .providers import BacenSGSProvider, StaticTableProvider, IBGEProvider

# Instanciamos os provedores uma única vez para serem reutilizados no catálogo
bcb_provider = BacenSGSProvider()
static_provider = StaticTableProvider()
# O IBGEProvider é mantido para futura referência, mas o BACEN já espelha os principais índices.
ibge_provider = IBGEProvider()

# ==============================================================================
# CATÁLOGO CENTRAL DE ÍNDICES ECONÔMICOS
# ==============================================================================
# Este dicionário mapeia o nome do índice (exibido para o usuário) para o seu
# provedor de dados, os parâmetros necessários e o tipo de dado que ele representa.
#
# - provider: A classe que buscará os dados (BacenSGSProvider, etc.).
# - params: Dicionário com os argumentos para o provider.
#   - 'serie_id': Código da Série Temporal no sistema SGS do Banco Central.
#   - 'filename': Nome do arquivo CSV para o StaticTableProvider.
# - type: Define como a CalculoEngine deve tratar os dados.
#   - 'daily_rate': Uma taxa diária (ex: SELIC, TR).
#   - 'monthly_variation': Uma variação percentual mensal (ex: IPCA, IGP-M).
#   - 'factor_table': Uma tabela de fatores acumulados (comum em tabelas de tribunais).
# ==============================================================================

INDICE_CATALOG = {
    # --- Índices Gerais (Fontes: BACEN/SGS e IBGE/SIDRA) ---
    'SELIC (Taxa diária)': {'provider': bcb_provider, 'params': {'serie_id': 11}, 'type': 'daily_rate'},
    'CDI (Taxa diária)': {'provider': bcb_provider, 'params': {'serie_id': 12}, 'type': 'daily_rate'},
    'TR (Taxa diária)': {'provider': bcb_provider, 'params': {'serie_id': 226}, 'type': 'daily_rate'},
    'IGP-M (FGV)': {'provider': bcb_provider, 'params': {'serie_id': 189}, 'type': 'monthly_variation'},
    'IPCA (IBGE)': {'provider': bcb_provider, 'params': {'serie_id': 433}, 'type': 'monthly_variation'},
    'IPCA-15 (IBGE)': {'provider': bcb_provider, 'params': {'serie_id': 7478}, 'type': 'monthly_variation'},
    'IPCA-E (IBGE)': {'provider': bcb_provider, 'params': {'serie_id': 4449}, 'type': 'monthly_variation'},
    'INPC (IBGE)': {'provider': bcb_provider, 'params': {'serie_id': 188}, 'type': 'monthly_variation'},

    # --- Poupança (Fonte: BACEN/SGS) ---
    'POUPANÇA ATÉ 03/05/2012': {'provider': bcb_provider, 'params': {'serie_id': 25}, 'type': 'daily_rate'},
    'POUPANÇA A PARTIR DE 04/05/2012': {'provider': bcb_provider, 'params': {'serie_id': 196}, 'type': 'daily_rate'},

    # --- Índices de Custo e Setoriais (Fonte: Arquivos Estáticos) ---
    'CUB - SINDUSCON/RS': {'provider': static_provider, 'params': {'filename': 'cub_rs.csv'}, 'type': 'factor_table'},
    'IPC (FIPE)': {'provider': static_provider, 'params': {'filename': 'ipc_fipe.csv'}, 'type': 'factor_table'},

    # --- Justiça Federal (Fonte: Arquivos Estáticos) ---
    'JF - Ações condenatórias em geral': {'provider': static_provider, 'params': {'filename': 'jf_condenatorias.csv'},
                                          'type': 'factor_table'},
    'JF - Desapropriações': {'provider': static_provider, 'params': {'filename': 'jf_desapropriacoes.csv'},
                             'type': 'factor_table'},

    # --- Tabelas de Tribunais de Justiça (Fonte: Arquivos Estáticos) ---
    'TJ/PR (IPCA-E / Precatórios)': {'provider': bcb_provider, 'params': {'serie_id': 4449},
                                     'type': 'monthly_variation'},
    'TJ/PR (média IGP/INPC)': {'provider': static_provider, 'params': {'filename': 'tjpr_media_igp_inpc.csv'},
                               'type': 'factor_table'},
    'TJ/RJ': {'provider': static_provider, 'params': {'filename': 'tjrj_tabela.csv'}, 'type': 'factor_table'},
    'TJ/SC (Tabela Tribunal Just SC)': {'provider': static_provider, 'params': {'filename': 'tjsc_tabela.csv'},
                                        'type': 'factor_table'},
    'TJ/SP (INPC)': {'provider': bcb_provider, 'params': {'serie_id': 188}, 'type': 'monthly_variation'},
    # TJSP usa o INPC puro.
    'TJ/DF (expurgada)': {'provider': static_provider, 'params': {'filename': 'tjdf_expurgada.csv'},
                          'type': 'factor_table'},
    'TJ/DF (não expurgada)': {'provider': static_provider, 'params': {'filename': 'tjdf_nao_expurgada.csv'},
                              'type': 'factor_table'},
    'TJ/MG (expurgada)': {'provider': static_provider, 'params': {'filename': 'tjmg_expurgada.csv'},
                          'type': 'factor_table'},
    'TJ/MG (não expurgada)': {'provider': static_provider, 'params': {'filename': 'tjmg_nao_expurgada.csv'},
                              'type': 'factor_table'},

    # --- UFIR (Fonte: Arquivos Estáticos) ---
    'UFIR MENSAL (EXTINTA) – Fev/1989 à Jan/2001': {'provider': static_provider,
                                                    'params': {'filename': 'ufir_mensal_extinta.csv'},
                                                    'type': 'factor_table'},
    'UFIR MENSAL RJ': {'provider': static_provider, 'params': {'filename': 'ufir_mensal_rj.csv'},
                       'type': 'factor_table'},
}


def get_indice_info(indice_nome: str) -> dict:
    """
    Função central para buscar as informações de um índice (provedor, parâmetros, tipo)
    pelo nome amigável usado na interface.
    """
    if indice_nome not in INDICE_CATALOG:
        raise ValueError(f"Índice '{indice_nome}' não suportado ou não encontrado no catálogo.")

    return INDICE_CATALOG[indice_nome]