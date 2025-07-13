from django import template
import re

register = template.Library()


@register.filter(name='get_item')
def get_item(dictionary, key):
    return dictionary.get(key)


# --- FILTROS ADICIONADOS ---

@register.filter(name='mask_cpf_cnpj')
def mask_cpf_cnpj(value):
    """Aplica máscara de CPF (###.###.###-##) ou CNPJ (##.###.###/####-##)."""
    if not value:
        return ""

    # Remove todos os caracteres que não são dígitos
    value = re.sub(r'\D', '', str(value))

    if len(value) == 11:
        return f"{value[:3]}.{value[3:6]}.{value[6:9]}-{value[9:]}"
    elif len(value) == 14:
        return f"{value[:2]}.{value[2:5]}.{value[5:8]}/{value[8:12]}-{value[12:]}"
    else:
        return value  # Retorna o valor original se não for CPF ou CNPJ


@register.filter(name='mask_phone')
def mask_phone(value):
    """Aplica máscara de telefone (##) ####-#### ou (##) #####-####."""
    if not value:
        return ""

    # Remove todos os caracteres que não são dígitos
    value = re.sub(r'\D', '', str(value))

    if len(value) == 11:
        return f"({value[:2]}) {value[2:7]}-{value[7:]}"
    elif len(value) == 10:
        return f"({value[:2]}) {value[2:6]}-{value[6:]}"
    else:
        return value  # Retorna o valor original se não for um telefone reconhecido