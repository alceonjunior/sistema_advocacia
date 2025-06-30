# gestao/utils.py

from datetime import date
import locale


def data_por_extenso(data_obj: date) -> str:
    """
    Converte um objeto date para uma string por extenso em português do Brasil.
    Exemplo: date(2025, 6, 19) -> "19 de junho de 2025"

    Args:
        data_obj: Um objeto datetime.date.

    Returns:
        A data formatada como string por extenso.
    """
    if not isinstance(data_obj, date):
        return ""

    # Define o locale para português do Brasil para obter os nomes dos meses corretamente
    # Isso é mais robusto do que uma lista manual.
    try:
        # Tenta configurar o locale. Pode falhar dependendo do sistema operacional.
        locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
    except locale.Error:
        # Fallback para um formato que funciona na maioria dos sistemas
        locale.setlocale(locale.LC_TIME, 'Portuguese_Brazil')

    # Formata a data usando as diretivas do strftime
    # %d = dia do mês como número
    # %B = nome completo do mês (ex: "junho")
    # %Y = ano com quatro dígitos
    return data_obj.strftime("%d de %B de %Y")


def valor_por_extenso(valor):
    """
    Converte um valor monetário para sua representação por extenso em português.
    Limitado a valores abaixo de 1 milhão para simplicidade.
    """
    if valor is None or valor == 0:
        return "zero reais"

    valor_str = f"{valor:.2f}"
    partes = valor_str.split('.')
    reais, centavos = int(partes[0]), int(partes[1])

    unidades = ["", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove"]
    dezenas1 = ["dez", "onze", "doze", "treze", "quatorze", "quinze", "dezesseis", "dezessete", "dezoito", "dezenove"]
    dezenas2 = ["", "", "vinte", "trinta", "quarenta", "cinquenta", "sessenta", "setenta", "oitenta", "noventa"]
    centenas = ["", "cento", "duzentos", "trezentos", "quatrocentos", "quinhentos", "seiscentos", "setecentos",
                "oitocentos", "novecentos"]

    def _converter(n):
        if n == 0: return ""
        if n == 100: return "cem"

        partes_texto = []
        c, n = divmod(n, 100)
        if c > 0: partes_texto.append(centenas[c])

        d, u = divmod(n, 10)
        if d == 1:
            partes_texto.append(dezenas1[u])
        else:
            if d > 1: partes_texto.append(dezenas2[d])
            if u > 0: partes_texto.append(unidades[u])

        return " e ".join(filter(None, partes_texto))

    texto_reais = "real" if reais == 1 else "reais"
    extenso_reais = f"{_converter(reais)} {texto_reais}" if reais > 0 else ""

    texto_centavos = "centavo" if centavos == 1 else "centavos"
    extenso_centavos = f"{_converter(centavos)} {texto_centavos}" if centavos > 0 else ""

    if extenso_reais and extenso_centavos:
        return f"{extenso_reais} e {extenso_centavos}"
    return (extenso_reais or extenso_centavos).strip().capitalize()
