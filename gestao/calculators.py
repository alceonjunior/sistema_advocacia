# gestao/calculators.py
from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from dateutil.relativedelta import relativedelta
import calendar

# AQUI ESTÁ A CORREÇÃO PRINCIPAL: O CAMINHO DA IMPORTAÇÃO FOI ATUALIZADO
from .services.indices.providers import ServicoIndices


class CalculadoraMonetaria:
    """
    Motor de cálculo judicial aprimorado com lógica pro-rata e aplicação correta de índices.
    """

    def calcular_fases(self, valor_original, fases):
        """
        Calcula o valor final processando uma lista de fases de cálculo em ordem.
        """
        saldo_atual = Decimal(valor_original)
        servico_indices = ServicoIndices()
        fases_resultados = []

        # Garante que as fases sejam processadas em ordem
        for fase in sorted(fases, key=lambda f: f.ordem):
            memoria_fase = []
            valor_inicial_fase = saldo_atual

            # --- LÓGICA DE CORREÇÃO MONETÁRIA (IPCA, IGP-M, etc.) ---
            if fase.indice != 'SELIC':
                indices_periodo = servico_indices.get_indices_por_periodo(fase.indice, fase.data_inicio, fase.data_fim)

                # Loop mês a mês para aplicar a correção
                data_corrente = fase.data_inicio
                while data_corrente <= fase.data_fim:
                    chave_indice = data_corrente.strftime('%Y-%m')
                    fator_mensal_cheio = indices_periodo.get(chave_indice, Decimal('0')) / 100

                    dias_no_mes = calendar.monthrange(data_corrente.year, data_corrente.month)[1]
                    dias_a_aplicar = dias_no_mes

                    # Lógica pro-rata para o primeiro mês (se não for o mês inteiro)
                    if data_corrente.year == fase.data_inicio.year and data_corrente.month == fase.data_inicio.month:
                        dias_a_aplicar = dias_no_mes - fase.data_inicio.day + 1

                    # Lógica pro-rata para o último mês (se não for o mês inteiro)
                    if data_corrente.year == fase.data_fim.year and data_corrente.month == fase.data_fim.month:
                        # Se o período todo ocorre no mesmo mês
                        if fase.data_inicio.strftime('%Y-%m') == fase.data_fim.strftime('%Y-%m'):
                            dias_a_aplicar = (fase.data_fim - fase.data_inicio).days + 1
                        else:  # Se for o mês final de um período maior
                            dias_a_aplicar = fase.data_fim.day

                    # Aplica o fator proporcional aos dias
                    fator_pro_rata = (fator_mensal_cheio / dias_no_mes) * dias_a_aplicar
                    valor_correcao = saldo_atual * fator_pro_rata

                    memoria_fase.append({
                        'descricao': f"Correção {fase.indice} ({data_corrente.strftime('%m/%Y')}, {dias_a_aplicar} de {dias_no_mes} dias)",
                        'valor': valor_correcao.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    })
                    saldo_atual += valor_correcao

                    # Avança para o primeiro dia do próximo mês
                    data_corrente = (data_corrente.replace(day=1) + relativedelta(months=1))

            # --- LÓGICA DE JUROS E SELIC ---
            if fase.indice == 'SELIC':
                indices_selic = servico_indices.get_indices_por_periodo('SELIC', fase.data_inicio, fase.data_fim)
                fator_acumulado = Decimal('1.0')

                # Itera dia a dia para aplicar a SELIC
                data_selic = fase.data_inicio
                while data_selic <= fase.data_fim:
                    taxa_dia = indices_selic.get(data_selic.isoformat(), Decimal('0'))
                    fator_acumulado *= (Decimal('1.0') + taxa_dia / 100)
                    data_selic += relativedelta(days=1)

                valor_corrigido_selic = valor_inicial_fase * fator_acumulado
                juros_selic = valor_corrigido_selic - valor_inicial_fase
                saldo_atual = valor_corrigido_selic  # Atualiza o saldo principal

                memoria_fase.append({
                    'descricao': f"Aplicação da Taxa SELIC de {fase.data_inicio.strftime('%d/%m/%Y')} a {fase.data_fim.strftime('%d/%m/%Y')}",
                    'valor': juros_selic.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                })

            elif fase.juros_taxa and fase.juros_taxa > 0:
                # Juros (simples/composto) são aplicados sobre o valor já corrigido pela inflação
                taxa_juros_mensal = fase.juros_taxa / 100
                num_dias = (fase.data_fim - fase.data_inicio).days + 1
                num_meses = Decimal(num_dias) / Decimal('30.4375')

                if fase.juros_tipo == 'SIMPLES':
                    juros_aplicados = saldo_atual * taxa_juros_mensal * num_meses
                else:  # COMPOSTO
                    juros_aplicados = saldo_atual * ((1 + taxa_juros_mensal) ** num_meses - 1)

                saldo_atual += juros_aplicados
                memoria_fase.append({
                    'descricao': f"Juros {fase.juros_tipo.lower()} de {fase.juros_taxa}% a.m.",
                    'valor': juros_aplicados.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                })

            # --- FINALIZAÇÃO DA FASE ---
            fases_resultados.append({
                'ordem': fase.ordem,
                'observacao': fase.observacao or f"Cálculo de {fase.data_inicio.strftime('%d/%m/%Y')} a {fase.data_fim.strftime('%d/%m/%Y')}",
                'valor_inicial': valor_inicial_fase.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                'memoria': memoria_fase,
                'valor_final': saldo_atual.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            })

        resumo_final = {
            'valor_original': Decimal(valor_original).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            'valor_final': saldo_atual.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        }

        return {
            "resumo": resumo_final,
            "fases_resultados": fases_resultados,
        }