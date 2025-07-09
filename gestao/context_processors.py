# gestao/context_processors.py

from .forms import ServicoForm, ClienteForm, TipoServicoForm, ContratoHonorariosForm, ServicoConcluirForm
from .models import EscritorioConfiguracao


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

def escritorio_context(request):
    """
    Torna os dados de configuração do escritório disponíveis em todos os templates.
    """
    # Usamos get_or_create para garantir que ele funcione mesmo se o objeto
    # ainda não tiver sido criado no banco pela primeira vez.
    config, created = EscritorioConfiguracao.objects.get_or_create(pk=1)
    return {
        'escritorio_config': config
    }
