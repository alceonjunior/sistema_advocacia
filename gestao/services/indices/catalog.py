# gestao/services/indices/catalog.py

from __future__ import annotations
from typing import Dict, Any

from .providers import BacenSGSProvider, StaticTableProvider, IBGEProvider

# Códigos SGS mais comuns
# 433 = IPCA (var. % mensal)
# 188 = INPC (var. % mensal)
# 189 = IGP-M (var. % mensal)
# 1178 = Selic diária (% a.a.)

INDICE_CATALOG: Dict[str, Dict[str, Any]] = {
    "IPCA": {
        "label": "IPCA (IBGE) — variação % mensal",
        "provider": BacenSGSProvider(),
        "params": {"serie_id": 433},
        "type": "monthly_variation",
        "group": "Índices de Preços",
    },
    "INPC": {
        "label": "INPC (IBGE) — variação % mensal",
        "provider": BacenSGSProvider(),
        "params": {"serie_id": 188},
        "type": "monthly_variation",
        "group": "Índices de Preços",
    },
    "IGPM": {
        "label": "IGP-M — variação % mensal",
        "provider": BacenSGSProvider(),
        "params": {"serie_id": 189},
        "type": "monthly_variation",
        "group": "Índices de Preços",
    },
    "SELIC_DIA": {
        "label": "SELIC diária — % a.a. (diária)",
        "provider": BacenSGSProvider(),
        "params": {"serie_id": 1178},
        "type": "daily_rate",
        "group": "Taxas",
    },
    # Exemplo de tabela local:
    # "TABELA_LOCAL": {
    #     "label": "Tabela Local (CSV) — variação % mensal",
    #     "provider": StaticTableProvider(),
    #     "params": {"filename": "tabela_local.csv", "col_key": "period", "col_value": "value"},
    #     "type": "monthly_variation",
    #     "group": "Locais",
    # },
}


def get_indice_info(nome: str) -> Dict[str, Any]:
    try:
        return INDICE_CATALOG[nome]
    except KeyError as exc:
        raise ValueError(f"Índice desconhecido: {nome}") from exc


def public_catalog_for_api() -> Dict[str, Any]:
    """Estrutura amigável para o front popular o `<select>` (grupos/opções)."""
    groups: Dict[str, Any] = {}
    for key, meta in INDICE_CATALOG.items():
        grp = meta.get("group", "Outros")
        groups.setdefault(grp, [])
        groups[grp].append(
            {
                "key": key,
                "label": meta.get("label", key),
                "type": meta.get("type", "daily_rate"),
            }
        )
    return {"groups": groups}
