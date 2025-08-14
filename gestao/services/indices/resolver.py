# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, List, Mapping, Optional, Tuple

from .providers import ServicoIndices

# =============================================================================
# Utilidades
# =============================================================================


def _to_decimal_pt(value: Any) -> Decimal:
    """
    Converte strings como '1.234,56', '1234,56', '1234.56' ou Decimal/float
    para Decimal. Lança InvalidOperation em valores vazios/None.
    """
    if isinstance(value, Decimal):
        return value
    if value is None:
        raise InvalidOperation("valor None")

    s = str(value).strip()
    if s == "":
        raise InvalidOperation("valor vazio")

    # normaliza separadores
    if "," in s and "." in s:
        # ponto como milhar, vírgula decimal
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", ".")

    return Decimal(s)


def _fmt_money(d: Decimal) -> str:
    """
    Formata Decimal no padrão pt-BR: 1.234,56
    """
    q = d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    s = f"{q:.2f}"
    # troca ponto por vírgula
    s = s.replace(".", ",")
    # insere milhar
    int_part, dec_part = s.split(",")
    int_part = "".join(reversed(int_part))
    chunks = [int_part[i : i + 3] for i in range(0, len(int_part), 3)]
    int_part = ".".join(reversed(chunks))
    return f"{int_part},{dec_part}"


def _parse_date_any(s: str | date | datetime) -> date:
    """
    Aceita date/datetime/strings em:
      - ISO 'YYYY-MM-DD' ou 'YYYY-MM'
      - pt-BR 'DD/MM/AAAA' ou 'MM/AAAA'
    Retorna sempre um date no primeiro dia do mês quando não houver dia.
    """
    if isinstance(s, date):
        return s
    if isinstance(s, datetime):
        return s.date()

    st = str(s).strip()
    # ISO com dia
    try:
        return datetime.fromisoformat(st).date()
    except Exception:
        pass

    # ISO 'YYYY-MM'
    if len(st) == 7 and st[4] == "-":
        return datetime.strptime(st + "-01", "%Y-%m-%d").date()

    # 'DD/MM/AAAA'
    try:
        return datetime.strptime(st, "%d/%m/%Y").date()
    except Exception:
        pass

    # 'MM/AAAA'
    try:
        return datetime.strptime("01/" + st, "%d/%m/%Y").date()
    except Exception as e:
        raise ValueError(f"data inválida: {s!r}") from e


def _month_key(d: date | str | datetime) -> str:
    """
    Normaliza para 'YYYY-MM'
    """
    if isinstance(d, (date, datetime)):
        return f"{d.year:04d}-{d.month:02d}"
    # reaproveita o parser
    dd = _parse_date_any(d)
    return f"{dd.year:04d}-{dd.month:02d}"


def _months_between(inicio: date, fim: date) -> List[str]:
    """
    Lista de chaves 'YYYY-MM' do período (inclusive).
    """
    y, m = inicio.year, inicio.month
    yf, mf = fim.year, fim.month
    out: List[str] = []
    while (y < yf) or (y == yf and m <= mf):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m = 1
            y += 1
    return out


# =============================================================================
# Núcleo do cálculo
# =============================================================================


@dataclass
class FaixaResultado:
    indice: str
    inicio: str
    fim: str
    fator: Decimal
    valor_corrigido: Decimal
    meses_usados: List[Tuple[str, Decimal]]  # [(YYYY-MM, var%), ...]
    aviso_meses_ausentes: List[str]


@dataclass
class ParcelaResultado:
    descricao: str
    valor_original: Decimal
    data_valor: str
    faixas: List[FaixaResultado]
    valor_apos_correcao: Decimal
    juros_aplicados: Decimal
    valor_final: Decimal


class IndiceResolver:
    """
    Resolve fatores de correção a partir do catálogo de índices, aplicando
    o produto das variações mensais:  Π (1 + var/100).

    Se 'juros_perc' vier na faixa, aplica juros simples ao fim do período:
      juros = valor_corrigido * (juros_perc/100) * n_meses
    """

    def __init__(self, service: Optional[ServicoIndices] = None) -> None:
        self.service = service or ServicoIndices()

    # ------------------------------------------------------------------

    def _corrigir_faixa(
        self,
        valor_base: Decimal,
        indice_key: str,
        dt_inicio: date,
        dt_fim: date,
    ) -> FaixaResultado:
        meta = self.service.get_meta(indice_key)
        tabela = self.service.get_indices_por_periodo(indice_key, dt_inicio, dt_fim)

        # Constrói a lista de meses e aplica produto
        meses = _months_between(dt_inicio, dt_fim)
        fator = Decimal("1.0")
        meses_usados: List[Tuple[str, Decimal]] = []
        ausentes: List[str] = []

        for k in meses:
            if k in tabela:
                var = tabela[k]  # já é Decimal
                meses_usados.append((k, var))
                fator *= (Decimal("1.0") + (var / Decimal("100")))
            else:
                ausentes.append(k)

        valor_corrigido = (valor_base * fator).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        return FaixaResultado(
            indice=indice_key,
            inicio=_month_key(dt_inicio),
            fim=_month_key(dt_fim),
            fator=fator,
            valor_corrigido=valor_corrigido,
            meses_usados=meses_usados,
            aviso_meses_ausentes=ausentes,
        )

    # ------------------------------------------------------------------

    def _aplicar_juros_simples(
        self,
        valor_base: Decimal,
        perc_ao_mes: Decimal,
        dt_inicio: date,
        dt_fim: date,
    ) -> Decimal:
        """
        Juros simples: valor * (i * n_meses)
        """
        n_meses = Decimal(str(len(_months_between(dt_inicio, dt_fim))))
        juros = (valor_base * (perc_ao_mes / Decimal("100")) * n_meses).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        return juros

    # ------------------------------------------------------------------

    def corrigir_parcelas(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        """
        Espera o mesmo *shape* que vem do wizard no frontend:

        {
          "basicos": {...},
          "parcelas": [
            {
              "descricao": "Parcela 1",
              "valor": "1.000,00" | "1000.00",
              "data_valor": "13/03/2020" | "2020-03-13",
              "faixas": [
                {"inicio":"13/03/2020","fim":"31/12/2020","indice":"IPCA","juros":"nao","juros_perc":"1,0"}
              ]
            },
            ...
          ],
          "extras": {"multa_perc":"0","honorarios_perc":"0"}
        }
        """
        erros: List[str] = []
        resultado_parcelas: List[ParcelaResultado] = []
        total = Decimal("0.00")

        parcelas = list(payload.get("parcelas") or [])
        if not parcelas:
            return {"ok": False, "erro": "Nenhuma parcela informada."}

        for i, p in enumerate(parcelas, start=1):
            try:
                desc = (p.get("descricao") or f"Parcela {i}").strip()
                valor_original = _to_decimal_pt(p.get("valor"))
                dt_valor = _parse_date_any(p.get("data_valor"))

                valor_corrente = valor_original
                faixas_res: List[FaixaResultado] = []
                juros_total = Decimal("0.00")

                faixas = list(p.get("faixas") or [])
                if not faixas:
                    raise ValueError("Nenhuma faixa definida para a parcela.")

                for j, fx in enumerate(faixas, start=1):
                    indice_key = (fx.get("indice") or "").strip()
                    if not indice_key:
                        raise ValueError(f"Faixa {j}: índice não informado.")
                    dt_inicio = _parse_date_any(fx.get("inicio") or dt_valor)
                    dt_fim = _parse_date_any(fx.get("fim") or dt_valor)

                    # aplica correção da faixa sobre o valor atual
                    fx_res = self._corrigir_faixa(valor_corrente, indice_key, dt_inicio, dt_fim)
                    faixas_res.append(fx_res)
                    valor_corrente = fx_res.valor_corrigido

                    # juros simples opcional
                    juros_flag = str(fx.get("juros") or "").strip().lower() in {"sim", "true", "1", "yes"}
                    juros_perc_raw = fx.get("juros_perc")
                    if juros_flag and juros_perc_raw not in (None, ""):
                        try:
                            juros_perc = _to_decimal_pt(juros_perc_raw)
                            juros_val = self._aplicar_juros_simples(valor_corrente, juros_perc, dt_inicio, dt_fim)
                            juros_total += juros_val
                            valor_corrente = (valor_corrente + juros_val).quantize(
                                Decimal("0.01"), rounding=ROUND_HALF_UP
                            )
                        except Exception:
                            # ignora juros com formato inválido, mas segue o cálculo
                            pass

                resultado = ParcelaResultado(
                    descricao=desc,
                    valor_original=valor_original,
                    data_valor=dt_valor.strftime("%Y-%m-%d"),
                    faixas=faixas_res,
                    valor_apos_correcao=valor_corrente - juros_total,
                    juros_aplicados=juros_total,
                    valor_final=valor_corrente,
                )
                resultado_parcelas.append(resultado)
                total += resultado.valor_final

            except Exception as e:
                erros.append(f"Parcela {i}: {e}")

        # Extras (multa/honorários)
        extras = payload.get("extras") or {}
        multa_perc = extras.get("multa_perc")
        honor_perc = extras.get("honorarios_perc")
        multa_val = Decimal("0.00")
        honor_val = Decimal("0.00")

        try:
            if multa_perc not in (None, ""):
                multa_val = (total * (_to_decimal_pt(multa_perc) / Decimal("100"))).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
        except Exception:
            pass

        try:
            if honor_perc not in (None, ""):
                honor_val = (total * (_to_decimal_pt(honor_perc) / Decimal("100"))).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
        except Exception:
            pass

        total_final = (total + multa_val + honor_val).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # Serialização amigável ao front
        def _faixa_to_dict(fr: FaixaResultado) -> Dict[str, Any]:
            return {
                "indice": fr.indice,
                "inicio": fr.inicio,
                "fim": fr.fim,
                "fator": str(fr.fator),
                "valor_corrigido": _fmt_money(fr.valor_corrigido),
                "meses_usados": [{"competencia": k, "variacao_perc": str(v)} for (k, v) in fr.meses_usados],
                "meses_ausentes": fr.aviso_meses_ausentes,
            }

        def _parcela_to_dict(pr: ParcelaResultado) -> Dict[str, Any]:
            return {
                "descricao": pr.descricao,
                "valor_original": _fmt_money(pr.valor_original),
                "data_valor": pr.data_valor,
                "faixas": [_faixa_to_dict(fx) for fx in pr.faixas],
                "valor_apos_correcao": _fmt_money(pr.valor_apos_correcao),
                "juros_aplicados": _fmt_money(pr.juros_aplicados),
                "valor_final": _fmt_money(pr.valor_final),
            }

        payload_out = {
            "ok": len(erros) == 0,
            "erros": erros,
            "parcelas": [_parcela_to_dict(p) for p in resultado_parcelas],
            "totais": {
                "subtotal_corrigido": _fmt_money(total),
                "multa_valor": _fmt_money(multa_val),
                "honorarios_valor": _fmt_money(honor_val),
                "total_final": _fmt_money(total_final),
            },
        }
        return payload_out


# =============================================================================
# Função de alto nível (atalho)
# =============================================================================


def calcular(payload: Mapping[str, Any]) -> Dict[str, Any]:
    """
    Atalho simples para uso na view:
        return JsonResponse(calcular(request_json))
    """
    srv = ServicoIndices()
    resolver = IndiceResolver(srv)
    return resolver.corrigir_parcelas(payload)
