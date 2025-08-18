# gestao/services/calculo.py

import calendar
import logging
from datetime import date
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from dateutil.relativedelta import relativedelta

from .indices.catalog import get_indice_info
from .indices.providers import PROVIDERS_MAP

logger = logging.getLogger(__name__)


class CalculoEngine:
    """
    Motor de cálculo judicial robusto. Opera com dados pré-validados e tipados.
    """

    def __init__(self, payload: dict):
        self.payload = payload
        self.results = {
            'parcelas': [],
            'resumo': {
                'principal': Decimal('0.0'), 'correcao': Decimal('0.0'), 'juros': Decimal('0.0'),
                'multas': Decimal('0.0'), 'honorarios': Decimal('0.0')
            },
            'memoria_calculo': {}
        }

    def run(self):
        """Orquestra a execução do cálculo de forma segura."""
        for parcela_data in self.payload.get('parcelas', []):
            try:
                resultado_parcela = self._calcular_parcela(parcela_data)
                self.results['parcelas'].append(resultado_parcela)
                # Acumula apenas se o cálculo foi bem-sucedido
                self.results['resumo']['principal'] += resultado_parcela['valor_original']
                self.results['resumo']['correcao'] += resultado_parcela['correcao_total']
                self.results['resumo']['juros'] += resultado_parcela['juros_total']
            except Exception as e:
                descricao_erro = parcela_data.get('descricao', 'Desconhecida')
                logger.error(f"Erro CRÍTICO ao calcular parcela '{descricao_erro}': {e}", exc_info=True)
                valor_original_fallback = parcela_data.get('valor_original', Decimal('0.0'))
                self.results['parcelas'].append({
                    'descricao': f"ERRO: {descricao_erro}",
                    'valor_original': valor_original_fallback,
                    'data_evento': parcela_data.get('data_evento').isoformat() if isinstance(
                        parcela_data.get('data_evento'), date) else None,
                    'correcao_total': Decimal('0.0'), 'juros_total': Decimal('0.0'),
                    'valor_final': valor_original_fallback,
                    'memoria_detalhada': [{'error': f"ERRO NO CÁLCULO: {e}"}]
                })

        self._calcular_extras()

        # Cálculo explícito e seguro do total geral
        resumo = self.results['resumo']
        resumo['total_geral'] = resumo['principal'] + resumo['correcao'] + resumo['juros'] + resumo['multas'] + resumo[
            'honorarios']

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

    def _calcular_parcela(self, parcela_data: dict):
        valor_original = parcela_data['valor_original']
        valor_atual = valor_original
        correcao_total_parcela = Decimal('0.0')
        juros_total_parcela = Decimal('0.0')

        faixas = sorted(parcela_data.get('faixas', []), key=lambda x: x['data_inicio'])

        for faixa in faixas:
            data_inicio, data_fim = faixa['data_inicio'], faixa['data_fim']
            info_indice = get_indice_info(faixa['indice'])
            ProviderClass = PROVIDERS_MAP[info_indice['provider']]
            provider = ProviderClass()

            indices = provider.get_indices(
                inicio=data_inicio, fim=data_fim, params=info_indice.get('params', {}),
                index_type=info_indice.get('type')
            )

            if not indices and info_indice['provider'] == 'BacenSGSProvider':
                raise ConnectionError(
                    f"Não foi possível obter dados para o índice '{faixa['indice']}'. A API do Banco Central pode estar instável.")

            valor_base_faixa = valor_atual
            fator_correcao = Decimal('1.0')

            if info_indice['type'] == 'monthly_variation':
                data_loop = data_inicio.replace(day=1)
                while data_loop <= data_fim:
                    variacao = indices.get(data_loop.strftime('%Y-%m'), Decimal('0.0')) / 100
                    if faixa.get('pro_rata', True):
                        dias_aplicar = self._get_dias_pro_rata(data_loop, data_inicio, data_fim)
                        dias_no_mes = calendar.monthrange(data_loop.year, data_loop.month)[1]
                        if dias_no_mes == 0: raise ValueError("Divisão por zero: dias no mês é zero.")
                        fator_correcao *= (1 + (variacao / Decimal(dias_no_mes) * Decimal(dias_aplicar)))
                    else:
                        fator_correcao *= (1 + variacao)
                    data_loop += relativedelta(months=1)
            elif info_indice['type'] == 'daily_rate':
                data_loop = data_inicio
                while data_loop <= data_fim:
                    taxa_dia = indices.get(data_loop.isoformat(), Decimal('0.0')) / 100
                    fator_correcao *= (1 + taxa_dia)
                    data_loop += relativedelta(days=1)

            if not fator_correcao.is_finite():
                raise InvalidOperation(
                    f"Fator de correção tornou-se não-finito na faixa do índice '{faixa['indice']}'.")

            correcao_faixa = valor_base_faixa * (fator_correcao - 1)
            valor_corrigido_faixa = valor_base_faixa + correcao_faixa
            juros_faixa = Decimal('0.0')

            if not faixa.get('modo_selic_exclusiva', False) and faixa['juros_tipo'] != 'NENHUM':
                taxa_mensal = faixa['juros_taxa_mensal'] / 100
                meses = Decimal((data_fim - data_inicio).days + 1) / Decimal('30.4375')
                if faixa['juros_tipo'] == 'SIMPLES':
                    juros_faixa = valor_corrigido_faixa * taxa_mensal * meses
                elif faixa['juros_tipo'] == 'COMPOSTO':
                    base_juros = 1 + taxa_mensal
                    if base_juros < 0 and meses % 1 != 0:
                        raise InvalidOperation("Cálculo de juros compostos inválido (raiz de número negativo).")
                    juros_faixa = valor_corrigido_faixa * ((base_juros ** meses) - 1)

            valor_atual = valor_corrigido_faixa + juros_faixa
            if not valor_atual.is_finite():
                raise InvalidOperation(f"Valor atual tornou-se não-finito ({valor_atual}) após juros/correção.")

            correcao_total_parcela += correcao_faixa
            juros_total_parcela += juros_faixa

        if not all(v.is_finite() for v in [valor_original, correcao_total_parcela, juros_total_parcela, valor_atual]):
            raise InvalidOperation("Resultado final da parcela contém valores não-finitos.")

        return {
            'descricao': parcela_data['descricao'],
            'data_evento': parcela_data['data_evento'].isoformat(),
            'valor_original': valor_original,
            'correcao_total': correcao_total_parcela,
            'juros_total': juros_total_parcela,
            'valor_final': valor_atual,
        }

    def _calcular_extras(self):
        extras = self.payload.get('extras', {})
        if not isinstance(extras, dict): return
        base_principal_corrigido = self.results['resumo']['principal'] + self.results['resumo']['correcao']
        base_principal_juros = base_principal_corrigido + self.results['resumo']['juros']
        multa_perc = extras.get('multa_percentual', Decimal('0.0'))
        if multa_perc > 0:
            base_multa = base_principal_juros if extras.get('multa_sobre_juros') else base_principal_corrigido
            self.results['resumo']['multas'] = (base_multa * (multa_perc / 100))
        honorarios_perc = extras.get('honorarios_percentual', Decimal('0.0'))
        if honorarios_perc > 0:
            base_honorarios = base_principal_juros + self.results['resumo'].get('multas', Decimal('0.0'))
            self.results['resumo']['honorarios'] = (base_honorarios * (honorarios_perc / 100))

    def _gerar_memoria_de_calculo_estruturada(self):
        def format_brl(d_value):
            if not isinstance(d_value, Decimal) or not d_value.is_finite():
                return "Erro de Cálculo"
            quantized = d_value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            return f"{quantized:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        detalhe_parcelas_formatado = []
        for p in self.results['parcelas']:
            if 'error' in p:
                detalhe_parcelas_formatado.append(p)
                continue

            valor_apos_correcao = p['valor_original'] + p['correcao_total']
            detalhe_parcelas_formatado.append({
                'descricao': p['descricao'], 'data_valor': p.get('data_evento'),
                'valor_original': format_brl(p['valor_original']),
                'valor_apos_correcao': format_brl(valor_apos_correcao),
                'juros_aplicados': format_brl(p['juros_total']),
                'valor_final': format_brl(p['valor_final']),
            })

        resumo_quantized = {k: v.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) for k, v in
                            self.results['resumo'].items() if isinstance(v, Decimal) and v.is_finite()}

        self.results['memoria_calculo'] = {
            'resumo_total': [
                {'label': '(+) Valor Principal', 'value': resumo_quantized.get('principal', Decimal('0.0'))},
                {'label': '(+) Correção Monetária', 'value': resumo_quantized.get('correcao', Decimal('0.0'))},
                {'label': '(+) Juros', 'value': resumo_quantized.get('juros', Decimal('0.0'))},
                {'label': '(+) Multas', 'value': resumo_quantized.get('multas', Decimal('0.0'))},
                {'label': '(+) Honorários', 'value': resumo_quantized.get('honorarios', Decimal('0.0'))},
            ],
            'total_geral': resumo_quantized.get('total_geral', Decimal('0.0')),
            'detalhe_parcelas': detalhe_parcelas_formatado
        }