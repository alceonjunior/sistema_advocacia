# gestao/services/calculo.py

import calendar
import logging
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from dateutil.relativedelta import relativedelta

from .indices.catalog import get_indice_info

logger = logging.getLogger(__name__)


class CalculoEngine:
    """
    Motor de cálculo judicial completo. Processa um payload estruturado com
    parcelas, faixas de cálculo e itens extras, retornando um resultado detalhado.
    """

    def __init__(self, payload):
        self.payload = payload
        self.results = {
            'parcelas': [],
            'extras_calculados': [],
            'resumo': {
                'principal': Decimal('0.0'), 'correcao': Decimal('0.0'), 'juros': Decimal('0.0'),
                'multas': Decimal('0.0'), 'honorarios': Decimal('0.0'), 'custas': Decimal('0.0'),
                'total_geral': Decimal('0.0')
            },
            'memoria_texto': ""
        }

    def run(self):
        """
        Orquestra a execução do cálculo em três etapas:
        1. Calcula o valor atualizado de cada parcela individualmente.
        2. Calcula os itens extras (multas, honorários) com base nos totais.
        3. Monta o resumo final e a memória de cálculo textual.
        """
        for parcela_data in self.payload.get('parcelas', []):
            try:
                resultado_parcela = self._calcular_parcela(parcela_data)
                self.results['parcelas'].append(resultado_parcela)
                self.results['resumo']['principal'] += resultado_parcela['valor_original']
                self.results['resumo']['correcao'] += resultado_parcela['correcao_total']
                self.results['resumo']['juros'] += resultado_parcela['juros_total']
            except Exception as e:
                logger.error(f"Erro ao calcular parcela '{parcela_data.get('descricao')}': {e}", exc_info=True)
                # Retorna um resultado de erro para a parcela específica
                self.results['parcelas'].append({
                    'descricao': parcela_data.get('descricao', 'ERRO'),
                    'valor_original': Decimal(parcela_data.get('valor_original', '0.0')),
                    'correcao_total': Decimal('0.0'), 'juros_total': Decimal('0.0'),
                    'valor_final': Decimal(parcela_data.get('valor_original', '0.0')),
                    'memoria_detalhada': [f"ERRO NO CÁLCULO: {e}"]
                })

        self._calcular_extras()
        self.results['resumo']['total_geral'] = sum(
            val for key, val in self.results['resumo'].items() if key != 'total_geral'
        )
        self._gerar_memoria_texto()
        return self.results

    def _get_dias_pro_rata(self, data_ref, data_inicio_faixa, data_fim_faixa):
        """Calcula os dias a serem considerados para o cálculo pro rata em um determinado mês."""
        dias_no_mes = calendar.monthrange(data_ref.year, data_ref.month)[1]
        if data_inicio_faixa.year == data_fim_faixa.year and data_inicio_faixa.month == data_fim_faixa.month:
            return (data_fim_faixa - data_inicio_faixa).days + 1
        if data_inicio_faixa.year == data_ref.year and data_inicio_faixa.month == data_ref.month:
            return dias_no_mes - data_inicio_faixa.day + 1
        if data_fim_faixa.year == data_ref.year and data_fim_faixa.month == data_ref.month:
            return data_fim_faixa.day
        return dias_no_mes

    def _calcular_parcela(self, parcela_data):
        """Calcula uma única parcela, aplicando todas as suas faixas de correção e juros em sequência."""
        valor_original = Decimal(parcela_data['valor_original'])
        valor_atual = valor_original
        memoria_detalhada = []
        correcao_total_parcela = Decimal('0.0')
        juros_total_parcela = Decimal('0.0')

        faixas = sorted(parcela_data['faixas'], key=lambda x: x['data_inicio'])

        for faixa in faixas:
            data_inicio = datetime.strptime(faixa['data_inicio'], '%Y-%m-%d').date()
            data_fim = datetime.strptime(faixa['data_fim'], '%Y-%m-%d').date()
            info_indice = get_indice_info(faixa['indice'])

            # AQUI ESTÁ A CORREÇÃO: Passamos o `index_type` para o provedor
            provider = info_indice['provider']
            params = info_indice['params']
            index_type = info_indice.get('type')

            indices = provider.get_indices(
                data_inicio=data_inicio,
                data_fim=data_fim,
                index_type=index_type,
                **params
            )

            valor_base_faixa = valor_atual
            fator_correcao = Decimal('1.0')

            # --- 1. Correção Monetária ---
            if info_indice['type'] == 'monthly_variation':
                data_loop = data_inicio.replace(day=1)
                while data_loop <= data_fim:
                    mes_chave = data_loop.strftime('%Y-%m')
                    variacao = indices.get(mes_chave, Decimal('0.0')) / 100
                    if faixa.get('pro_rata', True):
                        dias_aplicar = self._get_dias_pro_rata(data_loop, data_inicio, data_fim)
                        dias_no_mes = calendar.monthrange(data_loop.year, data_loop.month)[1]
                        fator_correcao *= (1 + (variacao / dias_no_mes * dias_aplicar))
                    else:
                        fator_correcao *= (1 + variacao)
                    data_loop += relativedelta(months=1)

            elif info_indice['type'] == 'daily_rate':
                data_loop = data_inicio
                while data_loop <= data_fim:
                    taxa_dia = indices.get(data_loop.isoformat(), Decimal('0.0')) / 100
                    fator_correcao *= (1 + taxa_dia)
                    data_loop += relativedelta(days=1)

            correcao_faixa = valor_base_faixa * (fator_correcao - 1)
            valor_corrigido_faixa = valor_base_faixa + correcao_faixa

            # --- 2. Juros ---
            juros_faixa = Decimal('0.0')
            if not faixa.get('modo_selic_exclusiva', False) and faixa['juros_tipo'] != 'NENHUM':
                taxa_mensal = Decimal(faixa['juros_taxa_mensal']) / 100
                total_dias = (data_fim - data_inicio).days + 1
                meses = Decimal(total_dias) / Decimal('30.4375')

                if faixa['juros_tipo'] == 'SIMPLES':
                    juros_faixa = valor_corrigido_faixa * taxa_mensal * meses
                elif faixa['juros_tipo'] == 'COMPOSTO':
                    juros_faixa = valor_corrigido_faixa * (((1 + taxa_mensal) ** meses) - 1)

            # --- 3. Consolidação da Faixa ---
            valor_atual = valor_corrigido_faixa + juros_faixa
            correcao_total_parcela += correcao_faixa
            juros_total_parcela += juros_faixa

            memoria_detalhada.append(
                f"Faixa [{faixa['indice']}] de {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}: "
                f"Correção R$ {correcao_faixa:,.2f}, Juros R$ {juros_faixa:,.2f}"
            )

        return {
            'descricao': parcela_data['descricao'],
            'valor_original': valor_original.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            'correcao_total': correcao_total_parcela.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            'juros_total': juros_total_parcela.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            'valor_final': valor_atual.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            'memoria_detalhada': memoria_detalhada,
        }

    def _calcular_extras(self):
        """Calcula itens como multas e honorários com base nos totais já apurados."""
        base_principal_corrigido = self.results['resumo']['principal'] + self.results['resumo']['correcao']
        base_principal_juros = base_principal_corrigido + self.results['resumo']['juros']

        for extra in self.payload.get('extras', []):
            valor_extra = Decimal('0.0')
            descricao_extra = extra.get('descricao', 'Item extra')

            if extra.get('percentual'):
                percentual = Decimal(extra['percentual']) / 100
                base_de_calculo = Decimal('0.0')
                if extra['base_incidencia'] == 'PRINCIPAL_CORRIGIDO':
                    base_de_calculo = base_principal_corrigido
                elif extra['base_incidencia'] == 'PRINCIPAL_MAIS_JUROS':
                    base_de_calculo = base_principal_juros

                valor_extra = base_de_calculo * percentual

            # (Futuro) Lógica para corrigir valores fixos de custas/multas seria adicionada aqui

            # Adiciona ao resumo e à lista de extras calculados
            tipo = extra.get('tipo', '').lower() + 's'  # ex: 'multa' -> 'multas'
            if tipo in self.results['resumo']:
                self.results['resumo'][tipo] += valor_extra
                self.results['extras_calculados'].append({'descricao': descricao_extra, 'valor': valor_extra})

    def _gerar_memoria_texto(self):
        """Gera um relatório textual completo do cálculo em formato Markdown."""
        f = lambda v: f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        memoria = [f"## Memória de Cálculo\n"]
        memoria.append("**Resumo Geral do Débito**\n")
        memoria.append("| Discriminação | Valor |")
        memoria.append("|:---|---:|")
        memoria.append(f"| (+) Valor Principal Original | {f(self.results['resumo']['principal'])} |")
        memoria.append(f"| (+) Correção Monetária Total | {f(self.results['resumo']['correcao'])} |")
        memoria.append(f"| (+) Juros Totais | {f(self.results['resumo']['juros'])} |")
        if self.results['resumo']['multas'] > 0:
            memoria.append(f"| (+) Multas | {f(self.results['resumo']['multas'])} |")
        if self.results['resumo']['honorarios'] > 0:
            memoria.append(f"| (+) Honorários | {f(self.results['resumo']['honorarios'])} |")
        memoria.append(f"| **(=) Total Geral Devido** | **{f(self.results['resumo']['total_geral'])}** |")
        memoria.append("\n---\n")

        for i, parcela in enumerate(self.results['parcelas']):
            memoria.append(f"### Detalhamento da Parcela {i + 1}: {parcela['descricao']}\n")
            memoria.append(f"- **Valor Original:** {f(parcela['valor_original'])}")
            for detalhe in parcela['memoria_detalhada']:
                memoria.append(f"- {detalhe}")
            memoria.append(f"- **Subtotal da Parcela:** {f(parcela['valor_final'])}\n")

        self.results['memoria_texto'] = "\n".join(memoria)