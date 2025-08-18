# gestao/services/indices/providers.py

import csv
import json
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Mapping

import requests
from dateutil.relativedelta import relativedelta
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .catalog import INDICE_CATALOG

logger = logging.getLogger(__name__)

# --- Funções Utilitárias ---
def _safe_decimal(value: Any) -> Decimal:
    if value is None: raise InvalidOperation("O valor não pode ser nulo.")
    if isinstance(value, Decimal): return value
    s = str(value).strip()
    if not s: raise InvalidOperation("O valor não pode ser uma string vazia.")
    if "," in s and "." in s: s = s.replace(".", "").replace(",", ".")
    else: s = s.replace(",", ".")
    try: return Decimal(s)
    except InvalidOperation as e: raise InvalidOperation(f"Valor inválido para conversão para Decimal: '{value}'") from e

def _month_key(dt: date | datetime | str) -> str:
    if isinstance(dt, (date, datetime)): return f"{dt.year:04d}-{dt.month:02d}"
    s = str(dt).strip()
    try:
        d = datetime.fromisoformat(s).date()
        return f"{d.year:04d}-{d.month:02d}"
    except Exception: pass
    try:
        d = datetime.strptime(s, "%d/%m/%Y").date()
        return f"{d.year:04d}-{d.month:02d}"
    except Exception as e: raise ValueError(f"Formato de data inválido para chave mensal: '{dt}'") from e

def _between_months(table: Mapping[str, Decimal], inicio: date, fim: date) -> Dict[str, Decimal]:
    m0, m1 = _month_key(inicio), _month_key(fim)
    return {k: v for k, v in table.items() if m0 <= k <= m1}

def _project_data_dir() -> Path: return Path(__file__).resolve().parent / "data"

@lru_cache(maxsize=32)
def _load_table_from_file(filename: str) -> Dict[str, Decimal]:
    path = _project_data_dir() / filename
    if not path.exists(): raise FileNotFoundError(f"Arquivo de dados estáticos não encontrado: '{filename}'")
    table: Dict[str, Decimal] = {}
    try:
        if path.suffix.lower() == ".csv":
            with path.open("r", encoding="utf-8-sig") as f:
                delimiter = ';' if ';' in f.readline() else ','
                f.seek(0)
                reader = csv.DictReader(f, delimiter=delimiter)
                for row in reader:
                    data_col = next((k for k in row if k.lower() in ['data', 'competencia', 'mes']), None)
                    valor_col = next((k for k in row if k.lower() in ['valor', 'indice', 'fator', 'numero_indice']), None)
                    if data_col and valor_col and row[data_col] and row[valor_col]:
                        table[_month_key(row[data_col])] = _safe_decimal(row[valor_col])
        elif path.suffix.lower() == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
            for k, v in data.items():
                if k and v is not None: table[_month_key(k)] = _safe_decimal(v)
    except Exception as e: raise IOError(f"Erro ao ler ou processar o arquivo {filename}: {e}") from e
    return dict(sorted(table.items()))

# --- Classes de Provedores ---
class BaseProvider:
    def get_indices(self, inicio: date, fim: date, **kwargs: Any) -> Dict[str, Decimal]:
        raise NotImplementedError

class BacenSGSProvider(BaseProvider):
    BASE_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie_id}/dados"

    def __init__(self):
        self.session = requests.Session()
        retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
        self.session.mount("https://", HTTPAdapter(max_retries=retries))
        self.session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"})

    @lru_cache(maxsize=64)
    def _fetch_from_api(self, serie_id: int, inicio: date, fim: date) -> Dict[str, Decimal]:
        url = self.BASE_URL.format(serie_id=serie_id)
        params = {'formato': 'json', 'dataInicial': inicio.strftime('%d/%m/%Y'), 'dataFinal': fim.strftime('%d/%m/%Y')}
        logger.info(f"Buscando série SGS {serie_id} de {params['dataInicial']} a {params['dataFinal']}")
        try:
            response = self.session.get(url, params=params, timeout=15, verify=True)
            response.raise_for_status()
            data = response.json()
            table = {}
            for item in data:
                if item and 'data' in item and 'valor' in item and item['valor']:
                    data_item = datetime.strptime(item['data'], '%d/%m/%Y').date()
                    table[data_item.isoformat()] = _safe_decimal(item['valor'])
            return table
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de comunicação com a API do Bacen para a série {serie_id}: {e}")
            return {}
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            raise ValueError(f"Resposta inválida da API do Bacen para a série {serie_id}: {e}")

    def get_indices(self, inicio: date, fim: date, **kwargs: Any) -> Dict[str, Decimal]:
        params = kwargs.get('params', {})
        serie_id = params.get('serie_id')
        index_type = kwargs.get('index_type', 'monthly_variation')
        if not serie_id: raise ValueError("BacenSGSProvider requer o 'serie_id'.")

        api_inicio = inicio.replace(day=1) if index_type == 'monthly_variation' else inicio
        api_fim = (fim + relativedelta(months=1, day=1) - timedelta(days=1)) if index_type == 'monthly_variation' else fim
        api_data = self._fetch_from_api(serie_id, api_inicio, api_fim)
        if not api_data:
            logger.warning(f"Nenhum dado retornado pela API do Bacen para a série {serie_id}.")
            return {}

        if index_type == 'daily_rate':
            return {k: v for k, v in api_data.items() if inicio.isoformat() <= k <= fim.isoformat()}
        else:
            monthly_table = {}
            for iso_date, value in api_data.items():
                monthly_table[iso_date[:7]] = value
            return _between_months(monthly_table, inicio, fim)

class StaticTableProvider(BaseProvider):
    def get_indices(self, inicio: date, fim: date, **kwargs: Any) -> Dict[str, Decimal]:
        params = kwargs.get('params', {})
        filename = params.get('filename')
        if not filename: raise ValueError("StaticTableProvider requer o 'filename'.")
        return _between_months(_load_table_from_file(filename), inicio, fim)

# --- Serviço de Alto Nível ---
PROVIDERS_MAP = {"BacenSGSProvider": BacenSGSProvider, "StaticTableProvider": StaticTableProvider}

class ServicoIndices:
    def __init__(self) -> None:
        self._catalog = INDICE_CATALOG
        self._providers = {name: ProviderClass() for name, ProviderClass in PROVIDERS_MAP.items()}

    def get_meta(self, chave: str) -> Dict[str, Any]:
        if not (meta := self._catalog.get(chave)): raise KeyError(f"Índice '{chave}' não encontrado.")
        return meta

    def get_indices_por_periodo(self, chave: str, inicio: date, fim: date) -> Dict[str, Decimal]:
        meta = self.get_meta(chave)
        provider_name = meta.get("provider")
        if not (provider_instance := self._providers.get(provider_name)):
            raise ValueError(f"Provider '{provider_name}' não mapeado.")
        return provider_instance.get_indices(
            inicio=inicio, fim=fim, params=meta.get("params", {}), index_type=meta.get("type")
        )