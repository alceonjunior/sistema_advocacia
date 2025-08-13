# tests/test_calculo_engine.py
from django.test import TestCase
from unittest.mock import patch, MagicMock
from decimal import Decimal, ROUND_HALF_UP, getcontext
from datetime import date, datetime
from gestao.services.calculo import CalculoEngine

# Usaremos 6 casas internas p/ reduzir ruído de arredondamento e só quantizar ao final
getcontext().prec = 28

def q2(x: Decimal) -> Decimal:
    return Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class CalculoEngineTest(TestCase):
    """
    Testes unitários com providers mockados.
    Não dependem de internet nem de arquivos externos.
    """

    @patch("gestao.services.calculo.get_indice_info")
    def test_ipca_ate_citacao_depois_selic_exclusiva(self, mock_get_indice_info):
        """
        Cenário: IPCA (pro rata) do dia 15/01/2023 até 28/02/2023,
        e depois SELIC EXCLUSIVA (sem juros adicionais) em 01/03/2023 e 02/03/2023.

        - IPCA mensal mockado:
            jan/2023 = 0,50%
            fev/2023 = 0,80%
        - SELIC diária mockada:
            01/03/2023 = 0,05%
            02/03/2023 = 0,05%
        """

        # --- providers mockados ---
        ipca_provider = MagicMock()
        ipca_provider.get_indices.return_value = {
            # engine usa chave 'YYYY-MM' para monthly_variation
            "2023-01": Decimal("0.50"),
            "2023-02": Decimal("0.80"),
        }
        selic_provider = MagicMock()
        selic_provider.get_indices.return_value = {
            # engine usa chave 'YYYY-MM-DD' para daily_rate
            "2023-03-01": Decimal("0.05"),
            "2023-03-02": Decimal("0.05"),
        }

        def side_effect(indice_nome: str):
            if "SELIC" in indice_nome:
                return {"provider": selic_provider, "type": "daily_rate", "params": {}}
            if "IPCA" in indice_nome:
                return {"provider": ipca_provider, "type": "monthly_variation", "params": {}}
            raise AssertionError(f"Índice inesperado no teste: {indice_nome}")

        mock_get_indice_info.side_effect = side_effect

        # --- payload do cálculo ---
        payload = {
            "global": {},
            "parcelas": [
                {
                    "descricao": "Dano moral",
                    "valor_original": "10000.00",
                    "data_evento": "2023-01-15",
                    "faixas": [
                        {
                            "indice": "IPCA (IBGE)",
                            "data_inicio": "2023-01-15",
                            "data_fim": "2023-02-28",
                            "juros_tipo": "NENHUM",
                            "juros_taxa_mensal": "0.0",
                            "pro_rata": True,
                            "base_dias": "corridos",
                            "modo_selic_exclusiva": False,
                        },
                        {
                            "indice": "SELIC (Taxa diária)",
                            "data_inicio": "2023-03-01",
                            "data_fim": "2023-03-02",
                            "juros_tipo": "NENHUM",
                            "juros_taxa_mensal": "0.0",
                            "pro_rata": True,
                            "base_dias": "corridos",
                            "modo_selic_exclusiva": True,
                        },
                    ],
                }
            ],
            "extras": [],
        }

        # --- cálculo esperado (manual) ---
        V0 = Decimal("10000.00")

        # IPCA pro rata:
        # jan/2023: 0,50% * (17/31)  (de 15 a 31 => 17 dias)
        # fev/2023: 0,80% integral
        jan_var = Decimal("0.50") / Decimal("100")
        fev_var = Decimal("0.80") / Decimal("100")
        jan_factor = Decimal(1) + (jan_var * Decimal(17) / Decimal(31))
        fev_factor = Decimal(1) + fev_var
        fator_ipca = (jan_factor * fev_factor)

        # SELIC exclusiva, diária e composta em 2 dias com 0,05%/dia
        d1 = Decimal("0.05") / Decimal("100")
        fator_selic = (Decimal(1) + d1) * (Decimal(1) + d1)

        esperado_final = V0 * fator_ipca * fator_selic
        esperado_final = q2(esperado_final)

        # --- executa engine ---
        engine = CalculoEngine(payload)
        resultado = engine.run()

        print(resultado)  # <-- ADICIONE ESTA LINHA PARA VER O RESULTADO NO TERMINAL

        self.assertIn("parcelas", resultado)
        self.assertEqual(len(resultado["parcelas"]), 1)

        valor_final_engine = resultado["parcelas"][0]["valor_final"]
        self.assertEqual(q2(valor_final_engine), esperado_final)

        # A SELIC é exclusiva: não deve haver juros adicionais na faixa SELIC
        juros_total = resultado["parcelas"][0]["juros_total"]
        self.assertEqual(q2(juros_total), q2(Decimal("0.00")))

    @patch("gestao.services.calculo.get_indice_info")
    def test_ipca_com_juros_simples_pro_rata(self, mock_get_indice_info):
        """
        Cenário resumido: IPCA com juros SIMPLES de 1% a.m. entre 15/01/2024 e 31/03/2024.
        Varições mockadas:
            jan/24 = 0,50% ; fev/24 = 0,80% ; mar/24 = 0,70%
        """

        ipca_provider = MagicMock()
        ipca_provider.get_indices.return_value = {
            "2024-01": Decimal("0.50"),
            "2024-02": Decimal("0.80"),
            "2024-03": Decimal("0.70"),
        }

        def side_effect(indice_nome: str):
            return {"provider": ipca_provider, "type": "monthly_variation", "params": {}}

        mock_get_indice_info.side_effect = side_effect

        payload = {
            "global": {},
            "parcelas": [
                {
                    "descricao": "Valor Principal",
                    "valor_original": "5000.00",
                    "data_evento": "2024-01-15",
                    "faixas": [
                        {
                            "indice": "IPCA (IBGE)",
                            "data_inicio": "2024-01-15",
                            "data_fim": "2024-03-31",
                            "juros_tipo": "SIMPLES",
                            "juros_taxa_mensal": "1.0",
                            "pro_rata": True,
                            "base_dias": "corridos",
                            "modo_selic_exclusiva": False,
                        }
                    ],
                }
            ],
            "extras": [],
        }

        # Esperado: correção *depois* juros simples a 1% a.m. com pro rata.
        V0 = Decimal("5000.00")
        # Corre
