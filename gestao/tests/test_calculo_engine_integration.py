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
    Estes testes realizam chamadas reais às APIs do Banco Central e IBGE.
    """

    def setUp(self):
        if not CAN_RUN_NETWORK_TESTS:
            self.skipTest("A biblioteca 'requests' é necessária para rodar os testes de integração.")

    def test_valida_contra_pdf_exemplo(self):
        """
        Valida o cálculo do cenário do PDF (Proc. 0013996-16.2025.8.16.0019)
        buscando dados reais das APIs para garantir a precisão do sistema.
        """
        print("\nExecutando teste de integração com APIs reais para validar contra o PDF... (Pode demorar)")

        # --- Payload do Cálculo ---
        # Reproduz exatamente os parâmetros do PDF
        payload = {
            "global": {
                "observacoes": "Teste de integração com dados reais de API, validando o PDF do processo 0013996-16."
            },
            "parcelas": [{
                "descricao": "Parcela do Processo",
                "valor_original": "18250.00",
                "data_evento": "2020-03-13",
                "faixas": [
                    {
                        "indice": "IPCA-E (IBGE)",
                        "data_inicio": "2020-03-13",
                        "data_fim": "2023-11-03",  # Conforme PDF [cite: 14]
                        "juros_tipo": "NENHUM",
                        "juros_taxa_mensal": "0.0",
                        "pro_rata": True,
                        "modo_selic_exclusiva": False,
                    },
                    {
                        "indice": "SELIC (Taxa diária)",
                        "data_inicio": "2023-11-04",
                        # AJUSTE PRINCIPAL: A data final agora corresponde à do PDF [cite: 15]
                        "data_fim": "2025-08-12",
                        "juros_tipo": "NENHUM",
                        "juros_taxa_mensal": "0.0",
                        "pro_rata": True,
                        "modo_selic_exclusiva": True,
                    }
                ]
            }],
            "extras": [],
        }

        # --- Executa a Engine ---
        engine = CalculoEngine(payload)
        resultado = engine.run()

        # --- Validação ---
        # O valor final esperado é o que consta no resumo do PDF.
        valor_final_esperado_pdf = Decimal("27904.63")  # [cite: 10]

        resumo = resultado['resumo']
        valor_original = Decimal(payload['parcelas'][0]['valor_original'])

        print(f"\n--- Comparativo do Cálculo ---")
        print(f"Valor Original: R$ {valor_original:,.2f}")
        print(f"Valor Final Calculado (Sistema): R$ {resumo['total_geral']:,.2f}")
        print(f"Valor Final Esperado (PDF):    R$ {valor_final_esperado_pdf:,.2f}")

        diferenca = abs(resumo['total_geral'] - valor_final_esperado_pdf)
        print(f"Diferença Absoluta: R$ {diferenca:,.2f}")

        self.assertIsNotNone(resultado, "O motor de cálculo não retornou um resultado.")
        self.assertIn('resumo', resultado)

        # 1. Validação principal: o valor calculado deve ser muito próximo ao do PDF.
        # Usamos uma tolerância (delta) para absorver micro-diferenças de arredondamento
        # entre a nossa engine e a ferramenta que gerou o PDF.
        self.assertAlmostEqual(resumo['total_geral'], valor_final_esperado_pdf, places=2,
                               msg=f"O valor final calculado {resumo['total_geral']} diverge do esperado {valor_final_esperado_pdf}")

        # 2. Garante que os juros são zero, conforme o PDF [cite: 19]
        self.assertEqual(resumo['juros'], Decimal("0.00"))