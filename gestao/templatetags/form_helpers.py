# gestao/templatetags/form_helpers.py

from django import template

# Cria uma instância de registro de tags e filtros do Django.
register = template.Library()


@register.filter(name='get_field_column_width')
def get_field_column_width(field_name):
    """
    Este filtro customizado retorna a largura da coluna do Bootstrap (de 1 a 12)
    com base no nome do campo do formulário. Isso permite que o layout do formulário
    seja definido de forma mais inteligente e dinâmica no template.

    Exemplo de uso no template:
    <div class="col-md-{{ field.name|get_field_column_width }}">
    """
    # Mapeamento de nomes de campo para larguras de coluna
    if field_name in ['tipo_pessoa', 'data_nascimento', 'estado_civil', 'cep', 'numero', 'estado']:
        return '4'
    if field_name in ['cpf_cnpj', 'telefone_principal', 'bairro', 'cidade']:
        return '6'
    if field_name in ['nome_completo', 'nacionalidade', 'profissao', 'logradouro', 'complemento', 'representante_legal',
                      'cpf_representante_legal']:
        return '8'

    # Valor padrão se o nome do campo não estiver no mapeamento
    return '12'

