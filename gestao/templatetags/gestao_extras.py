# gestao/templatetags/gestao_extras.py

from django import template

register = template.Library()

@register.filter(name='get_field_column_width')
def get_field_column_width(field_name):
    """
    Este filtro customizado retorna a largura da coluna Bootstrap (de 1 a 12)
    para um campo de formulário com base em seu nome. Isso permite criar layouts
    dinâmicos e organizados no template sem lógica complexa de 'if/else'.
    """
    # Mapeia nomes de campos específicos para larguras de coluna.
    # Útil para campos que devem ocupar a linha inteira (12) ou ter tamanhos específicos.
    width_map = {
        'nome_completo': 12,
        'email': 12,
        'profissao': 12,
        'logradouro': 8,
        'complemento': 8,
        'representante_legal': 7,
        'cpf_representante_legal': 5,
    }
    # Se o nome do campo estiver no mapa, retorna a largura definida.
    # Caso contrário, retorna um valor padrão de 6 (meia largura).
    return width_map.get(field_name, 6)

