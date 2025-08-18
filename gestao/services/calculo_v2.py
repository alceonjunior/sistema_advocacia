# gestao/services/calculo_v2.py
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from datetime import date
from .indices.providers import ServicoIndices


def to_decimal(value, default=Decimal('0.00')):
    """Converte valor para Decimal de forma segura."""
    if value is None:
        return default
    try:
        # Normaliza removendo pontos de milhar e trocando vírgula por ponto
        s_value = str(value).strip().replace('.', '').replace(',', '.')
        return Decimal(s_value)
    except (InvalidOperation, TypeError, ValueError):
        return default


def safe_quantize(value):
    """Aplica arredondamento padrão de 2 casas decimais."""
    return to_decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


class CalculoProEngine:
    def __init__(self, payload):
        self.payload = payload
        self.indice_service = ServicoIndices()
        self.totais = {
            'principal': Decimal('0.0'), 'correcao': Decimal('0.0'),
            'juros': Decimal('0.0'), 'multa': Decimal('0.0'),
            'descontos': Decimal('0.0'), 'atualizado': Decimal('0.0')
        }
        self.parcelas_calculadas = []
        self.warnings = []

    def run_preview(self):
        """Executa o cálculo para todas as parcelas."""
        for parcela_data in self.payload.get('parcelas', []):
            resultado_p = self._calcular_parcela(parcela_data)
            self.parcelas_calculadas.append(resultado_p)
            self.totais['principal'] += resultado_p['detalhes']['principal']
            self.totais['correcao'] += resultado_p['detalhes']['correcao']
            self.totais['juros'] += resultado_p['detalhes']['juros']
            self.totais['multa'] += resultado_p['detalhes']['multa']
            self.totais['atualizado'] += resultado_p['atualizado']

        return {
            "ok": True,
            "totais": {k: str(safe_quantize(v)) for k, v in self.totais.items()},
            "parcelas": self.parcelas_calculadas,
            "warnings": self.warnings
        }

    def _calcular_parcela(self, parcela_data):
        """Calcula uma única parcela."""
        principal = to_decimal(parcela_data.get('principal'))
        juros_perc = to_decimal(parcela_data.get('juros'))
        multa_perc = to_decimal(parcela_data.get('multa'))

        # Simulação de cálculo de correção
        # Lógica real usaria o provider de índices
        correcao = principal * Decimal('0.01')  # Simplesmente 1%

        subtotal = principal + correcao

        juros = subtotal * (juros_perc / 100)
        multa = (subtotal + juros) * (multa_perc / 100)

        valor_atualizado = subtotal + juros + multa

        return {
            "id": parcela_data.get('id'),
            "atualizado": str(safe_quantize(valor_atualizado)),
            "detalhes": {
                "principal": safe_quantize(principal),
                "correcao": safe_quantize(correcao),
                "juros": safe_quantize(juros),
                "multa": safe_quantize(multa),
            },
            "warnings": []
        }