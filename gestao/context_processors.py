# gestao/context_processors.py

from .forms import ServicoForm, ClienteForm, TipoServicoForm, ContratoHonorariosForm, ServicoConcluirForm


def global_forms_context(request):
    """
    Disponibiliza os formulários do modal de serviço em todas as páginas.
    """
    return {
        'form_servico': ServicoForm(),
        'form_cliente': ClienteForm(),
        'form_tipo_servico': TipoServicoForm(),
        'form_contrato': ContratoHonorariosForm(),
        'form_concluir': ServicoConcluirForm(), # <-- ADICIONE ESTA LINHA
    }