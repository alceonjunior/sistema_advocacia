# gestao/calculators.py

from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from dateutil.relativedelta import relativedelta
import calendar


class CalculadoraMonetaria:
    """
    Motor de cálculo judicial aprimorado.
    Gera um relatório detalhado com resumo e memória analítica,
    seguindo o formato de calculadoras judiciais profissionais.
    """

    def __init__(self, valor_original, data_inicio, data_fim, indices_periodo):
        self.valor_original = Decimal(valor_original)
        self.data_inicio = data_inicio
        self.data_fim = data_fim
        self.indices_periodo = indices_periodo
        self.memorial = []

    def _get_dias_no_mes(self, data):
        """Retorna o número de dias no mês da data fornecida."""
        return calendar.monthrange(data.year, data.month)[1]

    def calcular(self, juros_taxa=0, juros_tipo='SIMPLES', juros_periodo='MENSAL',
                 juros_data_inicio=None, juros_data_fim=None, correcao_pro_rata=False,
                 multa_taxa=0, multa_sobre_juros=False, honorarios_taxa=0):

        # ... (A seção de cálculo da CORREÇÃO MONETÁRIA permanece a mesma) ...
        saldo_corrigido = self.valor_original
        fator_correcao_acumulado = Decimal('1.0')
        data_corrente = date(self.data_inicio.year, self.data_inicio.month, 1)

        while data_corrente <= self.data_fim:
            termo_inicial_mes = date(data_corrente.year, data_corrente.month, 1)
            termo_final_mes = termo_inicial_mes + relativedelta(months=1)

            chave_indice = data_corrente.strftime('%Y-%m')
            fator_correcao_mes = self.indices_periodo.get(chave_indice, Decimal('0')) / 100

            if correcao_pro_rata:
                dias_no_mes = self._get_dias_no_mes(data_corrente)
                fator_diario = fator_correcao_mes / dias_no_mes

                if (self.data_inicio.year == data_corrente.year and self.data_inicio.month == data_corrente.month and
                        self.data_fim.year == data_corrente.year and self.data_fim.month == data_corrente.month):
                    dias_a_corrigir = (self.data_fim - self.data_inicio).days
                    fator_correcao_mes = fator_diario * dias_a_corrigir
                    termo_inicial_mes = self.data_inicio
                    termo_final_mes = self.data_fim

                elif self.data_inicio.year == data_corrente.year and self.data_inicio.month == data_corrente.month:
                    dias_a_corrigir = dias_no_mes - self.data_inicio.day + 1
                    fator_correcao_mes = fator_diario * dias_a_corrigir
                    termo_inicial_mes = self.data_inicio

                elif self.data_fim.year == data_corrente.year and self.data_fim.month == data_corrente.month:
                    dias_a_corrigir = self.data_fim.day
                    fator_correcao_mes = fator_diario * dias_a_corrigir
                    termo_final_mes = self.data_fim

            fator_correcao_acumulado *= (1 + fator_correcao_mes)
            saldo_corrigido += saldo_corrigido * fator_correcao_mes

            self.memorial.append({
                'termo_inicial': termo_inicial_mes,
                'termo_final': termo_final_mes,
                'variacao_periodo': fator_correcao_mes * 100,
                'valor_atualizado_mes': saldo_corrigido,
            })

            data_corrente += relativedelta(months=1)

        # --- 2. CÁLCULO DOS JUROS (APÓS A CORREÇÃO TOTAL) ---
        total_juros = Decimal('0')
        # CORREÇÃO APLICADA AQUI: Inicializamos a variável com um valor padrão
        dias_corridos_juros = 0
        juros_inicio = juros_data_inicio or self.data_inicio
        juros_fim = juros_data_fim or self.data_fim

        if juros_taxa and juros_taxa > 0:
            taxa_juros_decimal = Decimal(juros_taxa) / 100

            if juros_periodo == 'ANUAL':
                taxa_juros_decimal_mensal = taxa_juros_decimal / 12
            else:  # MENSAL
                taxa_juros_decimal_mensal = taxa_juros_decimal

            dias_corridos_juros = (juros_fim - juros_inicio).days
            numero_meses = Decimal(dias_corridos_juros) / Decimal('30.0')

            if juros_tipo == 'SIMPLES':
                total_juros = saldo_corrigido * taxa_juros_decimal_mensal * numero_meses
            else:  # COMPOSTO
                fator_composto = (1 + taxa_juros_decimal_mensal) ** numero_meses
                total_juros = saldo_corrigido * (fator_composto - 1)

        # --- 3. CÁLCULOS FINAIS ---
        base_calculo_multa = (saldo_corrigido + total_juros) if multa_sobre_juros else saldo_corrigido
        multa_valor = base_calculo_multa * (Decimal(multa_taxa) / 100 if multa_taxa else Decimal('0'))

        subtotal_com_multa = saldo_corrigido + total_juros + multa_valor
        honorarios_valor = subtotal_com_multa * (Decimal(honorarios_taxa) / 100 if honorarios_taxa else Decimal('0'))

        valor_final_total = subtotal_com_multa + honorarios_valor

        # --- 4. GERAÇÃO DO DICIONÁRIO FINAL DE RESULTADOS ---
        diff_total_dias = (self.data_fim - self.data_inicio).days
        percentual_juros_total = (total_juros / saldo_corrigido * 100) if saldo_corrigido > 0 else Decimal('0')

        return {
            "resumo": {
                "dias_corridos": diff_total_dias,
                "fator_correcao_periodo": fator_correcao_acumulado.quantize(Decimal('0.000000')),
                "percentual_correcao_periodo": ((fator_correcao_acumulado - 1) * 100).quantize(Decimal('0.000000')),
                "valor_corrigido_total": saldo_corrigido.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                "dias_juros": dias_corridos_juros,
                "percentual_juros_total": percentual_juros_total.quantize(Decimal('0.00000')),
                "total_juros": total_juros.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                "multa_valor": multa_valor.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                "sub_total": subtotal_com_multa.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                "honorarios_valor": honorarios_valor.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                "valor_final": valor_final_total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            },
            "memorial": self.memorial,
        }
