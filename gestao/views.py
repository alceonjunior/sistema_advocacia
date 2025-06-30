# gestao/views.py

# ==============================================================================
# IMPORTS
# ==============================================================================

# Python Standard Library
import datetime
import itertools
import json
import unicodedata
from datetime import date
from decimal import Decimal
from operator import attrgetter, itemgetter

# Django Core
from django.apps import apps
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import (Q, Case, Count, DateField, DecimalField, F,
                              OuterRef, Subquery, Sum, Value, When)
from django.http import (Http404, HttpResponse, HttpResponseBadRequest,
                         JsonResponse)
from django.shortcuts import get_object_or_404, redirect, render
from django.template import Context, Template
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

# Local Application
from . import models
from .calculators import CalculadoraMonetaria
from .filters import ClienteFilter, ProcessoFilter, ServicoFilter
from .forms import (AreaProcessoForm, CalculoForm, ClienteForm,
                    ClienteModalForm, ContratoHonorariosForm,
                    CustomUserChangeForm, CustomUserCreationForm,
                    DocumentoForm, EscritorioConfiguracaoForm, IncidenteForm,
                    ModeloDocumentoForm, MovimentacaoForm,
                    MovimentacaoServicoForm, PagamentoForm,
                    ParteProcessoFormSet, ProcessoCreateForm, ProcessoForm,
                    RecursoForm, ServicoConcluirForm, ServicoEditForm,
                    ServicoForm, TipoAcaoForm, TipoServicoForm,
                    UsuarioPerfilForm)
from .models import (AreaProcesso, CalculoJudicial, Cliente, Documento,
                     EscritorioConfiguracao, Incidente, LancamentoFinanceiro,
                     ModeloDocumento, Movimentacao, MovimentacaoServico,
                     Pagamento, Processo, Recurso, Servico, TipoAcao,
                     TipoServico, UsuarioPerfil)
from .services import ServicoIndices
from .utils import data_por_extenso, valor_por_extenso

PERMISSOES_MAPEADAS = {
    "Processos": [
        {'codename': 'view_processo', 'label': 'Visualizar Processos'},
        {'codename': 'add_processo', 'label': 'Adicionar Processos'},
        {'codename': 'change_processo', 'label': 'Editar Processos'},
        {'codename': 'delete_processo', 'label': 'Excluir Processos'},
    ],
    "Clientes": [
        {'codename': 'view_cliente', 'label': 'Visualizar Clientes'},
        {'codename': 'add_cliente', 'label': 'Adicionar Clientes'},
        {'codename': 'change_cliente', 'label': 'Editar Clientes'},
        {'codename': 'delete_cliente', 'label': 'Excluir Clientes'},
    ],
    "Financeiro": [
        {'codename': 'view_lancamentofinanceiro', 'label': 'Visualizar Financeiro'},
        {'codename': 'add_contratohonorarios', 'label': 'Adicionar Contratos'},
        {'codename': 'add_pagamento', 'label': 'Registrar Pagamentos'},
        {'codename': 'delete_pagamento', 'label': 'Excluir Pagamentos'},
    ],
    "Configurações": [
        {'codename': 'view_escritorioconfiguracao', 'label': 'Visualizar Configurações'},
        {'codename': 'change_escritorioconfiguracao', 'label': 'Alterar Configurações do Escritório'},
        {'codename': 'view_user', 'label': 'Visualizar Usuários'},
        {'codename': 'add_user', 'label': 'Adicionar Usuários'},
        {'codename': 'change_user', 'label': 'Editar Usuários'},
        {'codename': 'delete_user', 'label': 'Excluir Usuários'},
    ]
}


# ==============================================================================
# SEÇÃO: VIEWS PRINCIPAIS E DASHBOARD
# ==============================================================================

@login_required
def dashboard(request):
    """
    Dashboard Analítico e de Gestão.
    Fornece uma visão completa das urgências, agenda e pulso do escritório.
    """
    hoje = timezone.now().date()
    proximos_30_dias = hoje + datetime.timedelta(days=30)
    status_aberto = ['PENDENTE', 'EM_ANDAMENTO']
    usuario = request.user
    agenda_completa = []

    # Otimização: Evitar chamadas desnecessárias ao banco de dados dentro do loop
    movimentacoes_qs = Movimentacao.objects.filter(
        responsavel=usuario, status__in=status_aberto
    ).select_related('processo__tipo_acao', 'tipo_movimentacao')

    tarefas_servico_qs = MovimentacaoServico.objects.filter(
        responsavel=usuario, status__in=status_aberto
    ).select_related('servico__cliente', 'servico__tipo_servico')

    def remove_accents(input_str):
        if not input_str: return ""
        nfkd_form = unicodedata.normalize('NFKD', input_str)
        return "".join([c for c in nfkd_form if not unicodedata.combining(c)])

    for m in movimentacoes_qs:
        if not m.tipo_movimentacao: continue  # Pula movimentações sem tipo

        tipo_mov_sem_acento = remove_accents(m.tipo_movimentacao.nome.lower())
        titulo_sem_acento = remove_accents(m.titulo.lower())
        is_audiencia = 'audiencia' in tipo_mov_sem_acento or 'audiencia' in titulo_sem_acento

        agenda_completa.append({
            'tipo': 'audiencia' if is_audiencia else 'prazo',
            'data': m.data_prazo_final,
            'hora': m.hora_prazo,
            'titulo': m.titulo,
            'url': reverse('gestao:detalhe_processo', args=[m.processo.pk]),
            'objeto_str': str(m.processo),
            'cliente': m.processo.get_polo_ativo_display(),
            'data_criacao': m.data_criacao
        })

    for ts in tarefas_servico_qs:
        agenda_completa.append({
            'tipo': 'tarefa_servico',
            'data': ts.prazo_final,
            'hora': None,
            'titulo': ts.titulo,
            'url': reverse('gestao:detalhe_servico', args=[ts.servico.pk]),
            'objeto_str': str(ts.servico),
            'cliente': ts.servico.cliente.nome_completo,
            'data_criacao': ts.data_criacao
        })

    # Acesso seguro a chaves de dicionário com .get()
    itens_para_hoje = sorted([item for item in agenda_completa if item.get('data') == hoje],
                             key=lambda x: (x.get('hora') is not None, x.get('hora')), reverse=True)
    itens_vencidos = sorted([item for item in agenda_completa if item.get('data') and item['data'] < hoje],
                            key=itemgetter('data'))
    proximas_audiencias = sorted(
        [item for item in agenda_completa if item['tipo'] == 'audiencia' and item.get('data') and item['data'] > hoje],
        key=itemgetter('data'))
    proximos_prazos = sorted([item for item in agenda_completa if
                              item['tipo'] == 'prazo' and item.get('data') and hoje < item['data'] <= proximos_30_dias],
                             key=itemgetter('data'))
    tarefas_pendentes = sorted(
        [item for item in agenda_completa if item['tipo'] == 'tarefa_servico' or not item.get('data')],
        key=itemgetter('data_criacao'), reverse=True)

    ultimas_movimentacoes = Movimentacao.objects.filter(processo__advogado_responsavel=usuario).order_by(
        '-data_criacao').select_related('processo')[:5]
    processos_ativos_count = Processo.objects.filter(advogado_responsavel=usuario, status_processo='ATIVO').count()
    servicos_ativos_count = Servico.objects.filter(responsavel=usuario, concluido=False).count()
    total_pendencias = len(
        [item for item in agenda_completa if item['tipo'] != 'audiencia' and item.get('data') is not None]) + len(
        tarefas_pendentes)

    context = {
        'processos_ativos_count': processos_ativos_count,
        'servicos_ativos_count': servicos_ativos_count,
        'total_pendencias': total_pendencias,
        'itens_para_hoje': itens_para_hoje,
        'itens_vencidos': itens_vencidos,
        'proximas_audiencias': proximas_audiencias,
        'proximos_prazos': proximos_prazos,
        'tarefas_pendentes': tarefas_pendentes,
        'ultimas_movimentacoes': ultimas_movimentacoes,
        'form_servico': ServicoForm(),
        'form_contrato': ContratoHonorariosForm(),
        'form_tipo_servico': TipoServicoForm(),
        'form_cliente': ClienteForm(),
        'hoje': hoje,
    }
    return render(request, 'gestao/dashboard.html', context)


# ==============================================================================
# SEÇÃO: VIEWS DE LISTAGEM E DETALHES
# ==============================================================================

@login_required
def lista_processos(request):
    """
    Exibe a lista de processos com filtros, estatísticas e anotação do próximo prazo.
    """
    base_queryset = Processo.objects.all() if request.user.is_superuser else Processo.objects.filter(
        Q(advogado_responsavel=request.user) | Q(advogados_envolvidos=request.user)
    ).distinct()

    proximo_prazo_subquery = Movimentacao.objects.filter(
        processo=OuterRef('pk'),
        status__in=['PENDENTE', 'EM_ANDAMENTO'],
        data_prazo_final__isnull=False
    ).order_by('data_prazo_final').values('data_prazo_final')[:1]

    # Otimização com select_related e prefetch_related
    annotated_queryset = base_queryset.annotate(
        proximo_prazo=Subquery(proximo_prazo_subquery, output_field=DateField())
    ).select_related('tipo_acao__area', 'advogado_responsavel').prefetch_related('partes__cliente')

    processo_filter = ProcessoFilter(request.GET, queryset=annotated_queryset)

    stats = {
        'total': base_queryset.count(),
        'ativos': base_queryset.filter(status_processo='ATIVO').count(),
        'suspensos': base_queryset.filter(status_processo='SUSPENSO').count(),
        'arquivados': base_queryset.filter(status_processo='ARQUIVADO').count(),
    }

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'gestao/partials/_lista_processos_partial.html', {
            'filter': processo_filter,
            'today': date.today()
        })

    context = {
        'filter': processo_filter,
        'stats': stats,
        'today': date.today()
    }
    return render(request, 'gestao/lista_processos.html', context)


@login_required
def detalhe_processo(request, pk):
    """
    View central para exibir todos os detalhes de um processo.
    """
    processo = get_object_or_404(
        Processo.objects.prefetch_related(
            'partes__cliente', 'documentos', 'movimentacoes__responsavel',
            'recursos', 'incidentes', 'advogados_envolvidos', 'lancamentos__pagamentos'
        ).select_related('tipo_acao__area', 'advogado_responsavel'),
        pk=pk
    )

    if request.method == 'POST':
        # [REINTEGRADO] Lógica da âncora para redirecionar o usuário à aba correta após submeter um formulário.
        redirect_anchor = ''
        if 'submit_movimentacao' in request.POST:
            form = MovimentacaoForm(request.POST)
            if form.is_valid():
                movimentacao = form.save(commit=False)
                movimentacao.processo = processo
                movimentacao.save()
                redirect_anchor = '#movimentacoes-pane'
        elif 'submit_recurso' in request.POST:
            form = RecursoForm(request.POST)
            if form.is_valid():
                novo_recurso = form.save(commit=False)
                novo_recurso.processo = processo
                novo_recurso.save()
                redirect_anchor = '#detalhes-adicionais-pane'
        elif 'submit_incidente' in request.POST:
            form = IncidenteForm(request.POST)
            if form.is_valid():
                novo_incidente = form.save(commit=False)
                novo_incidente.processo = processo
                novo_incidente.save()
                redirect_anchor = '#detalhes-adicionais-pane'

        redirect_url = f"{reverse('gestao:detalhe_processo', args=[pk])}{redirect_anchor}"
        return redirect(redirect_url)

    # --- LÓGICA GET ---
    movimentacoes = processo.movimentacoes.all().order_by('-data_criacao')
    today = timezone.now().date()
    for mov in movimentacoes:
        if mov.data_prazo_final:
            delta = mov.data_prazo_final - today
            mov.dias_restantes = delta.days
            if mov.dias_restantes < 0:
                mov.dias_vencidos = abs(mov.dias_restantes)
        else:
            mov.dias_restantes = None

    lancamentos_qs = processo.lancamentos.all()
    regulares_agrupados, inadimplentes_agrupados = _preparar_dados_financeiros(lancamentos_qs)

    valor_total_contratado_processo = lancamentos_qs.aggregate(total=Sum('valor'))['total'] or Decimal('0.00')
    total_recebido_processo = \
    Pagamento.objects.filter(lancamento__in=lancamentos_qs).aggregate(total=Sum('valor_pago'))['total'] or Decimal(
        '0.00')

    context = {
        'processo': processo,
        'movimentacoes': movimentacoes,
        'lancamentos_regulares_agrupados': regulares_agrupados,
        'lancamentos_inadimplentes_agrupados': inadimplentes_agrupados,
        'todos_modelos': ModeloDocumento.objects.all().order_by('titulo'),
        'form_movimentacao': MovimentacaoForm(initial={'responsavel': request.user}),
        'form_recurso': RecursoForm(),
        'form_incidente': IncidenteForm(),
        'form_pagamento': PagamentoForm(),
        'resumo_financeiro_processo': {
            'valor_total_contratado': valor_total_contratado_processo,
            'total_recebido': total_recebido_processo,
            'saldo_devedor': valor_total_contratado_processo - total_recebido_processo,
        }
    }

    response = render(request, 'gestao/detalhe_processo.html', context)
    # [REINTEGRADO] Controle de cache para garantir que os dados da página de detalhes estejam sempre atualizados.
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


@login_required
def detalhe_processo_partes_partial(request, processo_pk):
    """
    View auxiliar que retorna apenas o HTML do card de partes envolvidas.
    Utilizada para atualizar dinamicamente o card via AJAX após a edição das partes em um modal.
    """
    processo = get_object_or_404(Processo, pk=processo_pk)
    return render(request, 'gestao/partials/_card_partes_envolvidas.html', {'processo': processo})


@login_required
def lista_servicos(request):
    """Exibe um painel de controle aprimorado para os serviços extrajudiciais."""
    base_queryset = Servico.objects.select_related(
        'cliente', 'tipo_servico', 'responsavel'
    ).annotate(
        valor_total=Sum('lancamentos__valor', default=Value(Decimal('0.00'))),
        total_pago=Sum('lancamentos__pagamentos__valor_pago', default=Value(Decimal('0.00')))
    ).order_by('-data_inicio')

    servico_filter = ServicoFilter(request.GET, queryset=base_queryset)

    # Adiciona o cálculo da porcentagem paga aos resultados filtrados
    servicos_filtrados = servico_filter.qs
    for servico in servicos_filtrados:
        servico.percentual_pago = (servico.total_pago / servico.valor_total * 100) if servico.valor_total > 0 else 0

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'gestao/partials/_lista_servicos_partial.html',
                      {'servicos': servicos_filtrados, 'today': date.today()})

    context = {
        'filter': servico_filter,
        'servicos': servicos_filtrados,
    }
    return render(request, 'gestao/lista_servicos.html', context)


@login_required
def detalhe_servico(request, pk):
    """Exibe o painel de controle completo e funcional para um serviço extrajudicial."""
    servico = get_object_or_404(
        Servico.objects.prefetch_related(
            'movimentacoes__responsavel', 'lancamentos__pagamentos'
        ), pk=pk
    )

    if request.method == 'POST' and 'submit_movimentacao_servico' in request.POST:
        form_movimentacao = MovimentacaoServicoForm(request.POST)
        if form_movimentacao.is_valid():
            nova_movimentacao = form_movimentacao.save(commit=False)
            nova_movimentacao.servico = servico
            if not nova_movimentacao.responsavel:
                nova_movimentacao.responsavel = request.user
            nova_movimentacao.save()
            messages.success(request, 'Andamento adicionado com sucesso!')
            return redirect('gestao:detalhe_servico', pk=servico.pk)
    else:
        form_movimentacao = MovimentacaoServicoForm(initial={'responsavel': request.user})

    # --- Lógica Financeira ---
    lancamentos_qs = servico.lancamentos.all()
    regulares_agrupados, inadimplentes_agrupados = _preparar_dados_financeiros(lancamentos_qs)
    valor_total_contratado = lancamentos_qs.aggregate(total=Sum('valor'))['total'] or Decimal('0.00')
    total_pago = Pagamento.objects.filter(lancamento__in=lancamentos_qs).aggregate(total=Sum('valor_pago'))[
                     'total'] or Decimal('0.00')
    saldo_devedor = valor_total_contratado - total_pago
    percentual_pago = (total_pago / valor_total_contratado * 100) if valor_total_contratado > 0 else 0

    percentual_pago_visual = min(percentual_pago, Decimal('100.0'))
    percentual_devedor_visual = Decimal('100.0') - percentual_pago_visual

    # --- Lógica de Prazo Inteligente ---
    info_prazo = {}
    if servico.prazo and not servico.concluido:
        hoje = timezone.now().date()
        delta = servico.prazo - hoje
        if delta.days < 0:
            info_prazo = {'status': 'VENCIDO', 'texto': f"Vencido há {abs(delta.days)} dia(s)"}
        elif delta.days == 0:
            info_prazo = {'status': 'VENCE_HOJE', 'texto': "Vence Hoje!"}
        else:
            info_prazo = {'status': 'EM_DIA', 'texto': f"Restam {delta.days} dia(s)"}

    context = {
        'servico': servico,
        'movimentacoes': servico.movimentacoes.all().order_by('-data_atividade', '-data_criacao'),
        'form_movimentacao': form_movimentacao,
        'form_pagamento': PagamentoForm(),
        'today': timezone.now().date(),
        'info_prazo': info_prazo,
        'financeiro': {
            'valor_total': valor_total_contratado,
            'total_pago': total_pago,
            'saldo_devedor': saldo_devedor,
            'percentual_pago': round(percentual_pago, 2),
            'percentual_a_pagar': 100 - round(percentual_pago, 2),
            'percentual_pago_css': f"{percentual_pago_visual:.2f}".replace(",", "."),
            'percentual_devedor_css': f"{percentual_devedor_visual:.2f}".replace(",", "."),
            'form_concluir': ServicoConcluirForm(initial={'data_encerramento': timezone.now().date()}),
        },
        'lancamentos_regulares_agrupados': regulares_agrupados,
        'lancamentos_inadimplentes_agrupados': inadimplentes_agrupados
    }

    response = render(request, 'gestao/detalhe_servico.html', context)
    # [REINTEGRADO] Controle de cache para garantir que os dados da página de detalhes estejam sempre atualizados.
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


# ==============================================================================
# SEÇÃO: VIEWS DE CRIAÇÃO, EDIÇÃO E EXCLUSÃO (CRUD)
# ==============================================================================

@login_required
def adicionar_processo(request):
    """Exibe e processa o formulário para adicionar um novo processo e suas partes (via formset)."""
    if request.method == 'POST':
        form = ProcessoCreateForm(request.POST)
        formset = ParteProcessoFormSet(request.POST, prefix='partes')
        if form.is_valid() and formset.is_valid():
            processo = form.save()
            formset.instance = processo
            formset.save()
            return redirect('gestao:detalhe_processo', pk=processo.pk)
    else:
        form = ProcessoCreateForm()
        formset = ParteProcessoFormSet(prefix='partes')

    all_clients = Cliente.objects.all().order_by('nome_completo')
    clients_data = [{"id": cliente.pk, "text": cliente.nome_completo} for cliente in all_clients]

    context = {
        'form': form,
        'formset': formset,
        'all_clients_json': json.dumps(clients_data),
        'form_cliente_modal': ClienteModalForm(),
    }
    return render(request, 'gestao/adicionar_processo.html', context)


@login_required
def editar_processo(request, pk):
    """Exibe e processa o formulário para editar os dados gerais de um processo existente."""
    processo = get_object_or_404(Processo, pk=pk)
    if request.method == 'POST':
        form = ProcessoForm(request.POST, instance=processo)
        if form.is_valid():
            form.save()
            return redirect('gestao:detalhe_processo', pk=processo.pk)
    else:
        form = ProcessoForm(instance=processo)
    return render(request, 'gestao/editar_processo.html', {'form': form, 'processo': processo})


@login_required
def editar_servico(request, pk):
    """Exibe e processa o formulário para editar um serviço extrajudicial."""
    servico = get_object_or_404(Servico, pk=pk)
    if request.method == 'POST':
        form = ServicoEditForm(request.POST, instance=servico)
        if form.is_valid():
            form.save()
            return redirect('gestao:detalhe_servico', pk=servico.pk)
    else:
        form = ServicoEditForm(instance=servico)
    return render(request, 'gestao/editar_servico.html', {'form': form, 'servico': servico})


@login_required
def gerenciar_partes(request, processo_pk):
    """
    Gerencia as partes (autores, réus) de um processo, otimizada para AJAX.
    """
    processo = get_object_or_404(Processo.objects.prefetch_related('partes__cliente'), pk=processo_pk)

    if request.method == 'POST':
        formset = ParteProcessoFormSet(request.POST, instance=processo, prefix='partes')
        if formset.is_valid():
            formset.save()
            return JsonResponse({'success': True})
        else:
            context = {'processo': processo, 'formset': formset, 'is_modal': True}
            form_html = render_to_string('gestao/gerenciar_partes.html', context, request=request)
            return JsonResponse({'success': False, 'form_html': form_html}, status=400)

    formset = ParteProcessoFormSet(instance=processo, prefix='partes')
    context = {
        'processo': processo,
        'formset': formset,
        'is_modal': True
    }
    return render(request, 'gestao/gerenciar_partes.html', context)


@require_POST
@login_required
def concluir_movimentacao(request, pk):
    """Marca uma movimentação de processo como 'CONCLUÍDA'."""
    movimentacao = get_object_or_404(Movimentacao, pk=pk)
    movimentacao.status = 'CONCLUIDA'
    movimentacao.save()
    redirect_url = reverse('gestao:detalhe_processo', kwargs={'pk': movimentacao.processo.pk}) + '#movimentacoes-pane'
    return redirect(redirect_url)


@login_required
def editar_movimentacao(request, pk):
    """Exibe e processa o formulário para editar uma movimentação de processo."""
    movimentacao = get_object_or_404(Movimentacao, pk=pk)
    if request.method == 'POST':
        form = MovimentacaoForm(request.POST, instance=movimentacao)
        if form.is_valid():
            form.save()
            return redirect('gestao:detalhe_processo', pk=movimentacao.processo.pk)
    else:
        form = MovimentacaoForm(instance=movimentacao)
    context = {'form': form, 'movimentacao': movimentacao}
    return render(request, 'gestao/editar_movimentacao.html', context)


@require_POST
@login_required
def excluir_movimentacao(request, pk):
    """Exclui uma movimentação de processo."""
    movimentacao = get_object_or_404(Movimentacao, pk=pk)
    processo_pk = movimentacao.processo.pk
    movimentacao.delete()
    return redirect('gestao:detalhe_processo', pk=processo_pk)


@login_required
def editar_movimentacao_servico(request, pk):
    """Exibe e processa o formulário para editar uma movimentação de serviço."""
    movimentacao = get_object_or_404(MovimentacaoServico, pk=pk)
    form = MovimentacaoServicoForm(request.POST or None, instance=movimentacao)
    if form.is_valid():
        form.save()
        return redirect('gestao:detalhe_servico', pk=movimentacao.servico.pk)
    return render(request, 'gestao/editar_movimentacao_servico.html', {'form': form, 'movimentacao': movimentacao})


@require_POST
@login_required
def excluir_movimentacao_servico(request, pk):
    """Exclui uma movimentação de serviço."""
    movimentacao = get_object_or_404(MovimentacaoServico, pk=pk)
    servico_pk = movimentacao.servico.pk
    movimentacao.delete()
    return redirect('gestao:detalhe_servico', pk=servico_pk)


@require_POST
@login_required
def concluir_servico(request, pk):
    """Marca um serviço como concluído."""
    servico = get_object_or_404(Servico, pk=pk)
    form = ServicoConcluirForm(request.POST, instance=servico)
    if form.is_valid():
        servico_concluido = form.save(commit=False)
        servico_concluido.concluido = True
        if not servico_concluido.data_encerramento:
            servico_concluido.data_encerramento = timezone.now().date()
        servico_concluido.save()
    return redirect('gestao:detalhe_servico', pk=pk)


@require_POST
@login_required
def concluir_movimentacao_servico(request, pk):
    """Marca uma movimentação de serviço como 'CONCLUIDA'."""
    movimentacao = get_object_or_404(MovimentacaoServico, pk=pk)
    movimentacao.status = 'CONCLUIDA'
    movimentacao.save()
    return redirect('gestao:detalhe_servico', pk=movimentacao.servico.pk)


# ==============================================================================
# SEÇÃO: VIEWS DE DOCUMENTOS E MODELOS
# ==============================================================================

VARIAVEIS_DOCUMENTO = {
    'Cliente': [
        {'label': 'Nome Completo', 'valor': '{{ cliente.nome_completo }}'},
        {'label': 'CPF/CNPJ', 'valor': '{{ cliente.cpf_cnpj }}'},
    ],
    'Processo': [
        {'label': 'Número do Processo', 'valor': '{{ processo.numero_processo }}'},
        {'label': 'Vara/Comarca', 'valor': '{{ processo.vara_comarca_orgao }}'},
    ],
    'Geral': [{'label': 'Data Atual por Extenso', 'valor': '{{ data_extenso }}'}, ]
}


@login_required
def lista_modelos(request):
    """Exibe a lista de todos os modelos de documentos disponíveis."""
    modelos = ModeloDocumento.objects.all().order_by('titulo')
    return render(request, 'gestao/modelos/lista_modelos.html', {'modelos': modelos})


@login_required
def adicionar_modelo(request):
    """Exibe e processa o formulário para adicionar um novo modelo de documento."""
    if request.method == 'POST':
        form = ModeloDocumentoForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('gestao:lista_modelos')
    else:
        form = ModeloDocumentoForm()
    context = {'form': form, 'titulo_pagina': 'Adicionar Novo Modelo', 'variaveis': VARIAVEIS_DOCUMENTO}
    return render(request, 'gestao/modelos/form_modelo.html', context)


@login_required
def editar_modelo(request, pk):
    """Exibe e processa o formulário para editar um modelo de documento existente."""
    modelo = get_object_or_404(ModeloDocumento, pk=pk)
    if request.method == 'POST':
        form = ModeloDocumentoForm(request.POST, instance=modelo)
        if form.is_valid():
            form.save()
            return redirect('gestao:lista_modelos')
    else:
        form = ModeloDocumentoForm(instance=modelo)
    context = {'form': form, 'modelo': modelo, 'titulo_pagina': 'Editar Modelo', 'variaveis': VARIAVEIS_DOCUMENTO}
    return render(request, 'gestao/modelos/form_modelo.html', context)


@require_POST
@login_required
def excluir_modelo(request, pk):
    """Exclui um modelo de documento."""
    modelo = get_object_or_404(ModeloDocumento, pk=pk)
    modelo.delete()
    return redirect('gestao:lista_modelos')


@login_required
def gerar_documento(request, processo_pk, modelo_pk):
    """
    Gera um novo documento a partir de um modelo para um processo.
    """
    processo = get_object_or_404(Processo, pk=processo_pk)
    modelo = get_object_or_404(ModeloDocumento, pk=modelo_pk)

    cliente_principal = None
    parte_autora = processo.partes.filter(tipo_participacao='AUTOR').first()
    if parte_autora:
        cliente_principal = parte_autora.cliente

    contexto_variaveis = Context({
        'cliente': cliente_principal,
        'processo': processo,
        'data_extenso': data_por_extenso(date.today()),
        'cidade_escritorio': EscritorioConfiguracao.objects.first().cidade if EscritorioConfiguracao.objects.first() else ''
    })

    conteudo_renderizado = Template(modelo.conteudo).render(contexto_variaveis)
    titulo_sugerido = f"{modelo.titulo} - {cliente_principal.nome_completo if cliente_principal else 'Processo'}"

    if request.method == 'POST':
        form = DocumentoForm(request.POST, request.FILES)
        if form.is_valid():
            documento = form.save(commit=False)
            documento.processo = processo
            documento.modelo_origem = modelo
            documento.save()
            return redirect('gestao:detalhe_processo', pk=processo.pk)
    else:
        form = DocumentoForm(initial={'titulo': titulo_sugerido, 'conteudo': conteudo_renderizado})

    context = {
        'form': form,
        'processo': processo,
        'titulo_pagina': 'Gerar Novo Documento'
    }
    return render(request, 'gestao/documentos/form_documento.html', context)


@login_required
def editar_documento(request, pk):
    """Exibe e processa a edição de um documento já existente."""
    documento = get_object_or_404(Documento, pk=pk)
    if request.method == 'POST':
        form = DocumentoForm(request.POST, request.FILES, instance=documento)
        if form.is_valid():
            form.save()
            return redirect('gestao:detalhe_processo', pk=documento.processo.pk)
    else:
        form = DocumentoForm(instance=documento)

    context = {
        'form': form,
        'processo': documento.processo,
        'titulo_pagina': 'Editar Documento'
    }
    return render(request, 'gestao/documentos/form_documento.html', context)


# ==============================================================================
# SEÇÃO: VIEWS FINANCEIRAS E DE PAGAMENTO
# ==============================================================================

@login_required
def adicionar_contrato(request, processo_pk=None, servico_pk=None):
    """Adiciona um contrato de honorários a um processo ou a um serviço."""
    parent_object = None
    # [REINTEGRADO] Lógica de âncora para redirecionar à aba financeira após a criação do contrato.
    redirect_url_with_hash = ""

    if processo_pk:
        parent_object = get_object_or_404(Processo.objects.prefetch_related('partes__cliente'), pk=processo_pk)
        redirect_url_with_hash = f"{parent_object.get_absolute_url()}#financeiro-pane"
    elif servico_pk:
        parent_object = get_object_or_404(Servico, pk=servico_pk)
        redirect_url_with_hash = f"{parent_object.get_absolute_url()}#financeiro-tab-pane"

    if not parent_object:
        return redirect('gestao:dashboard')

    if request.method == 'POST':
        form = ContratoHonorariosForm(request.POST)
        if form.is_valid():
            contrato = form.save(commit=False)
            contrato.content_object = parent_object

            if isinstance(parent_object, Processo):
                autor_principal = parent_object.partes.filter(tipo_participacao='AUTOR').first()
                if not autor_principal:
                    form.add_error(None, "Um processo deve ter um cliente no Polo Ativo para criar um contrato.")
                else:
                    contrato.cliente = autor_principal.cliente
            elif isinstance(parent_object, Servico):
                contrato.cliente = parent_object.cliente

            if not form.errors:
                contrato.save()
                return redirect(redirect_url_with_hash)
    else:
        form = ContratoHonorariosForm()

    context = {
        'form': form,
        'parent_object': parent_object,
    }
    return render(request, 'gestao/adicionar_contrato.html', context)


@require_POST
@login_required
def adicionar_pagamento(request, pk):
    """Adiciona um pagamento a um lançamento financeiro."""
    lancamento = get_object_or_404(LancamentoFinanceiro.objects.select_related('processo', 'servico'), pk=pk)
    form = PagamentoForm(request.POST)

    if form.is_valid():
        pagamento = form.save(commit=False)
        pagamento.lancamento = lancamento
        pagamento.save()
        success = True
        errors = None
    else:
        success = False
        errors = form.errors.as_json()

    redirect_url = ""
    tab_fragment = ""
    if lancamento.processo:
        redirect_url = reverse('gestao:detalhe_processo', kwargs={'pk': lancamento.processo.pk})
        tab_fragment = '#financeiro-pane'
    elif lancamento.servico:
        redirect_url = reverse('gestao:detalhe_servico', kwargs={'pk': lancamento.servico.pk})
        tab_fragment = '#financeiro-tab-pane'

    return JsonResponse({
        'success': success,
        'redirect_url': f"{redirect_url}{tab_fragment}",
        'errors': errors
    })


@require_POST
@login_required
def editar_pagamento(request, pk):
    """Edita um pagamento existente."""
    pagamento = get_object_or_404(Pagamento.objects.select_related('lancamento__processo', 'lancamento__servico'),
                                  pk=pk)
    form = PagamentoForm(request.POST, instance=pagamento)

    if form.is_valid():
        form.save()
        success = True
        errors = None
    else:
        success = False
        errors = form.errors.as_json()

    redirect_url = ""
    tab_fragment = ""
    if pagamento.lancamento.processo:
        redirect_url = reverse('gestao:detalhe_processo', kwargs={'pk': pagamento.lancamento.processo.pk})
        tab_fragment = '#financeiro-pane'
    elif pagamento.lancamento.servico:
        redirect_url = reverse('gestao:detalhe_servico', kwargs={'pk': pagamento.lancamento.servico.pk})
        tab_fragment = '#financeiro-tab-pane'

    return JsonResponse({
        'success': success,
        'redirect_url': f"{redirect_url}{tab_fragment}",
        'errors': errors
    })


@require_POST
@login_required
def excluir_pagamento(request, pk):
    """Exclui um pagamento existente."""
    pagamento = get_object_or_404(Pagamento.objects.select_related('lancamento__processo', 'lancamento__servico'),
                                  pk=pk)

    redirect_url = ""
    tab_fragment = ""
    if pagamento.lancamento.processo:
        redirect_url = reverse('gestao:detalhe_processo', kwargs={'pk': pagamento.lancamento.processo.pk})
        tab_fragment = '#financeiro-pane'
    elif pagamento.lancamento.servico:
        redirect_url = reverse('gestao:detalhe_servico', kwargs={'pk': pagamento.lancamento.servico.pk})
        tab_fragment = '#financeiro-tab-pane'

    pagamento.delete()
    return JsonResponse({
        'success': True,
        'redirect_url': f"{redirect_url}{tab_fragment}"
    })


@login_required
def imprimir_recibo(request, pagamento_pk):
    """Gera uma página de recibo de pagamento formatada para impressão."""
    pagamento = get_object_or_404(
        Pagamento.objects.select_related(
            'lancamento', 'lancamento__cliente', 'lancamento__processo', 'lancamento__servico'
        ),
        pk=pagamento_pk
    )

    # Lógica para obter dados do escritório do banco de dados, tornando o recibo dinâmico.
    escritorio = EscritorioConfiguracao.objects.first()

    context = {
        'pagamento': pagamento,
        'lancamento': pagamento.lancamento,
        'processo': pagamento.lancamento.processo,
        'servico': pagamento.lancamento.servico,
        'cliente': pagamento.lancamento.cliente,
        'data_emissao': timezone.now(),
        'valor_extenso': valor_por_extenso(pagamento.valor_pago),
        'escritorio': escritorio
    }

    return render(request, 'gestao/recibo_pagamento.html', context)


# ==============================================================================
# SEÇÃO: VIEWS DE CLIENTES
# ==============================================================================

@login_required
def lista_clientes(request):
    """Exibe a lista de clientes com filtros, ordenação e estatísticas."""
    base_queryset = Cliente.objects.annotate(
        processos_ativos_count=Count('participacoes__processo',
                                     filter=Q(participacoes__processo__status_processo='ATIVO'), distinct=True),
        servicos_ativos_count=Count('servicos', filter=Q(servicos__concluido=False), distinct=True)
    )
    cliente_filter = ClienteFilter(request.GET, queryset=base_queryset)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'gestao/partials/_lista_clientes_partial.html', {'filter': cliente_filter})

    stats = {
        'total': cliente_filter.qs.count(),
        'com_processos_ativos': cliente_filter.qs.filter(processos_ativos_count__gt=0).count(),
        'com_servicos_ativos': cliente_filter.qs.filter(servicos_ativos_count__gt=0).count(),
        'total_ativos': cliente_filter.qs.filter(
            Q(processos_ativos_count__gt=0) | Q(servicos_ativos_count__gt=0)).distinct().count(),
    }
    context = {
        'filter': cliente_filter,
        'stats': stats,
        'form': ClienteForm()
    }
    return render(request, 'gestao/lista_clientes.html', context)


@login_required
def detalhe_cliente(request, pk):
    """Exibe a página de detalhes de um cliente e permite a edição dos seus dados."""
    cliente = get_object_or_404(Cliente, pk=pk)

    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            return redirect('gestao:detalhe_cliente', pk=cliente.pk)
    else:
        form = ClienteForm(instance=cliente)

    context = {
        'cliente': cliente,
        'form': form
    }
    return render(request, 'gestao/detalhe_cliente.html', context)


@login_required
def adicionar_cliente_page(request):
    """Renderiza e processa a página completa de cadastro de um novo cliente."""
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            cliente = form.save()
            messages.success(request, f'Cliente "{cliente.nome_completo}" cadastrado com sucesso!')
            return redirect('gestao:detalhe_cliente', pk=cliente.pk)
        else:
            messages.error(request, 'Não foi possível salvar o cliente. Por favor, corrija os erros abaixo.')
    else:
        form = ClienteForm()

    context = {
        'form': form,
        'titulo_pagina': 'Cadastrar Novo Cliente'
    }
    return render(request, 'gestao/adicionar_cliente.html', context)


@require_POST
@login_required
def salvar_cliente(request, pk=None):
    """View unificada para salvar um cliente (criação ou edição) via AJAX."""
    instance = get_object_or_404(Cliente, pk=pk) if pk else None
    form = ClienteForm(request.POST, instance=instance)
    if form.is_valid():
        cliente = form.save()
        return JsonResponse({
            'status': 'success',
            'message': 'Cliente salvo com sucesso!',
            'cliente': {'pk': cliente.pk, 'nome': str(cliente)}
        })
    return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)


@login_required
def get_cliente_json(request, pk):
    """ Retorna os dados de um cliente em formato JSON para popular formulários."""
    cliente = get_object_or_404(Cliente, pk=pk)
    data_nascimento_fmt = cliente.data_nascimento.strftime('%Y-%m-%d') if cliente.data_nascimento else None
    data = {
        'nome_completo': cliente.nome_completo, 'tipo_pessoa': cliente.tipo_pessoa,
        'cpf_cnpj': cliente.cpf_cnpj, 'email': cliente.email, 'telefone_principal': cliente.telefone_principal,
        'data_nascimento': data_nascimento_fmt, 'nacionalidade': cliente.nacionalidade,
        'estado_civil': cliente.estado_civil, 'profissao': cliente.profissao,
        'cep': cliente.cep, 'logradouro': cliente.logradouro, 'numero': cliente.numero,
        'complemento': cliente.complemento, 'bairro': cliente.bairro, 'cidade': cliente.cidade,
        'estado': cliente.estado, 'representante_legal': cliente.representante_legal,
        'cpf_representante_legal': cliente.cpf_representante_legal,
    }
    return JsonResponse(data)


@require_POST
@login_required
def excluir_cliente(request, pk):
    """ Exclui um cliente, se ele não tiver casos ativos."""
    cliente = get_object_or_404(Cliente, pk=pk)
    # Verificação explícita em vez de try/except para mais clareza.
    if cliente.participacoes.exists() or cliente.servicos.exists():
        return JsonResponse({'status': 'error',
                             'message': 'Não é possível excluir o cliente pois ele está vinculado a processos ou serviços.'},
                            status=400)
    try:
        cliente.delete()
        return JsonResponse({'status': 'success', 'message': 'Cliente excluído com sucesso!'})
    except Exception as e:
        return JsonResponse({'status': 'error',
                             'message': f'Ocorreu um erro inesperado: {str(e)}'},
                            status=500)


# ==============================================================================
# SEÇÃO: VIEWS DE MODAL (AJAX) E SERVIÇOS
# ==============================================================================

@require_POST
@login_required
def adicionar_cliente_modal(request):
    """Processa a adição de um novo Cliente via modal e retorna JSON."""
    form = ClienteModalForm(request.POST)
    if form.is_valid():
        cliente = form.save()
        return JsonResponse({
            'status': 'success',
            'pk': cliente.pk,
            'nome': str(cliente)
        })
    return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)


@require_POST
@login_required
def adicionar_tipo_servico_modal(request):
    """Processa a adição de um novo Tipo de Serviço via modal e retorna JSON."""
    form = TipoServicoForm(request.POST)
    if form.is_valid():
        tipo_servico = form.save()
        return JsonResponse({
            'status': 'success',
            'pk': tipo_servico.pk,
            'nome': str(tipo_servico)
        })
    return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)


@login_required
def adicionar_servico_view(request):
    """Renderiza a página com o assistente para adicionar um novo serviço."""
    context = {
        'form_servico': ServicoForm(),
        'form_contrato': ContratoHonorariosForm(),
        'form_cliente_modal': ClienteModalForm(),
        'form_tipo_servico': TipoServicoForm(),
    }
    return render(request, 'gestao/adicionar_servico.html', context)


@require_POST
@login_required
def salvar_servico_ajax(request):
    """Processa os dados enviados via AJAX pelo wizard de cadastro de serviço."""
    try:
        data = json.loads(request.body)
        servico_data = data.get('servico', {})
        contrato_data = data.get('contrato', {})
        has_contrato = data.get('has_contrato', False)

        if not servico_data.get('responsavel'):
            servico_data['responsavel'] = request.user.pk

        form_servico = ServicoForm(servico_data)
        if form_servico.is_valid():
            servico = form_servico.save()

            if has_contrato:
                # [REINTEGRADO] Validação explícita para garantir dados mínimos do contrato na criação do serviço.
                # Nota: Os nomes das chaves 'valor_pagamento_fixo' e 'data_primeiro_vencimento' devem corresponder
                # ao que o JavaScript envia no objeto 'contrato_data'.
                if not contrato_data.get('valor_pagamento_fixo') or not contrato_data.get('data_primeiro_vencimento'):
                    servico.delete()  # Desfaz a criação do serviço se o contrato for inválido
                    return JsonResponse({'status': 'error', 'errors': {'Contrato': [
                        'Para adicionar um contrato, o Valor da Parcela e a Data do Primeiro Vencimento são obrigatórios.']}},
                                        status=400)

                form_contrato = ContratoHonorariosForm(contrato_data)
                if form_contrato.is_valid():
                    contrato = form_contrato.save(commit=False)
                    contrato.content_object = servico
                    contrato.cliente = servico.cliente
                    contrato.save()
                else:
                    servico.delete()  # Desfaz a criação do serviço se o formulário do contrato for inválido
                    return JsonResponse({'status': 'error', 'errors': form_contrato.errors}, status=400)

            return JsonResponse({'status': 'success', 'redirect_url': servico.get_absolute_url()})
        else:
            return JsonResponse({'status': 'error', 'errors': form_servico.errors}, status=400)

    except json.JSONDecodeError:
        return HttpResponseBadRequest('Requisição com JSON inválido.')
    except Exception as e:
        return JsonResponse({'status': 'error', 'errors': {'Erro Geral': [f'Ocorreu um erro inesperado: {str(e)}']}},
                            status=500)


# ==============================================================================
# SEÇÃO: VIEWS DE CÁLCULO JUDICIAL
# ==============================================================================

def _perform_calculation(dados):
    """
    Função auxiliar privada para encapsular a lógica de cálculo.
    """
    try:
        indice_selecionado_display = dict(CalculoForm.INDICE_CHOICES).get(dados['indice'])
        servico_indices = ServicoIndices()
        indices_periodo = servico_indices.get_indices_por_periodo(
            dados['indice'], dados['data_inicio'], dados['data_fim']
        )
        calculadora = CalculadoraMonetaria(
            valor_original=dados['valor_original'], data_inicio=dados['data_inicio'],
            data_fim=dados['data_fim'], indices_periodo=indices_periodo
        )
        resultado = calculadora.calcular(
            juros_taxa=dados.get('juros_taxa') or 0, juros_tipo=dados.get('juros_tipo', 'SIMPLES'),
            juros_periodo=dados.get('juros_periodo', 'MENSAL'), juros_data_inicio=dados.get('juros_data_inicio'),
            juros_data_fim=dados.get('juros_data_fim'), correcao_pro_rata=dados.get('correcao_pro_rata', False),
            multa_taxa=dados.get('multa_percentual') or 0, multa_sobre_juros=dados.get('multa_sobre_juros', False),
            honorarios_taxa=dados.get('honorarios_percentual') or 0
        )
        resultado['resumo']['indice_display_name'] = indice_selecionado_display
        if not dados.get('gerar_memorial'):
            resultado['memorial'] = None
        return resultado, None
    except Exception as e:
        return None, f"Ocorreu um erro inesperado durante o cálculo: {e}"


@login_required
def realizar_calculo(request, processo_pk, calculo_pk=None):
    """
    View central para a ferramenta de cálculo judicial.
    Usa a versão refatorada e mais limpa.
    """
    processo = get_object_or_404(Processo, pk=processo_pk)

    if request.method == 'POST':
        form = CalculoForm(request.POST)
        if form.is_valid():
            dados_calculo = form.cleaned_data
            resultado, erro = _perform_calculation(dados_calculo)

            if resultado and not erro:
                memoria_calculo_json = []
                if resultado.get('memorial'):
                    memoria_calculo_json = [
                        {'termo_inicial': l['termo_inicial'].isoformat(), 'termo_final': l['termo_final'].isoformat(),
                         'variacao_periodo': str(l['variacao_periodo']),
                         'valor_atualizado_mes': str(l['valor_atualizado_mes'])} for l in resultado['memorial']]

                # Versão limpa de salvar o cálculo
                novo_calculo_salvo = CalculoJudicial.objects.create(
                    processo=processo, responsavel=request.user, descricao=dados_calculo['descricao'],
                    valor_original=dados_calculo['valor_original'], data_inicio_correcao=dados_calculo['data_inicio'],
                    data_fim_correcao=dados_calculo['data_fim'], indice_correcao=dados_calculo['indice'],
                    correcao_pro_rata=dados_calculo.get('correcao_pro_rata', False),
                    juros_percentual=dados_calculo.get('juros_taxa'), juros_tipo=dados_calculo.get('juros_tipo'),
                    juros_periodo=dados_calculo.get('juros_periodo'),
                    juros_data_inicio=dados_calculo.get('juros_data_inicio'),
                    juros_data_fim=dados_calculo.get('juros_data_fim'),
                    multa_percentual=dados_calculo.get('multa_percentual'),
                    multa_sobre_juros=dados_calculo.get('multa_sobre_juros', False),
                    honorarios_percentual=dados_calculo.get('honorarios_percentual'),
                    valor_corrigido=resultado['resumo']['valor_corrigido_total'],
                    valor_final=resultado['resumo']['valor_final'], memoria_calculo=memoria_calculo_json
                )
                return redirect('gestao:carregar_calculo', processo_pk=processo.pk, calculo_pk=novo_calculo_salvo.pk)

        contexto = {
            'processo': processo,
            'calculos_salvos': processo.calculos.all().order_by('-data_calculo'),
            'form': form,
            'resultado': None,
            'erro': 'Formulário inválido. Verifique os campos marcados.',
        }
        return render(request, 'gestao/calculo_judicial.html', contexto)

    # --- LÓGICA GET ---
    form = CalculoForm(initial=request.session.pop('form_initial_data', None))
    resultado_final, erro_final, calculo_carregado = None, None, None

    if calculo_pk:
        calculo_carregado = get_object_or_404(CalculoJudicial, pk=calculo_pk, processo=processo)
        # Versão limpa de popular o formulário
        form_data = {
            'descricao': calculo_carregado.descricao, 'valor_original': calculo_carregado.valor_original,
            'data_inicio': calculo_carregado.data_inicio_correcao, 'data_fim': calculo_carregado.data_fim_correcao,
            'indice': calculo_carregado.indice_correcao, 'correcao_pro_rata': calculo_carregado.correcao_pro_rata,
            'juros_taxa': calculo_carregado.juros_percentual, 'juros_tipo': calculo_carregado.juros_tipo,
            'juros_periodo': calculo_carregado.juros_periodo,
            'juros_data_inicio': calculo_carregado.juros_data_inicio,
            'juros_data_fim': calculo_carregado.juros_data_fim,
            'multa_percentual': calculo_carregado.multa_percentual,
            'multa_sobre_juros': calculo_carregado.multa_sobre_juros,
            'honorarios_percentual': calculo_carregado.honorarios_percentual,
            'gerar_memorial': True,
        }
        form = CalculoForm(initial=form_data)
        resultado_final, erro_final = _perform_calculation(form_data)

    contexto = {
        'processo': processo,
        'calculos_salvos': processo.calculos.all().order_by('-data_calculo'),
        'form': form,
        'calculo_carregado': calculo_carregado,
        'resultado': resultado_final,
        'erro': erro_final,
    }
    return render(request, 'gestao/calculo_judicial.html', contexto)


@login_required
@require_POST
def atualizar_calculo_hoje(request, calculo_pk):
    """Prepara os dados de um cálculo existente para serem recalculados com a data atual."""
    calculo = get_object_or_404(CalculoJudicial, pk=calculo_pk)
    form_data = {
        'descricao': f"Cópia de '{calculo.descricao}' (Atualizado)",
        'valor_original': str(calculo.valor_original),
        'data_inicio': calculo.data_inicio_correcao.isoformat(),
        'data_fim': date.today().isoformat(),
        'indice': calculo.indice_correcao,
        'correcao_pro_rata': calculo.correcao_pro_rata,
        'juros_taxa': str(calculo.juros_percentual or ''),
        'juros_tipo': calculo.juros_tipo,
        'juros_periodo': calculo.juros_periodo,
        'juros_data_inicio': calculo.juros_data_inicio.isoformat() if calculo.juros_data_inicio else None,
        'juros_data_fim': calculo.juros_data_fim.isoformat() if calculo.juros_data_fim else None,
        'multa_percentual': str(calculo.multa_percentual or ''),
        'multa_sobre_juros': calculo.multa_sobre_juros,
        'honorarios_percentual': str(calculo.honorarios_percentual or ''),
        'gerar_memorial': True,
    }
    request.session['form_initial_data'] = form_data
    return redirect('gestao:novo_calculo', processo_pk=calculo.processo.pk)


@require_POST
@login_required
def excluir_calculo(request, calculo_pk):
    """Exclui um cálculo judicial específico."""
    calculo = get_object_or_404(CalculoJudicial, pk=calculo_pk)
    processo_pk = calculo.processo.pk
    calculo.delete()
    return redirect('gestao:pagina_de_calculos', processo_pk=processo_pk)


@require_POST
@login_required
def excluir_todos_calculos(request, processo_pk):
    """Exclui TODOS os cálculos judiciais associados a um processo."""
    processo = get_object_or_404(Processo, pk=processo_pk)
    processo.calculos.all().delete()
    return redirect('gestao:pagina_de_calculos', processo_pk=processo_pk)


# ==============================================================================
# SEÇÃO: VIEWS DE ESTADO (ATIVO/ARQUIVADO)
# ==============================================================================

@require_POST
@login_required
def arquivar_processo(request, pk):
    """Altera o status de um processo para 'ARQUIVADO'."""
    processo = get_object_or_404(Processo, pk=pk)
    processo.status_processo = 'ARQUIVADO'
    processo.save()
    return redirect('gestao:lista_processos')


@require_POST
@login_required
def desarquivar_processo(request, pk):
    """Altera o status de um processo de 'ARQUIVADO' de volta para 'ATIVO'."""
    processo = get_object_or_404(Processo, pk=pk)
    if processo.status_processo == 'ARQUIVADO':
        processo.status_processo = 'ATIVO'
        processo.save()
    return redirect('gestao:detalhe_processo', pk=pk)


# ==============================================================================
# SEÇÃO: VIEWS PARCIAIS (AJAX)
# ==============================================================================

def _preparar_dados_financeiros(lancamentos_qs):
    """
    Separa os lançamentos em regulares e inadimplentes, e agrupa ambos por ano/mês.
    Versão refatorada e mais concisa.
    """
    lancamentos_regulares = [lanc for lanc in lancamentos_qs if lanc.status != 'ATRASADO']
    lancamentos_inadimplentes = [lanc for lanc in lancamentos_qs if lanc.status == 'ATRASADO']

    def _agrupar(lancamentos):
        sorted_lancamentos = sorted(lancamentos, key=attrgetter('data_vencimento'))
        return {
            year: {
                month: list(items)
                for month, items in
                itertools.groupby(year_items, key=lambda l: l.data_vencimento.strftime('%B').capitalize())
            }
            for year, year_items in itertools.groupby(sorted_lancamentos, key=attrgetter('data_vencimento.year'))
        }

    return _agrupar(lancamentos_regulares), _agrupar(lancamentos_inadimplentes)


@login_required
def atualizar_tabela_financeira_partial(request, parent_pk, parent_type):
    """
    Retorna o HTML parcial da tabela financeira para um processo ou serviço.
    """
    try:
        if parent_type == 'processo':
            parent_object = get_object_or_404(Processo.objects.prefetch_related('lancamentos__pagamentos'),
                                              pk=parent_pk)
        elif parent_type == 'servico':
            parent_object = get_object_or_404(Servico.objects.prefetch_related('lancamentos__pagamentos'), pk=parent_pk)
        else:
            return JsonResponse({'error': 'Tipo de objeto pai inválido.'}, status=400)

        lancamentos_qs = parent_object.lancamentos.all()
        regulares_agrupados, inadimplentes_agrupados = _preparar_dados_financeiros(lancamentos_qs)

        html_content = render_to_string('gestao/partials/_tabela_financeira.html', {
            'lancamentos_regulares_agrupados': regulares_agrupados,
            'lancamentos_inadimplentes_agrupados': inadimplentes_agrupados,
            'processo': parent_object if parent_type == 'processo' else None,
            'servico': parent_object if parent_type == 'servico' else None,
            'form_pagamento': PagamentoForm(),
        }, request=request)

        return JsonResponse({'html': html_content})

    except Http404:
        return JsonResponse({'error': 'Recurso não encontrado.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': f'Erro interno do servidor: {e}'}, status=500)


@login_required
def atualizar_componentes_financeiros_servico(request, pk):
    """
    Retorna o HTML renderizado para os componentes financeiros de um serviço.
    """
    servico = get_object_or_404(Servico, pk=pk)

    lancamentos_qs = servico.lancamentos.all()
    regulares_agrupados, inadimplentes_agrupados = _preparar_dados_financeiros(lancamentos_qs)
    valor_total_contratado = lancamentos_qs.aggregate(total=Sum('valor'))['total'] or Decimal('0.00')
    total_pago = Pagamento.objects.filter(lancamento__in=lancamentos_qs).aggregate(total=Sum('valor_pago'))[
                     'total'] or Decimal('0.00')
    saldo_devedor = valor_total_contratado - total_pago
    percentual_pago = (total_pago / valor_total_contratado * 100) if valor_total_contratado > 0 else 0
    percentual_pago_visual = min(percentual_pago, Decimal('100.0'))
    percentual_devedor_visual = Decimal('100.0') - percentual_pago_visual
    percentual_a_pagar = 100 - round(percentual_pago, 2)

    context = {
        'servico': servico,
        'financeiro': {
            'valor_total': valor_total_contratado,
            'total_pago': total_pago,
            'saldo_devedor': saldo_devedor,
            'percentual_pago': round(percentual_pago, 2),
            'percentual_a_pagar': percentual_a_pagar,
            'percentual_pago_css': f"{percentual_pago_visual:.2f}".replace(",", "."),
            'percentual_devedor_css': f"{percentual_devedor_visual:.2f}".replace(",", "."),
        },
        'lancamentos_regulares_agrupados': regulares_agrupados,
        'lancamentos_inadimplentes_agrupados': inadimplentes_agrupados,
        'form_pagamento': PagamentoForm(),
    }

    resumo_html = render_to_string('gestao/partials/_servico_resumo_financeiro.html', context, request=request)
    tabela_html = render_to_string('gestao/partials/_tabela_financeira.html', context, request=request)

    return JsonResponse({
        'resumo_financeiro_html': resumo_html,
        'tabela_financeira_html': tabela_html
    })


@require_POST
@login_required
def adicionar_movimentacao_servico_ajax(request, servico_pk):
    """
    Salva um novo andamento de serviço enviado via AJAX e retorna uma resposta JSON.
    """
    servico = get_object_or_404(Servico, pk=servico_pk)
    form = MovimentacaoServicoForm(request.POST)
    if form.is_valid():
        movimentacao = form.save(commit=False)
        movimentacao.servico = servico
        if not movimentacao.responsavel:
            movimentacao.responsavel = request.user
        movimentacao.save()
        return JsonResponse({'status': 'success'})
    else:
        return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)


@login_required
def atualizar_historico_servico_partial(request, servico_pk):
    """
    Retorna apenas o HTML renderizado da timeline de andamentos.
    """
    servico = get_object_or_404(Servico, pk=servico_pk)
    movimentacoes = servico.movimentacoes.all().order_by('-data_atividade', '-data_criacao')
    return render(request, 'gestao/partials/_historico_movimentacoes_servico.html', {'movimentacoes': movimentacoes})


# ==============================================================================
# SEÇÃO: VIEWS DE CONFIGURAÇÃO E USUÁRIOS
# ==============================================================================

@login_required
def configuracoes(request):
    """ Página central de configurações com paginação de usuários e outras abas. """
    config, created = EscritorioConfiguracao.objects.get_or_create(pk=1)

    if request.method == 'POST' and 'salvar_escritorio' in request.POST:
        form_escritorio = EscritorioConfiguracaoForm(request.POST, request.FILES, instance=config)
        if form_escritorio.is_valid():
            form_escritorio.save()
            messages.success(request, 'Configurações do escritório salvas com sucesso!')
            return redirect('gestao:configuracoes')
    else:
        form_escritorio = EscritorioConfiguracaoForm(instance=config)

    # Otimização na busca de permissões
    users_list = User.objects.all().order_by('first_name').prefetch_related('groups')
    paginator = Paginator(users_list, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    grupos = Group.objects.order_by('name')
    perm_codenames = [p['codename'] for mod_perms in PERMISSOES_MAPEADAS.values() for p in mod_perms]
    perm_map = {p.codename: p for p in Permission.objects.filter(codename__in=perm_codenames)}
    perm_estruturadas = {
        mod: [{'id': perm_map[p['codename']].id, 'label': p['label']}
              for p in perms if p['codename'] in perm_map]
        for mod, perms in PERMISSOES_MAPEADAS.items()
    }

    context = {
        'form_escritorio': form_escritorio,
        'usuarios': page_obj,
        'grupos': grupos,
        'permissoes_estruturadas': perm_estruturadas,
        'form_tipo_servico': TipoServicoForm(),
        'form_area_processo': AreaProcessoForm(),
        'form_tipo_acao': TipoAcaoForm(),
        'tipos_servico': TipoServico.objects.all().order_by('nome'),
        'areas_processo': AreaProcesso.objects.all().order_by('nome'),
        'tipos_acao': TipoAcao.objects.select_related('area').all().order_by('area__nome', 'nome'),
    }
    return render(request, 'gestao/configuracoes.html', context)


@login_required
def get_permissoes_grupo_ajax(request, group_id):
    """ Retorna as permissões de um grupo específico em formato JSON. """
    grupo = get_object_or_404(Group, pk=group_id)
    permissoes = grupo.permissions.values_list('id', flat=True)
    return JsonResponse({'permissoes_ids': list(permissoes)})


@require_POST
@login_required
def salvar_permissoes_grupo(request, group_id):
    """ Salva as permissões selecionadas para um grupo. """
    grupo = get_object_or_404(Group, pk=group_id)
    permissoes_selecionadas_ids = request.POST.getlist('permissoes')
    permissoes_selecionadas = Permission.objects.filter(pk__in=permissoes_selecionadas_ids)
    grupo.permissions.set(permissoes_selecionadas)
    messages.success(request, f'Permissões do grupo "{grupo.name}" salvas com sucesso!')
    return redirect('gestao:configuracoes')


@login_required
@transaction.atomic
def adicionar_usuario(request):
    if request.method == 'POST':
        user_form = CustomUserCreationForm(request.POST)
        profile_form = UsuarioPerfilForm(request.POST, request.FILES)

        # Valida os dois formulários antes de qualquer ação no banco
        if user_form.is_valid() and profile_form.is_valid():
            # user_form.save() dispara o sinal que cria o UsuarioPerfil
            user = user_form.save()

            # O sinal já criou o perfil, agora o atualizamos com os dados do form
            profile = user.perfil

            # Recriamos o form do perfil, mas agora passando a instância
            # do perfil que acabamos de criar, para atualizá-lo
            profile_form_with_instance = UsuarioPerfilForm(request.POST, request.FILES, instance=profile)
            if profile_form_with_instance.is_valid():
                profile_form_with_instance.save()

            messages.success(request, f'Usuário "{user.username}" criado com sucesso!')
            return redirect('gestao:configuracoes')
    else:
        user_form = CustomUserCreationForm()
        profile_form = UsuarioPerfilForm()

    # Se algum formulário for inválido, eles serão renderizados novamente com os erros
    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'titulo_pagina': 'Adicionar Novo Usuário'
    }
    return render(request, 'gestao/form_usuario.html', context)


@login_required
@transaction.atomic
def editar_usuario(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    # Usar get_or_create é uma boa prática para garantir que o perfil sempre exista.
    perfil, created = UsuarioPerfil.objects.get_or_create(user=user)

    if request.method == 'POST':
        user_form = CustomUserChangeForm(request.POST, instance=user)
        profile_form = UsuarioPerfilForm(request.POST, request.FILES, instance=perfil)
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, f'Usuário "{user.username}" atualizado com sucesso!')
            return redirect('gestao:configuracoes')  # CORRIGIDO
    else:
        user_form = CustomUserChangeForm(instance=user)
        profile_form = UsuarioPerfilForm(instance=perfil)

    context = {
        'user_form': user_form, 'profile_form': profile_form, 'usuario_editado': user,
        'historico': user.history.all().order_by('-history_date'),
        'titulo_pagina': f'Editar Usuário: {user.username}'
    }
    return render(request, 'gestao/form_usuario.html', context)


@require_POST
@login_required
def ativar_desativar_usuario(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    if user != request.user:
        user.is_active = not user.is_active
        user.save()
        status = "ativado" if user.is_active else "desativado"
        messages.info(request, f'Usuário "{user.username}" foi {status}.')
    else:
        messages.error(request, 'Você não pode desativar seu próprio usuário.')
    return redirect('gestao:configuracoes')  # CORRIGIDO


@require_POST
@login_required
def salvar_cadastro_auxiliar_ajax(request, modelo, pk=None):
    try:
        ModelClass = apps.get_model('gestao', modelo)
        FormClass = {
            'tiposervico': TipoServicoForm,
            'areaprocesso': AreaProcessoForm,
            'tipoacao': TipoAcaoForm,
        }.get(modelo.lower())

        if not FormClass:
            return JsonResponse({'status': 'error', 'message': 'Modelo inválido.'}, status=400)

        instance = get_object_or_404(ModelClass, pk=pk) if pk else None
        form = FormClass(request.POST, instance=instance)

        if form.is_valid():
            instance = form.save()
            return JsonResponse({'status': 'success', 'pk': instance.pk, 'nome': str(instance)})
        else:
            return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@require_POST
@login_required
def excluir_cadastro_auxiliar_ajax(request, modelo, pk):
    try:
        ModelClass = apps.get_model('gestao', modelo)
        instance = get_object_or_404(ModelClass, pk=pk)
        instance.delete()
        return JsonResponse({'status': 'success'})
    except Exception as e:
        # Em um ambiente de produção, seria bom logar o erro `e`
        # para uma investigação mais aprofundada.
        return JsonResponse(
            {'status': 'error', 'message': 'Não foi possível excluir o item, pois ele pode estar em uso.'}, status=500)