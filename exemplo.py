class Veiculo:
    def __init__(self, marca, modelo, ano, placa):
        self.marca = marca
        self.modelo = modelo
        self.ano = ano
        self.placa = placa

    def acelerar(self):
        print("Aumentando velocidade")


class Carro(Veiculo):
    def __init__(self, marca, modelo, ano, placa, qtd_portas):
        super().__init__(marca, modelo, ano, placa)
        self.qtd_portas = qtd_portas

    def fechar_porta(self):
        print("Porta fechada")


# Testes
fusca = Veiculo("Volks", "Fusca", 1979, "AAABBB")
print(fusca.marca)

carro_teste = Carro("Marca", "Modelo", 2000, "AAABBB", 4)
carro_teste.fechar_porta()
