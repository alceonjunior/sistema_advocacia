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


def public_catalog_for_api() -> Dict[str, Any]:
    """Gera uma estrutura amigável para o frontend popular o seletor de índices."""
    groups: Dict[str, Any] = {}
    # Ordena o catálogo pelo label para exibição
    sorted_catalog = sorted(INDICE_CATALOG.items(), key=lambda item: item[1]['label'])

    for key, meta in sorted_catalog:
        grp = meta.get("group", "Outros")
        groups.setdefault(grp, [])
        groups[grp].append(
            {"key": key, "label": meta.get("label", key), "type": meta.get("type")}
        )
    return {"groups": groups}