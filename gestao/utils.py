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

