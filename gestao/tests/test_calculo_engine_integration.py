# gestao/tests/test_calculo_engine_integration.py

from django.test import TestCase, tag
from decimal import Decimal
from datetime import date

# Importamos a engine de cálculo que fará as chamadas reais
from gestao.services.calculo import CalculoEngine

# Ignoramos o teste se as dependências de rede não estiverem disponíveis
try:
    import requests
    CAN_RUN_NETWORK_TESTS = True
except ImportError:
    CAN_RUN_NETWORK_TESTS = False


@tag('integration')
class CalculoEngineIntegrationTest(TestCase):
    """
    Testes de Integração para a CalculoEngine.
    Estes testes realizam chamadas reais às APIs do Banco Central para validar
    a precisão do motor de cálculo contra um cenário real documentado.
    """

    def setUp(self):
        if not CAN_RUN_NETWORK_TESTS:
            self.skipTest("A biblioteca 'requests' é necessária para rodar os testes de integração.")

    def test_valida_contra_pdf_exemplo(self):
        """
        Valida o cálculo do cenário do PDF (Proc. 0013996-16.2025.8.16.0019)
        buscando dados reais das APIs. Este teste garante que a engine de cálculo,
        quando alimentada com dados já tipados (Decimal e date), produz o resultado esperado.
        """
        print("\nExecutando teste de integração com APIs reais para validar contra o PDF... (Pode demorar)")

        # --- Payload do Cálculo ---
        # Os dados aqui estão no formato que a CalculoEngine espera receber
        # após a validação e sanitização da view.
        payload = {
            "global": {
                "observacoes": "Teste de integração com dados reais de API, validando o PDF do processo 0013996-16."
            },
            "parcelas": [{
                "descricao": "Parcela do Processo",
                "valor_original": Decimal("18250.00"),
                "data_evento": date(2020, 3, 13),
                "faixas": [
                    {
                        # CORREÇÃO: Usando a chave "IPCA-E" do catalog.py
                        "indice": "IPCA-E",
                        "data_inicio": date(2020, 3, 13),
                        "data_fim": date(2023, 11, 3),
                        "juros_tipo": "NENHUM",
                        "juros_taxa_mensal": Decimal("0.0"),
                        "pro_rata": True,
                        "modo_selic_exclusiva": False,
                    },
                    {
                        # CORREÇÃO: Usando a chave "SELIC_DIARIA" do catalog.py
                        "indice": "SELIC_DIARIA",
                        "data_inicio": date(2023, 11, 4),
                        "data_fim": date(2025, 8, 12),
                        "juros_tipo": "NENHUM",
                        "juros_taxa_mensal": Decimal("0.0"),
                        "pro_rata": True,
                        "modo_selic_exclusiva": True,
                    }
                ]
            }],
            "extras": {
                "multa_percentual": Decimal("0.0"),
                "honorarios_percentual": Decimal("0.0")
            },
        }

        # --- Executa a Engine ---
        engine = CalculoEngine(payload)
        resultado = engine.run()

        # --- Validação ---
        valor_final_esperado_pdf = Decimal("27904.63")

        self.assertIsNotNone(resultado, "O motor de cálculo não retornou um resultado.")
        self.assertIn('resumo', resultado)
        self.assertIn('total_geral', resultado['resumo'])

        resumo = resultado['resumo']
        valor_original = payload['parcelas'][0]['valor_original']
        valor_final_calculado = resumo['total_geral']

        print("\n--- Comparativo do Cálculo ---")
        print(f"Valor Original: R$ {valor_original:,.2f}")
        print(f"Valor Final Calculado (Sistema): R$ {valor_final_calculado:,.2f}")
        print(f"Valor Final Esperado (PDF):    R$ {valor_final_esperado_pdf:,.2f}")

        diferenca = abs(valor_final_calculado - valor_final_esperado_pdf)
        print(f"Diferença Absoluta: R$ {diferenca:,.2f}")

        # Validação principal com tolerância para pequenas diferenças de arredondamento
        self.assertAlmostEqual(
            valor_final_calculado,
            valor_final_esperado_pdf,
            places=2,
            msg=f"O valor final calculado {valor_final_calculado} diverge do esperado {valor_final_esperado_pdf}"
        )

        # Garante que os juros são zero, conforme o PDF
        self.assertEqual(resumo['juros'].quantize(Decimal('0.01')), Decimal("0.00"))