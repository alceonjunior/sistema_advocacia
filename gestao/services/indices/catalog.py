# gestao/services/indices/catalog.py

from __future__ import annotations
from typing import Dict, Any

# Este dicionário é o coração do sistema de cálculos.
# Ele mapeia um nome amigável (chave) para a configuração de como obter os dados.
#
# Estrutura de cada item:
# - "label": O texto que aparecerá para o usuário no seletor de índices.
# - "provider": O nome da classe em 'providers.py' que buscará os dados.
# - "type": Como o motor de cálculo deve tratar os dados ('monthly_variation' ou 'daily_rate').
# - "group": Categoria para agrupar os índices na interface do usuário.
# - "params": Dicionário com parâmetros específicos para o provider.
#   - Para 'BacenSGSProvider': 'serie_id' é o código da série no sistema do Bacen.
#   - Para 'StaticTableProvider': 'filename' é o nome do arquivo CSV/JSON dentro da pasta 'data/'.

INDICE_CATALOG: Dict[str, Dict[str, Any]] = {
    # --- Índices de Preços (Inflação) ---
    "IPCA": {
        "label": "IPCA (IBGE)",
        "provider": "BacenSGSProvider",
        "params": {"serie_id": 433},
        "type": "monthly_variation",
        "group": "Índices de Preços",
    },
    "IPCA-E": {
        "label": "IPCA-E (IBGE)",
        "provider": "BacenSGSProvider",
        "params": {"serie_id": 4449},
        "type": "monthly_variation",
        "group": "Índices de Preços",
    },
    "INPC": {
        "label": "INPC (IBGE)",
        "provider": "BacenSGSProvider",
        "params": {"serie_id": 188},
        "type": "monthly_variation",
        "group": "Índices de Preços",
    },
    "IGP-M": {
        "label": "IGP-M (FGV)",
        "provider": "BacenSGSProvider",
        "params": {"serie_id": 189},
        "type": "monthly_variation",
        "group": "Índices de Preços",
    },
    "IGP-DI": {
        "label": "IGP-DI (FGV)",
        "provider": "BacenSGSProvider",
        "params": {"serie_id": 190},
        "type": "monthly_variation",
        "group": "Índices de Preços",
    },
    "IPC-BRASIL": {
        "label": "IPC-Brasil (FGV)",
        "provider": "BacenSGSProvider",
        "params": {"serie_id": 191},
        "type": "monthly_variation",
        "group": "Índices de Preços (FGV)",
    },

    # --- Taxas de Juros e Remuneração ---
    "SELIC_DIARIA": {
        "label": "SELIC (Taxa diária)",
        "provider": "BacenSGSProvider",
        "params": {"serie_id": 1178},
        "type": "daily_rate",
        "group": "Taxas de Juros",
    },
    "SELIC_MENSAL": {
        "label": "SELIC (Acumulada no mês)",
        "provider": "BacenSGSProvider",
        "params": {"serie_id": 4390},
        "type": "monthly_variation",
        "group": "Taxas de Juros",
    },
    "TR_DIARIA": {
        "label": "TR - Taxa Referencial (Fator diário)",
        "provider": "BacenSGSProvider",
        "params": {"serie_id": 226},
        "type": "daily_rate",  # TR é um fator, mas tratado como taxa diária
        "group": "Taxas de Remuneração",
    },
    "POUPANCA": {
        "label": "Poupança (Rendimento mensal)",
        "provider": "BacenSGSProvider",
        "params": {"serie_id": 195},
        "type": "monthly_variation",
        "group": "Taxas de Remuneração",
    },

    # --- Índices de Tribunais (Exemplos com arquivos locais) ---
    "TJSP": {
        "label": "Tabela Prática do TJSP",
        "provider": "StaticTableProvider",
        "params": {"filename": "tabela_tjsp.csv"},
        "type": "monthly_variation",
        "group": "Tabelas Judiciais",
    },
    "IPC-FIPE": {
        "label": "IPC (FIPE-SP)",
        "provider": "StaticTableProvider",
        "params": {"filename": "ipc_fipe.csv"},
        "type": "monthly_variation",
        "group": "Índices Regionais",
    },
}


def get_indice_info(nome: str) -> Dict[str, Any]:
    """Função de conveniência para obter metadados de um índice."""
    try:
        return INDICE_CATALOG[nome]
    except KeyError as exc:
        raise ValueError(f"Índice desconhecido: {nome}") from exc


def public_catalog_for_api() -> list[dict[str, Any]]:
    """
    Gera uma lista plana de índices para o frontend, garantindo que todos
    os itens tenham as chaves 'key' e 'label' para evitar erros de JavaScript.
    """
    indices = []
    for key, meta in INDICE_CATALOG.items():
        indices.append({
            "key": key,
            "label": meta.get("label", key),  # Garante que 'label' sempre exista
            "group": meta.get("group", "Outros"),
            "type": meta.get("type", "monthly_variation"),
        })
    # Ordena a lista final pelo 'label' para uma exibição consistente
    indices.sort(key=lambda x: x['label'])
    return indices