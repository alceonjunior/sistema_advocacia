# gestao/calculators.py
from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from dateutil.relativedelta import relativedelta
import calendar

from .services.indices.resolver import ServicoIndices

def _q2(v: Decimal) -> Decimal:
    return Decimal(v).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _norm_mensal(v):
    """
    Normaliza um valor mensal vindo do provider:
    - Se |v| > 1  -> trata como PERCENTUAL (divide por 100)
    - Caso contrário -> trata como FRAÇÃO (mantém)
    Aceita str, float, Decimal.
    """
    if v is None:
        return Decimal('0')
    d = Decimal(str(v))
    return d / Decimal('100') if d.copy_abs() > Decimal('1') else d


class CalculadoraMonetaria:
    """
    Motor de cálculo judicial com pró-rata mensal e SELIC diária composta.
    Espera fases com: ordem, indice, data_inicio, data_fim, juros_tipo, juros_taxa.
    """

    def calcular_fases(self, valor_original, fases):
        saldo_atual = Decimal(str(valor_original))
        servico_indices = ServicoIndices()
        fases_resultados = []

        # Ordena fases por ordem declarada
        for fase in sorted(fases, key=lambda f: f.ordem):
            memoria_fase = []
            valor_inicial_fase = saldo_atual

            indice_nome = (fase.indice or '').strip()
            indice_nome_upper = indice_nome.upper()

            # ===================== CORREÇÃO MONETÁRIA (MENSAL) =====================
            # Se a fase NÃO é SELIC, aplica índice mensal pró-rata
            if 'SELIC' not in indice_nome_upper:
                indices_periodo = servico_indices.get_indices_por_periodo(
                    indice_nome, fase.data_inicio, fase.data_fim
                )
                data_corrente = fase.data_inicio

                while data_corrente <= fase.data_fim:
                    chave = data_corrente.strftime('%Y-%m')
                    bruto = indices_periodo.get(chave, Decimal('0'))
                    fator_mensal = _norm_mensal(bruto)  # fração mensal

                    dias_mes = calendar.monthrange(data_corrente.year, data_corrente.month)[1]

                    # Pró-rata de dias
                    if data_corrente.year == fase.data_inicio.year and data_corrente.month == fase.data_inicio.month:
                        dias_aplic = dias_mes - fase.data_inicio.day + 1
                    else:
                        dias_aplic = dias_mes
                    if data_corrente.year == fase.data_fim.year and data_corrente.month == fase.data_fim.month:
                        if fase.data_inicio.strftime('%Y-%m') == fase.data_fim.strftime('%Y-%m'):
                            dias_aplic = (fase.data_fim - fase.data_inicio).days + 1
                        else:
                            dias_aplic = fase.data_fim.day

                    fator_pro_rata = (fator_mensal / dias_mes) * dias_aplic
                    valor_correcao = saldo_atual * fator_pro_rata

                    memoria_fase.append({
                        'descricao': f"Correção {indice_nome} ({data_corrente.strftime('%m/%Y')}, {dias_aplic} de {dias_mes} dias)",
                        'valor': _q2(valor_correcao)
                    })

                    saldo_atual += valor_correcao
                    data_corrente = (data_corrente.replace(day=1) + relativedelta(months=1))

            # ===================== JUROS / SELIC (DIÁRIA) ==========================
            if 'SELIC' in indice_nome_upper:
                # Usa EXATAMENTE o rótulo selecionado (ex.: 'SELIC (Taxa diária)') ao consultar o provider
                indices_selic = servico_indices.get_indices_por_periodo(
                    indice_nome, fase.data_inicio, fase.data_fim
                )
                fator_acum = Decimal('1.0')
                d = fase.data_inicio
                while d <= fase.data_fim:
                    # Providers diários usam chave ISO 'YYYY-MM-DD'
                    taxa_dia = Decimal(str(indices_selic.get(d.isoformat(), 0)))
                    # Série SGS 11/… vem em PERCENTUAL ao dia -> /100
                    fator_acum *= (Decimal('1.0') + (taxa_dia / Decimal('100')))
                    d += relativedelta(days=1)

                valor_corrigido = valor_inicial_fase * fator_acum
                juros = valor_corrigido - valor_inicial_fase
                saldo_atual = valor_corrigido

                memoria_fase.append({
                    'descricao': f"Aplicação da Taxa SELIC de {fase.data_inicio.strftime('%d/%m/%Y')} a {fase.data_fim.strftime('%d/%m/%Y')}",
                    'valor': _q2(juros)
                })

            # ===================== JUROS CONVENCIONAIS (opcional) ==================
            elif getattr(fase, 'juros_taxa', None):
                jt = Decimal(str(fase.juros_taxa))
                if jt != 0:
                    tipo = (fase.juros_tipo or '').upper()
                    meses = (fase.data_fim.year - fase.data_inicio.year) * 12 + (fase.data_fim.month - fase.data_inicio.month)
                    # aproximação pró-rata mensal: considera frações do primeiro/último mês
                    # (ajuste fino pode ser feito conforme sua regra interna)
                    if tipo in ('COMPOSTO', 'COMPOSTO_MENSAL', 'JUROS_COMPOSTO'):
                        fator = (Decimal('1.0') + (jt / Decimal('100')))**Decimal(meses)
                        valor_corrigido = saldo_atual * fator
                        juros_val = valor_corrigido - saldo_atual
                        saldo_atual = valor_corrigido
                    else:
                        # SIMPLES (padrão)
                        juros_val = saldo_atual * (jt / Decimal('100')) * Decimal(meses)
                        saldo_atual += juros_val

                    memoria_fase.append({
                        'descricao': f"Juros {fase.juros_tipo or 'simples'} no período",
                        'valor': _q2(juros_val)
                    })

            fases_resultados.append({
                'valor_inicial_fase': _q2(valor_inicial_fase),
                'valor_final_fase': _q2(saldo_atual),
                'memoria': memoria_fase
            })

        return {
            'resumo': {
                'valor_final': _q2(saldo_atual)
            },
            'fases_resultados': fases_resultados
        }
