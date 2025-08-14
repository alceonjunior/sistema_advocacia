# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

import csv
import json

# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------


def _safe_decimal(value: Any) -> Decimal:
    """
    Converte valores (str/float/Decimal) para Decimal.
    Aceita formatos '1.23', '1,23', '1.234,56', etc.
    """
    if value is None:
        raise InvalidOperation("valor None")
    if isinstance(value, Decimal):
        return value

    s = str(value).strip()
    if s == "" or s == "." or s.lower() == "nan":
        raise InvalidOperation(f"valor vazio: {value!r}")

    # normaliza separadores: remove milhares e usa ponto para decimal
    if "," in s and "." in s:
        # assume ponto como milhar e vírgula como decimal (pt-BR)
        s = s.replace(".", "").replace(",", ".")
    else:
        # se só tem vírgula, troca por ponto
        s = s.replace(",", ".")

    return Decimal(s)


def _month_key(dt: date | datetime | str) -> str:
    """
    Normaliza para 'YYYY-MM'.
    Aceita date/datetime/strings ('YYYY-MM', 'YYYY-MM-DD', 'DD/MM/YYYY').
    """
    if isinstance(dt, (date, datetime)):
        return f"{dt.year:04d}-{dt.month:02d}"

    s = str(dt).strip()
    if len(s) == 7 and s[4] == "-":  # 'YYYY-MM'
        return s
    # tenta ISO
    try:
        d = datetime.fromisoformat(s).date()
        return f"{d.year:04d}-{d.month:02d}"
    except Exception:
        pass
    # tenta dd/mm/aaaa
    try:
        d = datetime.strptime(s, "%d/%m/%Y").date()
        return f"{d.year:04d}-{d.month:02d}"
    except Exception:
        pass
    # tenta mm/yyyy
    try:
        d = datetime.strptime("01/" + s, "%d/%m/%Y").date()
        return f"{d.year:04d}-{d.month:02d}"
    except Exception as e:
        raise ValueError(f"Data inválida p/ chave mensal: {dt!r}") from e


def _between_months(
    table: Mapping[str, Decimal], inicio: date, fim: date
) -> Dict[str, Decimal]:
    """
    Filtra um dicionário mensal {'YYYY-MM': Decimal} dentro do período.
    Inclui bordas (mês de início e mês de fim).
    """
    m0 = _month_key(inicio)
    m1 = _month_key(fim)
    out: Dict[str, Decimal] = {}
    for k, v in table.items():
        if not isinstance(v, Decimal):
            try:
                v = _safe_decimal(v)
            except Exception:
                continue
        if m0 <= k <= m1:
            out[k] = v
    # ordenado por chave
    return dict(sorted(out.items()))


def _project_data_dir() -> Path:
    """
    Resolve a pasta de dados: <root>/gestao/services/indices/data.
    Não acessa settings no import. Funciona mesmo fora do Django.
    """
    # caminho relativo ao próprio arquivo
    here = Path(__file__).resolve()
    data_dir = here.parent / "data"
    if data_dir.exists():
        return data_dir

    # fallback: tenta partir do root presumido
    root = here.parents[3] if len(here.parents) >= 3 else here.parent
    guess = root / "gestao" / "services" / "indices" / "data"
    return guess


def _candidate_paths(
    base: str | int, extras: Iterable[str] = ()
) -> List[Path]:
    """
    Gera nomes candidatos para um arquivo de dados de série/índice.
    Ex.: 433 -> ['sgs_433.csv', '433.csv', 'sgs-433.csv', ...]
    """
    b = str(base)
    cand = [
        f"sgs_{b}.csv",
        f"{b}.csv",
        f"sgs-{b}.csv",
        f"sgs_{b}.json",
        f"{b}.json",
        f"sgs-{b}.json",
    ]
    cand.extend(list(extras or []))
    return [(_project_data_dir() / x) for x in cand]


def _load_monthly_table_from_csv(path: Path) -> Dict[str, Decimal]:
    """
    Lê CSV com duas colunas usuais: data, valor.
    Aceita cabeçalho variado: 'data;valor' ou 'date,value', etc.
    Datas podem estar em 'YYYY-MM-DD', 'YYYY-MM' ou 'DD/MM/YYYY'.
    """
    table: Dict[str, Decimal] = {}
    with path.open("r", encoding="utf-8") as f:
        sniffer = csv.Sniffer()
        sample = f.read(2048)
        f.seek(0)
        dialect = sniffer.sniff(sample, delimiters=";,")
        reader = csv.reader(f, dialect)
        rows = list(reader)

    # obtém índice das colunas
    header = [h.strip().lower() for h in rows[0]]
    if len(header) < 2:
        raise ValueError(f"CSV malformado: {path}")
    # tenta encontrar colunas
    try:
        idx_data = next(
            i for i, h in enumerate(header) if h in {"data", "date", "mes", "competencia"}
        )
    except StopIteration:
        idx_data = 0
    try:
        idx_val = next(
            i for i, h in enumerate(header) if h in {"valor", "value", "taxa", "indice", "ipca", "var"}
        )
    except StopIteration:
        idx_val = 1

    for row in rows[1:]:
        if not row or len(row) < 2:
            continue
        try:
            k = _month_key(row[idx_data])
            v = _safe_decimal(row[idx_val])
        except Exception:
            continue
        table[k] = v

    return dict(sorted(table.items()))


def _load_monthly_table_from_json(path: Path) -> Dict[str, Decimal]:
    """
    Lê JSON com mapeamento {'YYYY-MM': valor} ou lista de objetos.
    Se for lista, tenta chaves 'data'/'valor'.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    table: Dict[str, Decimal] = {}

    if isinstance(data, Mapping):
        for k, v in data.items():
            try:
                table[_month_key(k)] = _safe_decimal(v)
            except Exception:
                continue
    elif isinstance(data, list):
        for item in data:
            if not isinstance(item, Mapping):
                continue
            d = item.get("data") or item.get("date") or item.get("mes") or item.get("competencia")
            v = item.get("valor") or item.get("value") or item.get("taxa") or item.get("indice")
            if d is None or v is None:
                continue
            try:
                table[_month_key(d)] = _safe_decimal(v)
            except Exception:
                continue
    else:
        raise ValueError(f"Formato JSON não suportado em {path}")

    return dict(sorted(table.items()))


@lru_cache(maxsize=64)
def _load_table_any(*candidates: str) -> Dict[str, Decimal]:
    """
    Tenta carregar a primeira tabela encontrada dentre os candidatos.
    """
    # normaliza para Path
    for c in candidates:
        p = _project_data_dir() / c
        if not p.exists():
            continue
        if p.suffix.lower() == ".csv":
            return _load_monthly_table_from_csv(p)
        if p.suffix.lower() == ".json":
            return _load_monthly_table_from_json(p)
    raise FileNotFoundError(
        f"Arquivo de dados não encontrado. Procurado: {', '.join(str(_project_data_dir() / c) for c in candidates)}"
    )


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------


class BaseProvider:
    """
    Contrato básico de providers.
    A assinatura aceita kwargs opcionais para manter compatibilidade
    com chamadas antigas que passavam meta/params no método.
    """

    def __init__(self, **params: Any) -> None:
        # params típicos: serie_id / code / file / alias / etc.
        self._params = params or {}

    def get_indices(
        self,
        inicio: date,
        fim: date,
        *,
        meta: Optional[dict] = None,
        params: Optional[dict] = None,
        **kwargs: Any,
    ) -> Dict[str, Decimal]:
        raise NotImplementedError


class BacenSGSProvider(BaseProvider):
    """
    Provider de séries do SGS/Bacen.
    Não acessa a internet; utiliza arquivos locais na pasta 'data'.

    Aceita 'serie_id' OU 'code' tanto no __init__ quanto via meta/params.
    O arquivo esperado pode ter nomes como:
        - sgs_<serie_id>.csv / .json
        - <serie_id>.csv / .json
        - sgs-<serie_id>.csv / .json
    """

    def __init__(self, **params: Any) -> None:
        super().__init__(**params)
        self._serie_id = self._params.get("serie_id") or self._params.get("code")

    def _resolve_serie_id(self, meta: Optional[dict], params: Optional[dict]) -> int:
        if self._serie_id:
            return int(self._serie_id)

        if params:
            sid = params.get("serie_id") or params.get("code")
            if sid:
                return int(sid)

        if meta and isinstance(meta, dict):
            mp = meta.get("params") or {}
            sid = mp.get("serie_id") or mp.get("code")
            if sid:
                return int(sid)

        raise ValueError("BacenSGSProvider requer 'serie_id' ou 'code' (código SGS).")

    @lru_cache(maxsize=32)
    def _load_full_table(self, serie_id: int) -> Dict[str, Decimal]:
        cands = [
            f"sgs_{serie_id}.csv",
            f"{serie_id}.csv",
            f"sgs-{serie_id}.csv",
            f"sgs_{serie_id}.json",
            f"{serie_id}.json",
            f"sgs-{serie_id}.json",
        ]
        # permite arquivo explícito via __init__/params
        file_hint = self._params.get("file")
        if file_hint:
            cands.insert(0, str(file_hint))
        return _load_table_any(*cands)

    def get_indices(
        self,
        inicio: date,
        fim: date,
        *,
        meta: Optional[dict] = None,
        params: Optional[dict] = None,
        **kwargs: Any,
    ) -> Dict[str, Decimal]:
        serie_id = self._resolve_serie_id(meta, params)
        table = self._load_full_table(serie_id)
        return _between_months(table, inicio, fim)


class StaticTableProvider(BaseProvider):
    """
    Provider para tabelas estáticas locais (ex.: IGPM/INPC em CSV/JSON).
    A origem do arquivo pode ser indicada por:
      - __init__(file="inpc.csv")
      - params={'file': 'inpc.csv'}
      - meta={'params': {'file': 'inpc.csv'}}
    Caso não informe 'file', tenta nomes derivados de 'alias'/'name'.
    """

    @lru_cache(maxsize=32)
    def _load_full_table(
        self, *, meta: Optional[dict], params: Optional[dict]
    ) -> Dict[str, Decimal]:
        file_hint = (
            (self._params or {}).get("file")
            or (params or {}).get("file")
            or (meta or {}).get("params", {}).get("file")
        )

        if file_hint:
            return _load_table_any(str(file_hint))

        # tenta por alias/nome (ex.: 'INPC' -> inpc.csv/json)
        alias = (
            (self._params or {}).get("alias")
            or (params or {}).get("alias")
            or (meta or {}).get("name")
            or (meta or {}).get("alias")
        )
        cands: List[str] = []
        if alias:
            a = str(alias).lower()
            cands = [f"{a}.csv", f"{a}.json"]

        if not cands:
            raise FileNotFoundError(
                "StaticTableProvider precisa de 'file' (csv/json) "
                "ou alias/nome em meta/params."
            )

        return _load_table_any(*cands)

    def get_indices(
        self,
        inicio: date,
        fim: date,
        *,
        meta: Optional[dict] = None,
        params: Optional[dict] = None,
        **kwargs: Any,
    ) -> Dict[str, Decimal]:
        table = self._load_full_table(meta=meta, params=params)
        return _between_months(table, inicio, fim)


# ---------------------------------------------------------------------------
# Serviço de alto nível usado pela aplicação/API
# ---------------------------------------------------------------------------

try:
    # O catálogo deve estar no mesmo pacote
    from .catalog import INDICE_CATALOG  # type: ignore
except Exception:  # pragma: no cover
    INDICE_CATALOG = {}  # evita erro no import antecipado (por testes unitários)


PROVIDERS_MAP = {
    "BacenSGSProvider": BacenSGSProvider,
    "StaticTableProvider": StaticTableProvider,
    # Adicione aqui outros providers quando necessário
}


@dataclass(frozen=True)
class _IndiceMeta:
    key: str
    name: str
    type: str
    provider: str
    params: Dict[str, Any]


class ServicoIndices:
    """
    Fachada/serviço para resolver índices a partir do catálogo.
    Usada pela API '/api/indices/catalogo/' e pela view do cálculo.
    """

    def __init__(self) -> None:
        self._catalog: Dict[str, dict] = INDICE_CATALOG or {}

    # ------------------------- API Pública -------------------------

    def get_meta(self, chave: str) -> Dict[str, Any]:
        """
        Retorna os metadados normalizados do índice.
        """
        meta = self._catalog.get(chave)
        if not meta:
            raise KeyError(f"Índice não encontrado no catálogo: {chave!r}")
        # normaliza campos esperados
        return {
            "name": meta.get("name", chave),
            "type": meta.get("type", ""),
            "provider": meta.get("provider", ""),
            "params": meta.get("params", {}) or {},
        }

    def listar_catalogo(self) -> List[Dict[str, Any]]:
        """
        Lista em formato amigável para o front (id/nome/provider/tipo).
        """
        out: List[Dict[str, Any]] = []
        for k, v in self._catalog.items():
            out.append(
                {
                    "id": k,
                    "nome": v.get("name", k),
                    "provider": v.get("provider", ""),
                    "tipo": v.get("type", ""),
                }
            )
        # ordena alfabeticamente por nome
        out.sort(key=lambda x: x["nome"])
        return out

    def get_indices_por_periodo(
        self, chave: str, inicio: date, fim: date
    ) -> Dict[str, Decimal]:
        """
        Resolve o provider a partir do catálogo e obtém a tabela mensal
        no período solicitado.
        """
        meta = self.get_meta(chave)
        provider_name = meta["provider"]
        provider_cls = PROVIDERS_MAP.get(provider_name)
        if not provider_cls:
            raise ValueError(f"Provider não mapeado: {provider_name}")

        # passa os params preferencialmente no __init__
        provider = provider_cls(**(meta.get("params") or {}))
        # e chama usando keywords (evita erro de aridade)
        return provider.get_indices(inicio, fim, meta=meta)

