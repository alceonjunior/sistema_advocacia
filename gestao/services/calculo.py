# gestao/services/calculo.py

import calendar
import logging
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from dateutil.relativedelta import relativedelta

from .indices.catalog import get_indice_info
from .indices.providers import PROVIDERS_MAP

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
            'memoria_calculo': {}
        }

    def run(self):
        """
        Orquestra a execução do cálculo em três etapas.
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
                self.results['parcelas'].append({
                    'descricao': parcela_data.get('descricao', 'ERRO'),
                    'valor_original': Decimal(parcela_data.get('valor_original', '0.0')),
                    'correcao_total': Decimal('0.0'),
                    'juros_total': Decimal('0.0'), 'valor_final': Decimal(parcela_data.get('valor_original', '0.0')),
                    'memoria_detalhada': [{'error': f"ERRO NO CÁLCULO: {e}"}]
                })

        self._calcular_extras()

        # Consolida o total geral no final, após todos os cálculos.
        self.results['resumo']['total_geral'] = (
                self.results['resumo']['principal'] + self.results['resumo']['correcao'] +
                self.results['resumo']['juros'] + self.results['resumo']['multas'] +
                self.results['resumo']['honorarios']
        )

        self._gerar_memoria_de_calculo_estruturada()
        return self.results

    def _get_dias_pro_rata(self, data_ref, data_inicio_faixa, data_fim_faixa):
        dias_no_mes = calendar.monthrange(data_ref.year, data_ref.month)[1]
        if data_inicio_faixa.year == data_fim_faixa.year and data_inicio_faixa.month == data_fim_faixa.month:
            return (data_fim_faixa - data_inicio_faixa).days + 1
        if data_inicio_faixa.year == data_ref.year and data_inicio_faixa.month == data_ref.month:
            return dias_no_mes - data_inicio_faixa.day + 1
        if data_fim_faixa.year == data_ref.year and data_fim_faixa.month == data_ref.month:
            return data_fim_faixa.day
        return dias_no_mes

    def _calcular_parcela(self, parcela_data):
        valor_original = Decimal(parcela_data['valor_original'])
        valor_atual = valor_original
        memoria_detalhada = []
        correcao_total_parcela = Decimal('0.0')
        juros_total_parcela = Decimal('0.0')

        faixas = sorted(parcela_data.get('faixas', []), key=lambda x: x['data_inicio'])

        for faixa in faixas:
            data_inicio = datetime.strptime(faixa['data_inicio'], '%Y-%m-%d').date()
            data_fim = datetime.strptime(faixa['data_fim'], '%Y-%m-%d').date()
            info_indice = get_indice_info(faixa['indice'])

            provider_name = info_indice.get('provider')
            ProviderClass = PROVIDERS_MAP.get(provider_name)
            if not ProviderClass:
                raise ValueError(f"Provider '{provider_name}' não encontrado.")
            provider = ProviderClass()

            indices = provider.get_indices(
                inicio=data_inicio, fim=data_fim,
                params=info_indice.get('params', {}),
                index_type=info_indice.get('type')
            )

            valor_base_faixa = valor_atual
            fator_correcao = Decimal('1.0')

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

            juros_faixa = Decimal('0.0')
            if not faixa.get('modo_selic_exclusiva', False) and faixa['juros_tipo'] != 'NENHUM':
                taxa_mensal = Decimal(faixa['juros_taxa_mensal']) / 100
                total_dias = (data_fim - data_inicio).days + 1
                meses = Decimal(total_dias) / Decimal('30.4375')
                if faixa['juros_tipo'] == 'SIMPLES':
                    juros_faixa = valor_corrigido_faixa * taxa_mensal * meses
                elif faixa['juros_tipo'] == 'COMPOSTO':
                    juros_faixa = valor_corrigido_faixa * (((1 + taxa_mensal) ** meses) - 1)

            valor_atual = valor_corrigido_faixa + juros_faixa
            correcao_total_parcela += correcao_faixa
            juros_total_parcela += juros_faixa

            memoria_detalhada.append({
                'faixa_nome': info_indice.get('label', faixa['indice']),
                'data_inicio': data_inicio.strftime('%d/%m/%Y'), 'data_fim': data_fim.strftime('%d/%m/%Y'),
                'valor_correcao': f"{correcao_faixa:,.2f}", 'valor_juros': f"{juros_faixa:,.2f}",
                'valor_atualizado_faixa': f"{valor_atual:,.2f}"
            })

        return {
            'descricao': parcela_data['descricao'],
            'valor_original': valor_original.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            'correcao_total': correcao_total_parcela.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            'juros_total': juros_total_parcela.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            'valor_final': valor_atual.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            'memoria_detalhada': memoria_detalhada,
        }

    def _calcular_extras(self):
        """
        Calcula itens como multas e honorários com base nos totais já apurados,
        trabalhando com a estrutura de dicionário enviada pelo frontend.
        """
        extras = self.payload.get('extras', {})
        if not isinstance(extras, dict): return

        base_principal_corrigido = self.results['resumo']['principal'] + self.results['resumo']['correcao']
        base_principal_juros = base_principal_corrigido + self.results['resumo']['juros']

        multa_perc = Decimal(extras.get('multa_percentual', '0.0'))
        if multa_perc > 0:
            base_multa = base_principal_juros if extras.get('multa_sobre_juros') else base_principal_corrigido
            valor_multa = base_multa * (multa_perc / Decimal('100.0'))
            self.results['resumo']['multas'] = valor_multa.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        honorarios_perc = Decimal(extras.get('honorarios_percentual', '0.0'))
        if honorarios_perc > 0:
            base_honorarios = base_principal_juros + self.results['resumo'].get('multas', Decimal('0.0'))
            valor_honorarios = base_honorarios * (honorarios_perc / Decimal('100.0'))
            self.results['resumo']['honorarios'] = valor_honorarios.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def _gerar_memoria_de_calculo_estruturada(self):
        """Gera uma memória de cálculo estruturada para renderização no template."""
        self.results['memoria_calculo'] = {
            'resumo_total': [
                {'label': '(+) Valor Principal Original', 'value': self.results['resumo']['principal']},
                {'label': '(+) Correção Monetária Total', 'value': self.results['resumo']['correcao']},
                {'label': '(+) Juros Totais', 'value': self.results['resumo']['juros']},
                {'label': '(+) Multas', 'value': self.results['resumo']['multas']},
                {'label': '(+) Honorários', 'value': self.results['resumo']['honorarios']},
            ],
            'total_geral': self.results['resumo']['total_geral'],
            'detalhe_parcelas': self.results['parcelas']
        }