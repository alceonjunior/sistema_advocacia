# gestao/views.py

# ==============================================================================
# IMPORTS
# ==============================================================================

# Python Standard Library
import datetime
import itertools
import json
import unicodedata
from datetime import datetime, date, time, timedelta
from decimal import Decimal
from operator import attrgetter, itemgetter

from dateutil.relativedelta import relativedelta
# Django Core
from django.apps import apps
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator, EmptyPage, InvalidPage
from django.db import transaction
from django.db.models import (Q, Case, CharField, DateField, DecimalField, F,
                              OuterRef, Subquery, Sum, Value, When, Func)
from django.http import (Http404, HttpResponse, HttpResponseBadRequest,
                         JsonResponse, HttpResponseForbidden)
from django.shortcuts import get_object_or_404, redirect, render
from django.template import Context, Template
from django.template.defaultfilters import truncatechars
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.db.models.functions import Coalesce
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from django.contrib.admin.views.decorators import staff_member_required
from unidecode import unidecode

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
                    UsuarioPerfilForm, DocumentoForm, GerarDocumentoForm, LancamentoFinanceiroForm,
                    DespesaRecorrenteVariavelForm, DespesaRecorrenteFixaForm, DespesaPontualForm, DespesaTipoForm)
from .models import (AreaProcesso, CalculoJudicial, Cliente, Documento,
                     EscritorioConfiguracao, Incidente, LancamentoFinanceiro,
                     ModeloDocumento, Movimentacao, MovimentacaoServico,
                     Pagamento, Processo, Recurso, Servico, TipoAcao,
                     TipoServico, UsuarioPerfil, ContratoHonorarios, ParteProcesso)

from .services import ServicoIndices
from .utils import data_por_extenso, valor_por_extenso
from .nfse_service import NFSEService # Adicione este import no topo
from django.conf import settings  # <--- ADICIONE ESTE IMPORT
from .models import Processo, Cliente, TipoMovimentacao # <--- GARANTA QUE TipoMovimentacao ESTÁ AQUI
from django.conf import settings  # <--- ADICIONE ESTE IMPORT
from .models import Processo, Cliente, TipoMovimentacao # <--- GARANTA QUE TipoMovimentacao ESTÁ AQUI
from django.middleware.csrf import get_token # Adicione este import no topo

import logging # Adicione esta linha para registrar erros

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

def dashboard(request):
    """
    Carrega a estrutura principal do Dashboard com a lógica de permissões corrigida.
    Agora, o painel exibe todos os processos e atividades nos quais o usuário
    está envolvido, seja como responsável principal ou como colaborador.
    """
    # =========================================================================
    # === 1. CONFIGURAÇÕES INICIAIS E CONSULTAS DE BASE =======================
    # =========================================================================
    usuario = request.user
    hoje = timezone.now().date()
    status_aberto = ['PENDENTE', 'EM_ANDAMENTO']

    # [CORREÇÃO] A consulta de processos agora inclui tanto o responsável quanto os colaboradores.
    # O .distinct() é importante para não contar o mesmo processo duas vezes.
    filtro_processos_usuario = Q(advogado_responsavel=usuario) | Q(advogados_envolvidos=usuario)

    # Consultas para os totalizadores (KPIs)
    processos_ativos_qs = Processo.objects.filter(filtro_processos_usuario, status_processo='ATIVO').distinct()

    # A lógica para serviços permanece a mesma, pois não há campo de "colaboradores" em serviços.
    servicos_ativos_qs = Servico.objects.filter(responsavel=usuario, concluido=False)

    # [CORREÇÃO] A consulta do "Pulso do Escritório" também foi atualizada.
    ultimas_movimentacoes = Movimentacao.objects.filter(
        processo__in=processos_ativos_qs
    ).order_by('-data_criacao').select_related('processo')[:5]

    # =========================================================================
    # === 2. LÓGICA PARA O "FOCO DO DIA" ======================================
    # =========================================================================
    # Esta seção já filtra corretamente as tarefas pelo 'responsavel' direto da tarefa,
    # portanto, não precisa de alterações. A tarefa de "ana.carolina" aparecerá aqui
    # quando a data do prazo estiver próxima.

    agenda_completa_foco = []

    # Busca movimentações de PROCESSOS (prazos e audiências) vencidas ou para hoje
    movs_processo = Movimentacao.objects.filter(
        responsavel=usuario, status__in=status_aberto, data_prazo_final__isnull=False, data_prazo_final__lte=hoje
    ).select_related('processo')
    for mov in movs_processo:
        agenda_completa_foco.append({
            'pk': mov.pk,
            'tipo': 'processo',
            'data': mov.data_prazo_final,
            'hora': mov.hora_prazo,
            'titulo': mov.titulo,
            'objeto_str': f"Proc: {mov.processo.numero_processo}",
        })

    # Busca TAREFAS de SERVIÇOS vencidas ou para hoje
    movs_servico = MovimentacaoServico.objects.filter(
        responsavel=usuario, status__in=status_aberto, prazo_final__isnull=False, prazo_final__lte=hoje
    ).select_related('servico__cliente')
    for tarefa in movs_servico:
        agenda_completa_foco.append({
            'pk': tarefa.pk,
            'tipo': 'servico_task',
            'data': tarefa.prazo_final,
            'hora': None,
            'titulo': tarefa.titulo,
            'objeto_str': f"Serviço: {tarefa.servico.descricao}",
        })

    # Busca SERVIÇOS cujo prazo final é hoje ou está vencido
    servicos_com_prazo = Servico.objects.filter(
        responsavel=usuario, concluido=False, prazo__isnull=False, prazo__lte=hoje
    ).select_related('cliente')
    for servico in servicos_com_prazo:
        if not any(d['tipo'] == 'servico_task' and d['objeto_str'] == f"Serviço: {servico.descricao}" for d in
                   agenda_completa_foco):
            agenda_completa_foco.append({
                'pk': servico.pk,
                'tipo': 'servico_main',
                'data': servico.prazo,
                'hora': None,
                'titulo': f"Prazo final do serviço",
                'objeto_str': f"{servico.descricao}",
            })

    # Ordena e Filtra as listas do Foco do Dia
    agenda_completa_foco = sorted(agenda_completa_foco, key=lambda x: x['data'])
    itens_vencidos = [item for item in agenda_completa_foco if item['data'] < hoje]
    itens_para_hoje = [item for item in agenda_completa_foco if item['data'] == hoje]

    # Tarefas futuras para a terceira coluna da "Visão Geral" (paginação é feita via AJAX)
    tarefas_pendentes_futuras = MovimentacaoServico.objects.filter(
        responsavel=usuario, status__in=status_aberto, prazo_final__gt=hoje
    ).select_related('servico')

    # =========================================================================
    # === 3. CONTEXTO FINAL PARA O TEMPLATE ===================================
    # =========================================================================
    context = {
        # Contadores para os KPIs
        'processos_ativos_count': processos_ativos_qs.count(),
        'servicos_ativos_count': servicos_ativos_qs.count(),
        'total_pendencias': len(itens_vencidos) + len(itens_para_hoje),

        # Listas para o "Foco do Dia"
        'itens_vencidos': itens_vencidos,
        'itens_para_hoje': itens_para_hoje,

        # Lista para a terceira coluna da "Visão Geral da Agenda"
        'tarefas_pendentes': tarefas_pendentes_futuras,

        # Lista para o "Pulso do Escritório"
        'ultimas_movimentacoes': ultimas_movimentacoes,

        'hoje': hoje,

        # Passa as listas completas para o Modal Gerencial funcionar corretamente
        'lista_processos_ativos': processos_ativos_qs,
        'lista_servicos_ativos': servicos_ativos_qs,
        'lista_total_pendencias': agenda_completa_foco,

        # === AJUSTE PARA MODAIS DE EDIÇÃO ===
        # Passa as instâncias dos formulários que os modais da página precisam
        'form_movimentacao': MovimentacaoForm(initial={'responsavel': usuario}),
        'form_movimentacao_servico': MovimentacaoServicoForm(),
        'form_edit': ServicoEditForm(),  # A variável deve ser 'form_edit' para o _modal_editar_servico.html
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
    View central para exibir todos os detalhes de um processo, agora passando
    dados completos dos tipos de movimentação para o cálculo de prazo no front-end.
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

    # --- ALTERAÇÃO APLICADA AQUI ---
    # Buscamos todos os tipos de movimentação para obter não apenas os dias de prazo,
    # mas também o tipo de contagem (dias úteis ou corridos).
    tipos_movimentacao = TipoMovimentacao.objects.all()
    # Criamos um dicionário detalhado para ser convertido em JSON no template.
    dados_tipos_movimentacao = {
        tm.id: {
            'dias_prazo': tm.sugestao_dias_prazo,
            'tipo_contagem': tm.tipo_contagem_prazo
        }
        for tm in tipos_movimentacao if tm.sugestao_dias_prazo is not None
    }
    # ---------------------------------

    context = {
        'processo': processo,
        'movimentacoes': movimentacoes,
        'lancamentos_regulares_agrupados': regulares_agrupados,
        'lancamentos_inadimplentes_agrupados': inadimplentes_agrupados,
        'todos_modelos': ModeloDocumento.objects.all().order_by('titulo'),
        'form_movimentacao': MovimentacaoForm(initial={'responsavel': request.user}),
        'dados_tipos_movimentacao_json': json.dumps(dados_tipos_movimentacao),  # Enviamos o dicionário detalhado
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
        'form_edit': ServicoEditForm()
    }
    return render(request, 'gestao/lista_servicos.html', context)


@login_required
def detalhe_servico(request, pk):
    """
    Exibe o painel de controle completo e funcional para um serviço extrajudicial.
    VERSÃO CORRIGIDA: Utiliza o related_name 'movimentacoes_servico' correto.
    """
    servico = get_object_or_404(
        Servico.objects.prefetch_related(
            # --- CORREÇÃO APLICADA AQUI ---
            'movimentacoes_servico__responsavel',
            # -----------------------------
            'lancamentos__pagamentos'
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
    total_pago = Pagamento.objects.filter(lancamento__in=lancamentos_qs).aggregate(total=Sum('valor_pago'))['total'] or Decimal('0.00')
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
        # --- CORREÇÃO APLICADA AQUI ---
        'movimentacoes': servico.movimentacoes_servico.all().order_by('-data_atividade', '-data_criacao'),
        # -----------------------------
        'form_movimentacao_servico': form_movimentacao,
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
    processo = get_object_or_404(Processo, pk=pk)

    if request.method == 'POST':
        form = ProcessoForm(request.POST, instance=processo)
        if form.is_valid():
            form.save()
            # Adicionamos uma mensagem de sucesso para melhor feedback ao usuário
            messages.success(request, "Processo atualizado com sucesso!")
            return redirect('gestao:detalhe_processo', pk=processo.pk)
    else:
        form = ProcessoForm(instance=processo)

    # --- LÓGICA ADICIONADA PARA O NOVO COMPONENTE ---
    # Busca os colaboradores que já estão no processo
    colaboradores_no_processo = processo.advogados_envolvidos.all()
    advogado_responsavel_id = processo.advogado_responsavel.id if processo.advogado_responsavel else None

    # Busca todos os usuários ativos, excluindo quem já está no processo e o próprio advogado responsável
    colaboradores_disponiveis = User.objects.filter(is_active=True).exclude(
        pk__in=[c.pk for c in colaboradores_no_processo]
    )
    if advogado_responsavel_id:
        colaboradores_disponiveis = colaboradores_disponiveis.exclude(pk=advogado_responsavel_id)
    # --- FIM DA LÓGICA ADICIONADA ---

    context = {
        'form': form,
        'processo': processo,
        # Passa as novas listas para o template
        'colaboradores_no_processo': colaboradores_no_processo,
        'colaboradores_disponiveis': colaboradores_disponiveis,
    }
    return render(request, 'gestao/editar_processo.html', context)


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
    Versão corrigida para não duplicar cabeçalho/rodapé.
    """
    processo = get_object_or_404(Processo, pk=processo_pk)
    modelo = get_object_or_404(ModeloDocumento, pk=modelo_pk)

    # Lógica para obter o cliente e montar o contexto das variáveis
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

    # ===== CORREÇÃO DEFINITIVA APLICADA AQUI =====
    # Renderizamos APENAS o corpo principal do modelo para o campo 'conteudo'.
    # O cabeçalho e o rodapé serão adicionados pelo template de impressão.
    conteudo_renderizado = ""
    if modelo.conteudo:
        conteudo_renderizado = Template(modelo.conteudo).render(contexto_variaveis)

    titulo_sugerido = f"{modelo.titulo} - {cliente_principal.nome_completo if cliente_principal else 'Processo'}"

    if request.method == 'POST':
        form = GerarDocumentoForm(request.POST)
        if form.is_valid():
            documento = form.save(commit=False)
            documento.processo = processo
            # É crucial manter a referência ao modelo original para buscar o cabeçalho/rodapé depois
            documento.modelo_origem = modelo
            documento.save()
            # Redireciona para a página de impressão correta
            return redirect('gestao:imprimir_documento', pk=documento.pk)
    else:
        # Passa apenas o conteúdo principal renderizado para o formulário
        form = GerarDocumentoForm(initial={'titulo': titulo_sugerido, 'conteudo': conteudo_renderizado})

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
            # ===== LINHA ALTERADA =====
            # Redireciona para a nova página de impressão com o PK do documento editado
            return redirect('gestao:imprimir_documento', pk=documento.pk)
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
        'escritorio': escritorio,
        # Alterado: Garante que o nome e a OAB sejam string vazias se forem None ou vazias
        'emissor_nome': (escritorio.nome_escritorio if escritorio else '') or '',
        'emissor_oab': (escritorio.oab_principal if escritorio else '') or '',
        'data_emissao_extenso': data_por_extenso(timezone.now().date()), # Adiciona a data por extenso
    }

    return render(request, 'gestao/recibo_pagamento.html', context)


# ==============================================================================
# SEÇÃO: VIEWS DE CLIENTES
# ==============================================================================

@login_required
def lista_clientes(request):
    """Exibe a lista de CLIENTES ATIVOS com filtros, ordenação e estatísticas."""
    # AJUSTE: Adicionamos a contagem de TODOS os processos/serviços vinculados

    status_baixados = ['ARQUIVADO', 'EXTINTO', 'ENCERRADO']

    base_queryset = Cliente.objects.filter(is_cliente=True).annotate(
        # Contagem para a lógica do botão de exclusão (qualquer vínculo)
        processos_vinculados_count=Count('participacoes', distinct=True),
        servicos_vinculados_count=Count('servicos', distinct=True),
        # Contagem de casos ativos (para exibição)
        processos_ativos_count=Count('participacoes__processo',
                                     filter=Q(participacoes__processo__status_processo='ATIVO'), distinct=True),
        servicos_ativos_count=Count('servicos', filter=Q(servicos__concluido=False), distinct=True),
        # AJUSTE: Nova contagem de casos arquivados/concluídos (para exibição)
        processos_arquivados_count=Count('participacoes__processo',
                                         filter=Q(participacoes__processo__status_processo__in=status_baixados),
                                         distinct=True),
        servicos_concluidos_count=Count('servicos', filter=Q(servicos__concluido=True), distinct=True)
    )
    # O resto da view permanece igual...
    cliente_filter = ClienteFilter(request.GET, queryset=base_queryset)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'gestao/partials/_lista_clientes_partial.html', {'filter': cliente_filter})

    stats = {
        'total': cliente_filter.qs.count(),
        'com_processos_ativos': cliente_filter.qs.filter(processos_ativos_count__gt=0).count(),
        'com_servicos_ativos': cliente_filter.qs.filter(servicos_ativos_count__gt=0).count(),
        'total_ativos': cliente_filter.qs.filter(Q(processos_ativos_count__gt=0) | Q(servicos_ativos_count__gt=0)).distinct().count(),
    }
    stats_labels = {'total': 'TOTAL DE CLIENTES', 'total_ativos': 'CLIENTES ATIVOS (TOTAL)'}
    context = {
        'filter': cliente_filter,
        'stats': stats,
        'stats_labels': stats_labels,
        'form': ClienteForm(),
        'titulo_pagina': 'Painel de Clientes'
    }
    return render(request, 'gestao/lista_clientes.html', context)


@login_required
def lista_pessoas(request):
    """Exibe a lista de TODAS AS PESSOAS CADASTRADAS (clientes e não-clientes)."""
    # AJUSTE: Adicionamos a contagem de TODOS os processos/serviços vinculados
    status_baixados = ['ARQUIVADO', 'EXTINTO', 'ENCERRADO']

    base_queryset = Cliente.objects.annotate(
        processos_vinculados_count=Count('participacoes', distinct=True),
        servicos_vinculados_count=Count('servicos', distinct=True),
        processos_ativos_count=Count('participacoes__processo',
                                     filter=Q(participacoes__processo__status_processo='ATIVO'), distinct=True),
        servicos_ativos_count=Count('servicos', filter=Q(servicos__concluido=False), distinct=True),
        processos_arquivados_count=Count('participacoes__processo',
                                         filter=Q(participacoes__processo__status_processo__in=status_baixados),
                                         distinct=True),
        servicos_concluidos_count=Count('servicos', filter=Q(servicos__concluido=True), distinct=True)
    )
    # O resto da view permanece igual...
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
    stats_labels = {'total': 'TOTAL DE PESSOAS', 'total_ativos': 'PESSOAS ATIVAS (TOTAL)'}
    context = {
        'filter': cliente_filter,
        'stats': stats,
        'stats_labels': stats_labels,
        'form': ClienteForm(),
        'titulo_pagina': 'Painel de Pessoas'
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
        'titulo_pagina': 'Cadastrar Nova Pessoa'
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
        # ===== CORREÇÃO APLICADA AQUI =====
        'form_servico': ServicoForm(prefix='servico'),
        'form_contrato': ContratoHonorariosForm(prefix='contrato'),
        # ====================================
        'form_cliente_modal': ClienteModalForm(),
        'form_tipo_servico': TipoServicoForm(),
    }
    return render(request, 'gestao/adicionar_servico.html', context)


@require_POST
@login_required
@transaction.atomic  # Garante que ou tudo é salvo, ou nada é.
def salvar_servico_ajax(request):
    """
    Recebe os dados do wizard via AJAX, valida e salva o serviço e, opcionalmente, o contrato.
    Versão final e robusta.
    """
    try:
        data = json.loads(request.body)
        servico_data = data.get('servico', {})
        contrato_data = data.get('contrato', {})
        has_contrato = data.get('has_contrato', False)

        # ===== INÍCIO DA CORREÇÃO DEFINITIVA =====
        # 1. Os dados já vêm separados do JavaScript, então instanciamos os formulários
        #    passando diretamente os dicionários correspondentes, SEM o argumento 'prefix'.
        form_servico = ServicoForm(servico_data)

        form_contrato = None
        if has_contrato:
            form_contrato = ContratoHonorariosForm(contrato_data)
        # ===== FIM DA CORREÇÃO DEFINITIVA =====

        # Validação dos formulários
        servico_is_valid = form_servico.is_valid()
        contrato_is_valid = not has_contrato or (form_contrato and form_contrato.is_valid())

        if servico_is_valid and contrato_is_valid:
            # Salva o serviço primeiro para obter seu ID
            novo_servico = form_servico.save()

            # Se for para criar um contrato e os dados essenciais foram preenchidos
            if has_contrato and form_contrato and form_contrato.cleaned_data.get('valor_pagamento_fixo'):
                # Cria o objeto ContratoHonorarios manualmente para garantir que todos os
                # campos obrigatórios e relacionamentos sejam preenchidos antes de salvar.
                ContratoHonorarios.objects.create(
                    content_object=novo_servico,
                    cliente=novo_servico.cliente,
                    descricao=form_contrato.cleaned_data.get('descricao'),
                    valor_pagamento_fixo=form_contrato.cleaned_data.get('valor_pagamento_fixo'),
                    qtde_pagamentos_fixos=form_contrato.cleaned_data.get('qtde_pagamentos_fixos'),
                    data_primeiro_vencimento=form_contrato.cleaned_data.get('data_primeiro_vencimento'),
                    percentual_exito=form_contrato.cleaned_data.get('percentual_exito')
                )

            return JsonResponse({
                'status': 'success',
                'redirect_url': novo_servico.get_absolute_url()
            })
        else:
            # Combina os erros dos dois formulários em um único dicionário para exibição
            errors = {}
            errors.update(form_servico.errors.get_json_data())
            if has_contrato and form_contrato:
                errors.update(form_contrato.errors.get_json_data())

            return JsonResponse({'status': 'error', 'errors': errors}, status=400)

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'errors': {'Requisição': [{'message': 'Formato de dados inválido.'}]}},
                            status=400)
    except Exception as e:
        print(f"Erro inesperado em salvar_servico_ajax: {e}")
        return JsonResponse({'status': 'error', 'errors': {'Servidor': [{'message': f'Ocorreu um erro interno: {e}'}]}},
                            status=500)

@require_POST
@login_required
@transaction.atomic # Garante que ou tudo é salvo, ou nada é.
def excluir_servico(request, pk):
    """
    Exclui um serviço e qualquer contrato de honorários associado a ele.
    """
    servico = get_object_or_404(Servico, pk=pk)

    # Busca e exclui qualquer contrato vinculado a este serviço
    content_type = ContentType.objects.get_for_model(servico)
    ContratoHonorarios.objects.filter(content_type=content_type, object_id=servico.pk).delete()

    servico_nome = str(servico)
    servico.delete()

    messages.success(request, f'O serviço "{servico_nome}" e seus vínculos foram excluídos com sucesso.')
    return redirect('gestao:lista_servicos')


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

    # --- LÓGICA POST (quando um novo cálculo é submetido) ---
    if request.method == 'POST':
        form = CalculoForm(request.POST)
        if form.is_valid():
            dados_calculo = form.cleaned_data
            resultado, erro = _perform_calculation(dados_calculo)

            if resultado and not erro:
                memoria_calculo_json = []
                if resultado.get('memorial'):
                    # Converte o memorial para um formato serializável (JSON)
                    memoria_calculo_json = [
                        {'termo_inicial': l['termo_inicial'].isoformat(), 'termo_final': l['termo_final'].isoformat(),
                         'variacao_periodo': str(l['variacao_periodo']),
                         'valor_atualizado_mes': str(l['valor_atualizado_mes'])} for l in resultado['memorial']]

                # Salva o novo cálculo no banco de dados
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
                # Redireciona para a página de visualização do cálculo recém-criado
                return redirect('gestao:carregar_calculo', processo_pk=processo.pk, calculo_pk=novo_calculo_salvo.pk)

        # Se o formulário for inválido, renderiza a página novamente com os erros
        contexto = {
            'processo': processo,
            'calculos_salvos': processo.calculos.all().order_by('-data_calculo'),
            'form': form,
            'resultado': None,
            'erro': 'Formulário inválido. Verifique os campos marcados.',
        }
        return render(request, 'gestao/calculo_judicial.html', contexto)

    # --- LÓGICA GET (quando a página é carregada ou um cálculo é visualizado) ---
    form = CalculoForm(initial=request.session.pop('form_initial_data', None))
    resultado_final, erro_final, calculo_carregado = None, None, None
    form_data = {}  # ===== PONTO 1 DA CORREÇÃO: Inicializa o dicionário

    if calculo_pk:
        calculo_carregado = get_object_or_404(CalculoJudicial, pk=calculo_pk, processo=processo)

        # Popula o dicionário 'form_data' com os dados do cálculo carregado
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
            'gerar_memorial': True,  # Assume que sempre queremos ver o memorial ao carregar
        }
        # Preenche o formulário com os dados carregados
        form = CalculoForm(initial=form_data)
        # Recalcula o resultado para exibição
        resultado_final, erro_final = _perform_calculation(form_data)

    # Monta o contexto final para o template
    contexto = {
        'processo': processo,
        'calculos_salvos': processo.calculos.all().order_by('-data_calculo'),
        'form': form,
        'calculo_carregado': calculo_carregado,
        'resultado': resultado_final,
        'erro': erro_final,
        'form_data': form_data,  # ===== PONTO 2 DA CORREÇÃO: Adiciona ao contexto
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
        # É CRUCIAL PASSAR request.FILES AQUI PARA LIDAR COM UPLOAD DE ARQUIVOS
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
        'configuracao_escritorio': config,  # Passa a instância da configuração para o template
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

@login_required
def imprimir_documento(request, pk):
    """
    Prepara uma página otimizada para a impressão de um documento gerado.
    """
    documento = get_object_or_404(Documento, pk=pk)
    context = {
        'documento': documento,
        'escritorio': EscritorioConfiguracao.objects.first(),  # Para dados do cabeçalho/rodapé
    }
    return render(request, 'gestao/documentos/imprimir_documento.html', context)


@login_required
def get_movimentacao_json(request, pk):
    """
    Retorna os dados de uma movimentação em JSON, incluindo os novos campos de data,
    para preencher o modal de edição.
    """
    try:
        mov = get_object_or_404(Movimentacao, pk=pk)

        cliente_principal = mov.processo.partes.filter(is_cliente_do_processo=True).first() or mov.processo.partes.filter(tipo_participacao='AUTOR').first()
        cliente_nome = ""
        cliente_telefone = ""
        if cliente_principal and cliente_principal.cliente.telefone_principal:
            cliente_nome = cliente_principal.cliente.nome_completo
            cliente_telefone = ''.join(filter(str.isdigit, cliente_principal.cliente.telefone_principal))

        data = {
            'pk': mov.pk,
            'titulo': mov.titulo,
            'tipo_movimentacao_id': mov.tipo_movimentacao_id,
            'detalhes': mov.detalhes,
            'link_referencia': mov.link_referencia,
            'responsavel_id': mov.responsavel_id,
            'status': mov.status,
            'hora_prazo': mov.hora_prazo.strftime('%H:%M') if mov.hora_prazo else '',
            # --- NOVOS CAMPOS ADICIONADOS ---
            'data_publicacao': mov.data_publicacao.strftime('%Y-%m-%d') if mov.data_publicacao else '',
            'data_intimacao': mov.data_intimacao.strftime('%Y-%m-%d') if mov.data_intimacao else '',
            'data_inicio_prazo': mov.data_inicio_prazo.strftime('%Y-%m-%d') if mov.data_inicio_prazo else '',
            'data_prazo_final': mov.data_prazo_final.strftime('%Y-%m-%d') if mov.data_prazo_final else '',
            # ---------------------------------
            'cliente_nome': cliente_nome,
            'cliente_telefone': cliente_telefone,
            'remetente_nome': request.user.get_full_name() or request.user.username,
        }
        return JsonResponse(data)
    except Http404:
        return JsonResponse({'error': 'Movimentação não encontrada'}, status=404)


@require_POST
@login_required
def editar_movimentacao_ajax(request, pk):
    """
    Processa a submissão do formulário de edição da movimentação via AJAX.
    """
    movimentacao = get_object_or_404(Movimentacao, pk=pk)
    form = MovimentacaoForm(request.POST, instance=movimentacao)

    if form.is_valid():
        form.save()
        messages.success(request, 'Movimentação atualizada com sucesso!')
        return JsonResponse({'status': 'success'})
    else:
        # Retorna os erros do formulário em formato JSON para o frontend
        return JsonResponse({'status': 'error', 'errors': form.errors.get_json_data()}, status=400)


@login_required
def get_servico_json(request, pk):
    """
    Retorna os dados de um serviço específico em formato JSON para ser
    usado pelo modal de edição.

    VERSÃO CORRIGIDA: As chaves do dicionário agora correspondem
    aos nomes dos campos do formulário (ex: 'responsavel' em vez de 'responsavel_id').
    """
    try:
        servico = get_object_or_404(Servico, pk=pk)
        data = {
            'pk': servico.pk,
            # --- CORREÇÃO APLICADA AQUI ---
            'responsavel': servico.responsavel_id,  # Chave 'responsavel' para corresponder ao formulário
            'descricao': servico.descricao,
            'codigo_servico_municipal': servico.codigo_servico_municipal,  # Adicionado para completar o modal
            'data_inicio': servico.data_inicio.strftime('%Y-%m-%d') if servico.data_inicio else '',
            'recorrente': servico.recorrente,
            'prazo': servico.prazo.strftime('%Y-%m-%d') if servico.prazo else '',
            'data_encerramento': servico.data_encerramento.strftime('%Y-%m-%d') if servico.data_encerramento else '',
            'concluido': servico.concluido,
            'ativo': servico.ativo,
        }
        return JsonResponse(data)
    except Http404:
        return JsonResponse({'error': 'Serviço não encontrado'}, status=404)


@require_POST
@login_required
def editar_servico_ajax(request, pk):
    """
    Processa a submissão do formulário de edição do serviço via AJAX.
    """
    servico = get_object_or_404(Servico, pk=pk)
    # Usamos o ServicoEditForm que já existe
    form = ServicoEditForm(request.POST, instance=servico)

    if form.is_valid():
        form.save()
        messages.success(request, 'Serviço atualizado com sucesso!')
        return JsonResponse({'status': 'success'})
    else:
        return JsonResponse({'status': 'error', 'errors': form.errors.get_json_data()}, status=400)


@login_required
def get_movimentacao_servico_json(request, pk):
    """ Retorna os dados de uma movimentação de serviço em formato JSON. """
    try:
        mov = get_object_or_404(MovimentacaoServico, pk=pk)
        data = {
            'pk': mov.pk,
            'titulo': mov.titulo,
            'detalhes': mov.detalhes,
            'data_atividade': mov.data_atividade.strftime('%Y-%m-%d') if mov.data_atividade else '',
            'responsavel_id': mov.responsavel_id,
            'status': mov.status,
            'prazo_final': mov.prazo_final.strftime('%Y-%m-%d') if mov.prazo_final else '',
        }
        return JsonResponse(data)
    except Http404:
        return JsonResponse({'error': 'Movimentação não encontrada'}, status=404)

@require_POST
@login_required
def editar_movimentacao_servico_ajax(request, pk):
    """ Processa a submissão do formulário de edição da movimentação de serviço via AJAX. """
    movimentacao = get_object_or_404(MovimentacaoServico, pk=pk)
    form = MovimentacaoServicoForm(request.POST, instance=movimentacao)

    if form.is_valid():
        form.save()
        messages.success(request, 'Atividade atualizada com sucesso!')
        return JsonResponse({'status': 'success'})
    else:
        return JsonResponse({'status': 'error', 'errors': form.errors.get_json_data()}, status=400)


@require_POST
@login_required
def emitir_nfse_view(request, servico_pk):
    """ View que dispara o serviço de emissão de NFS-e. """
    service = NFSEService()
    resultado = service.enviar_rps_para_emissao(servico_pk)

    if resultado['status'] == 'sucesso':
        messages.success(request, resultado['mensagem'])
    else:
        messages.error(request, resultado['mensagem'])

    return redirect('gestao:detalhe_servico', pk=servico_pk)


@login_required
def get_all_clients_json(request):
    """
    Retorna uma lista de todos os clientes formatada para uso com a biblioteca Select2.
    """
    # Ordena os clientes por nome para uma melhor experiência no dropdown
    clientes = Cliente.objects.all().order_by('nome_completo')

    # Formata os dados no padrão que o Select2 espera: uma lista de objetos com 'id' e 'text'
    client_data = [{"id": cliente.pk, "text": cliente.nome_completo} for cliente in clientes]

    return JsonResponse(client_data, safe=False)


@login_required
def painel_financeiro(request):
    """
    Renderiza o painel financeiro aprimorado com KPIs, gráficos e projeções.
    Versão com todas as correções de erros.
    """
    hoje = timezone.now().date()

    # --- Lógica de Filtros ---
    data_inicio_str = request.GET.get('data_inicio', hoje.replace(day=1).strftime('%Y-%m-%d'))
    # CORREÇÃO DO AttributeError: Parênteses ajustados para calcular a data antes de formatar
    data_fim_default = (hoje.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    data_fim_str = request.GET.get('data_fim', data_fim_default.strftime('%Y-%m-%d'))

    data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
    data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()

    # --- Consulta Base com Anotações ---
    lancamentos_base = LancamentoFinanceiro.objects.all()

    lancamentos_com_status = lancamentos_base.annotate(
        total_pago=Coalesce(Sum('pagamentos__valor_pago'), Decimal(0), output_field=DecimalField())
    ).annotate(
        status_calculado=Case(
            When(valor__lte=F('total_pago'), then=Value('PAGO')),
            When(data_vencimento__lt=hoje, then=Value('ATRASADO')),
            When(total_pago__gt=0, then=Value('PARCIALMENTE_PAGO')),
            default=Value('A_PAGAR'),
            output_field=CharField()
        )
    )

    lancamentos_periodo = lancamentos_com_status.filter(data_vencimento__range=[data_inicio, data_fim])

    # --- KPIs (Indicadores Chave) ---
    pagamentos_periodo = Pagamento.objects.filter(data_pagamento__range=[data_inicio, data_fim])
    total_recebido = \
    pagamentos_periodo.filter(lancamento__tipo='RECEITA').aggregate(total=Coalesce(Sum('valor_pago'), Decimal(0)))[
        'total']
    total_pago = \
    pagamentos_periodo.filter(lancamento__tipo='DESPESA').aggregate(total=Coalesce(Sum('valor_pago'), Decimal(0)))[
        'total']
    saldo_realizado = total_recebido - total_pago

    previsao_receitas = lancamentos_periodo.filter(tipo='RECEITA').aggregate(total=Coalesce(Sum('valor'), Decimal(0)))[
        'total']
    previsao_despesas = lancamentos_periodo.filter(tipo='DESPESA').aggregate(total=Coalesce(Sum('valor'), Decimal(0)))[
        'total']

    # --- Análise de Inadimplência ---
    inadimplentes = lancamentos_com_status.filter(status_calculado='ATRASADO').order_by('data_vencimento')
    total_inadimplencia = sum(lanc.valor - lanc.total_pago for lanc in inadimplentes)

    # --- Estrutura de Dados Hierárquica ---
    analise_por_cliente = []
    clientes_no_periodo = Cliente.objects.filter(lancamentos__in=lancamentos_periodo).distinct()

    for cliente in clientes_no_periodo:
        lancamentos_cliente = lancamentos_periodo.filter(cliente=cliente)
        processos_cliente = lancamentos_cliente.filter(processo__isnull=False).values('processo_id',
                                                                                      'processo__numero_processo').annotate(
            total=Sum('valor'))
        servicos_cliente = lancamentos_cliente.filter(servico__isnull=False).values('servico_id',
                                                                                    'servico__descricao').annotate(
            total=Sum('valor'))

        analise_por_cliente.append({
            'cliente': cliente,
            'total_faturado_periodo': lancamentos_cliente.filter(tipo='RECEITA').aggregate(total=Sum('valor'))[
                                          'total'] or 0,
            'processos': list(processos_cliente),
            'servicos': list(servicos_cliente)
        })
    analise_por_cliente = sorted(analise_por_cliente, key=lambda x: x['total_faturado_periodo'], reverse=True)

    # --- Contexto Final ---
    context = {
        'titulo_pagina': "Painel Financeiro",
        'form_lancamento': LancamentoFinanceiroForm(),
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'saldo_realizado': saldo_realizado,
        'previsao_receitas': previsao_receitas,
        'previsao_despesas': previsao_despesas,
        'total_inadimplencia': total_inadimplencia,
        'analise_por_cliente': analise_por_cliente,
        'inadimplentes': inadimplentes,
        'contas_a_pagar': lancamentos_periodo.filter(tipo='DESPESA').order_by('data_vencimento'),
        'contas_a_receber': lancamentos_periodo.filter(tipo='RECEITA').order_by('data_vencimento'),
    }
    return render(request, 'gestao/financeiro/painel_financeiro.html', context)


@login_required
@transaction.atomic
def adicionar_despesa_wizard(request):
    """
    Controla o fluxo do wizard para adicionar diferentes tipos de despesa.
    O estado do wizard é mantido na sessão.
    Após salvar, redireciona para a tela de origem (painel financeiro ou de despesas).
    """
    STEP_SELECT_TYPE = 'select_type'
    STEP_FILL_DETAILS = 'fill_details'

    current_step = request.session.get('despesa_wizard_step', STEP_SELECT_TYPE)
    despesa_type = request.session.get('despesa_type', None)
    categoria = request.session.get('despesa_categoria', None)
    next_url = request.session.get('despesa_wizard_next_url', reverse('gestao:painel_financeiro'))

    if request.method == 'POST':
        if 'reset_wizard' in request.POST:
            request.session.pop('despesa_wizard_step', None)
            request.session.pop('despesa_type', None)
            request.session.pop('despesa_categoria', None)
            request.session.pop('despesa_wizard_next_url', None)
            return redirect('gestao:adicionar_despesa_wizard')

        if current_step == STEP_SELECT_TYPE:
            form_type = DespesaTipoForm(request.POST)
            if form_type.is_valid():
                despesa_type = form_type.cleaned_data['tipo_despesa']
                categoria = form_type.cleaned_data['categoria']
                request.session['despesa_type'] = despesa_type
                request.session['despesa_categoria'] = categoria
                request.session['despesa_wizard_step'] = STEP_FILL_DETAILS

                # Guarda a URL de onde o usuário veio
                if 'next' in request.GET:
                    request.session['despesa_wizard_next_url'] = request.GET['next']
                else:
                    referer = request.META.get('HTTP_REFERER')
                    # Verifica se o referer é um dos painéis esperados
                    if referer and (reverse('gestao:painel_financeiro') in referer or reverse(
                            'gestao:painel_despesas') in referer):
                        request.session['despesa_wizard_next_url'] = referer
                    else:
                        request.session['despesa_wizard_next_url'] = reverse('gestao:painel_financeiro')

                return redirect('gestao:adicionar_despesa_wizard')
            else:
                messages.error(request,
                               'Por favor, selecione um tipo de despesa válido e categoria.')  # Mensagem mais específica

        elif current_step == STEP_FILL_DETAILS and despesa_type:
            form_detail = None
            if despesa_type == 'pontual':
                form_detail = DespesaPontualForm(request.POST)
            elif despesa_type == 'recorrente_fixa':
                form_detail = DespesaRecorrenteFixaForm(request.POST)
            elif despesa_type == 'recorrente_variavel':
                form_detail = DespesaRecorrenteVariavelForm(request.POST)

            if form_detail and form_detail.is_valid():
                # NOVO: Obtém o cliente selecionado do formulário de detalhes
                cliente_selecionado = form_detail.cleaned_data.get('cliente')

                # Se cliente for obrigatório no seu modelo e não foi fornecido
                # você pode adicionar uma validação aqui antes do try
                # if not cliente_selecionado:
                #     messages.error(request, 'Cliente é um campo obrigatório para a despesa.')
                #     return render(request, 'gestao/financeiro/adicionar_despesa_wizard.html', context)

                try:
                    with transaction.atomic():
                        if despesa_type == 'pontual' or despesa_type == 'recorrente_variavel':
                            LancamentoFinanceiro.objects.create(
                                descricao=form_detail.cleaned_data['descricao'],
                                valor=form_detail.cleaned_data['valor'],
                                data_vencimento=form_detail.cleaned_data['data_vencimento'],
                                tipo='DESPESA',
                                categoria=categoria,
                                cliente=cliente_selecionado,  # NOVO: Passa o cliente
                                # usuario_criacao=request.user, # Descomentar se existir no seu modelo LancamentoFinanceiro
                            )
                        elif despesa_type == 'recorrente_fixa':
                            valor_recorrente = form_detail.cleaned_data['valor_recorrente']
                            dia_vencimento = form_detail.cleaned_data['dia_vencimento_recorrente']
                            data_inicio_recorrencia = form_detail.cleaned_data['data_inicio_recorrencia']
                            # Se data_fim_recorrencia não for fornecida, define um período longo (ex: 10 anos a partir de agora)
                            data_fim_recorrencia = form_detail.cleaned_data['data_fim_recorrencia']
                            if not data_fim_recorrencia:
                                data_fim_recorrencia = date.today() + relativedelta(
                                    years=10)  # Fallback para o fim da recorrência

                            # Começa a iteração a partir do mês da data_inicio_recorrencia
                            current_iteration_date = data_inicio_recorrencia.replace(day=1)

                            while current_iteration_date <= data_fim_recorrencia:
                                try:
                                    data_vencimento_mensal = current_iteration_date.replace(day=dia_vencimento)
                                except ValueError:
                                    # Se o dia do vencimento for maior que os dias do mês (ex: 31 de fev), ajusta para o último dia do mês
                                    last_day_of_month = (current_iteration_date + relativedelta(months=1)).replace(
                                        day=1) - timedelta(days=1)
                                    data_vencimento_mensal = last_day_of_month

                                # Somente cria o lançamento se a data de vencimento estiver dentro do período
                                if data_vencimento_mensal >= data_inicio_recorrencia and data_vencimento_mensal <= data_fim_recorrencia:
                                    LancamentoFinanceiro.objects.create(
                                        descricao=f"{form_detail.cleaned_data['descricao']} ({data_vencimento_mensal.strftime('%m/%Y')})",
                                        valor=valor_recorrente,
                                        data_vencimento=data_vencimento_mensal,
                                        tipo='DESPESA',
                                        categoria=categoria,
                                        cliente=cliente_selecionado,  # NOVO: Passa o cliente
                                        # usuario_criacao=request.user, # Descomentar se existir no seu modelo
                                    )
                                # Avança para o próximo mês
                                current_iteration_date += relativedelta(months=1)

                    messages.success(request, f'Despesa ({despesa_type}) salva com sucesso!')
                    request.session.pop('despesa_wizard_step', None)
                    request.session.pop('despesa_type', None)
                    request.session.pop('despesa_categoria', None)
                    final_redirect_url = request.session.pop('despesa_wizard_next_url',
                                                             reverse('gestao:painel_financeiro'))
                    return redirect(final_redirect_url)
                except Exception as e:
                    messages.error(request,
                                   f'Erro ao salvar despesa: {e}. Verifique se um cliente válido foi selecionado ou se o campo cliente no modelo é opcional.')  # Mensagem mais detalhada
                    # Permanece no mesmo passo para correção
            else:
                messages.error(request, 'Por favor, corrija os erros no formulário de detalhes.')
                # Continua no mesmo passo para exibir os erros

    # Lógica GET ou formulários inválidos (contexto)
    context = {'titulo_pagina': "Adicionar Nova Despesa"}
    if current_step == STEP_SELECT_TYPE:
        context['form_type'] = DespesaTipoForm(initial={'tipo_despesa': despesa_type, 'categoria': categoria})
        context['current_step'] = STEP_SELECT_TYPE
    elif current_step == STEP_FILL_DETAILS:
        if despesa_type == 'pontual':
            context['form_detail'] = DespesaPontualForm(request.POST if request.method == 'POST' else None)
        elif despesa_type == 'recorrente_fixa':
            context['form_detail'] = DespesaRecorrenteFixaForm(request.POST if request.method == 'POST' else None)
        elif despesa_type == 'recorrente_variavel':
            context['form_detail'] = DespesaRecorrenteVariavelForm(request.POST if request.method == 'POST' else None)
        context['despesa_type'] = despesa_type
        # NOVO: Para exibir a categoria selecionada (se for o caso)
        if categoria:
            context['categoria_selecionada'] = dict(LancamentoFinanceiro.CATEGORIA_CHOICES).get(categoria, categoria)
        context['current_step'] = STEP_FILL_DETAILS

    return render(request, 'gestao/financeiro/adicionar_despesa_wizard.html', context)


@require_POST
@login_required
@transaction.atomic  # Garante que a operação seja atômica
def adicionar_lancamento_financeiro_ajax(request):
    """
    Salva um novo lançamento financeiro (receita ou despesa) via AJAX.
    """
    form = LancamentoFinanceiroForm(request.POST)

    if form.is_valid():
        lancamento = form.save(commit=False)
        lancamento.usuario_criacao = request.user  # Assumindo que você tem um campo para o usuário que criou
        lancamento.save()

        messages.success(request, 'Lançamento financeiro salvo com sucesso!')
        return JsonResponse({'status': 'success'})
    else:
        # Retorna os erros do formulário em formato JSON para o frontend
        return JsonResponse({'status': 'error', 'errors': form.errors.get_json_data()}, status=400)


@login_required
def importacao_projudi_view(request):
    """
    Renderiza a página de importação, já pré-carregando a lista de todos
    os processos para uma experiência de vinculação instantânea.
    """
    # MELHORIA: Pré-carrega todos os processos para o seletor de vinculação.
    todos_processos = Processo.objects.select_related('advogado_responsavel').prefetch_related(
        'partes__cliente').order_by('-data_distribuicao')

    context = {
        'titulo_pagina': "Importador Inteligente do Projudi",
        'todos_processos': todos_processos,  # Envia a lista para o template
    }
    return render(request, 'gestao/importacao/importar_projudi.html', context)


@require_POST
@login_required
def analisar_dados_projudi_ajax(request):
    """
    Recebe o JSON, analisa os dados e busca clientes existentes.
    A lista de processos não é mais buscada aqui, pois já foi pré-carregada.
    """
    try:
        data = json.loads(request.body)
        import_type = data.get('type')
        payload = data.get('payload', [])

        # Otimização: A lista de processos já está na página. Buscamos apenas os clientes.
        todos_clientes = Cliente.objects.all().order_by('nome_completo')

        context = {
            'import_type': import_type,
            'csrf_token': get_token(request),
            'todos_clientes': todos_clientes,  # Apenas clientes são necessários aqui
        }
        dados_analisados = []

        if import_type == 'audiencias':
            nomes_no_json = set()
            for audiencia_data in payload:
                analise = {'partes': [], 'processo': {}, 'audiencia': {}}
                num_processo = audiencia_data.get('processoRecurso')
                processo_qs = Processo.objects.filter(numero_processo=num_processo)
                analise['processo'] = {'numero': num_processo, 'existe': processo_qs.exists(),
                                       'id': processo_qs.first().id if processo_qs.exists() else None}

                partes_raw = audiencia_data.get('partes', {})
                for polo, nomes in partes_raw.items():
                    for nome in nomes:
                        nome_limpo = nome.split('representado(a) por')[0].strip()
                        cliente_qs = Cliente.objects.filter(nome_completo__iexact=nome_limpo)
                        parte_info = {
                            'nome_original': nome,
                            'polo': polo,
                            'status': 'EXISTENTE' if cliente_qs.exists() else 'NOVO',
                            'cliente_id': cliente_qs.first().id if cliente_qs.exists() else None
                        }
                        analise['partes'].append(parte_info)

                tipo_audiencia_projudi = audiencia_data.get('tipoAudiencia', '')
                analise['audiencia'] = {
                    'data': audiencia_data.get('data'), 'hora': audiencia_data.get('hora'),
                    'tipo': tipo_audiencia_projudi, 'local': audiencia_data.get('localAudiencia'),
                    'situacao': audiencia_data.get('situacaoAudiencia'), 'modalidade': audiencia_data.get('modalidade'),
                }

                sugestao = TipoMovimentacao.objects.filter(nome__icontains='Audiência').first()
                analise['audiencia']['sugestao_tipo_id'] = sugestao.pk if sugestao else None
                dados_analisados.append(analise)

            context['dados_analisados'] = dados_analisados
            if import_type == 'audiencias':
                context['tipos_movimentacao_audiencia'] = TipoMovimentacao.objects.filter(
                    nome__icontains='audiência').order_by('nome')
            elif import_type == 'movimentacoes':
                context['todos_tipos_movimentacao'] = TipoMovimentacao.objects.all().order_by('nome')

            # Renderiza o mesmo template parcial, que foi ajustado para usar a lista de processos da página.
            html_preview = render_to_string('gestao/partials/_importacao_projudi_preview.html', context)
            return JsonResponse({'status': 'success', 'html_preview': html_preview})


        elif import_type == 'movimentacoes':
            movimentacoes_agrupadas = {}
            for mov_data in payload:
                chave = (mov_data.get('processoRecurso'), mov_data.get('dtPostagem'), mov_data.get('dataIntimacao'),
                         mov_data.get('prazo'))
                if chave not in movimentacoes_agrupadas:
                    movimentacoes_agrupadas[chave] = {'mov_data': mov_data, 'partes_intimadas': []}
                movimentacoes_agrupadas[chave]['partes_intimadas'].append(mov_data.get('parteIntimada'))

            for grupo in movimentacoes_agrupadas.values():
                mov_data = grupo['mov_data']
                analise = {'movimentacao': {}, 'processo': {}, 'partes': []}

                num_processo = mov_data.get('processoRecurso')
                processo_qs = Processo.objects.filter(numero_processo=num_processo)
                analise['processo'] = {'numero': num_processo, 'existe': processo_qs.exists(),
                                       'id': processo_qs.first().id if processo_qs.exists() else None}

                for nome_parte in grupo['partes_intimadas']:
                    nome_limpo = nome_parte.strip()
                    cliente_qs = Cliente.objects.filter(nome_completo__iexact=nome_limpo)
                    analise['partes'].append({
                        'nome': nome_limpo,
                        'existe': cliente_qs.exists(),
                        'cliente_id': cliente_qs.first().id if cliente_qs.exists() else None
                    })

                analise['movimentacao'] = {
                    'dtPostagem': mov_data.get('dtPostagem'),
                    'dataIntimacao': mov_data.get('dataIntimacao'),
                    'prazo': mov_data.get('prazo'),
                }
                dados_analisados.append(analise)

            context['dados_analisados'] = dados_analisados
            context['todos_tipos_movimentacao'] = TipoMovimentacao.objects.all().order_by('nome')

        else:
            return JsonResponse({'status': 'error', 'message': 'Tipo de arquivo JSON não reconhecido.'}, status=400)

        html_preview = render_to_string('gestao/partials/_importacao_projudi_preview.html', context)
        return JsonResponse({'status': 'success', 'html_preview': html_preview})

    except Exception as e:
        if settings.DEBUG:
            return JsonResponse({'status': 'error', 'message': f'Erro interno no servidor: {str(e)}'}, status=500)
        return JsonResponse({'status': 'error', 'message': 'Ocorreu um erro inesperado ao processar os dados.'},
                            status=500)


@require_POST
@login_required
@transaction.atomic
def processar_importacao_projudi(request):
    """
    Processa os dados conciliados, incluindo a vinculação manual a processos
    e clientes existentes e a edição de nomes.
    """
    try:
        import_type = request.POST.get('import_type')
        indices_a_importar = request.POST.getlist('importar_indice')

        for i in indices_a_importar:
            # --- 1. DETERMINAR O PROCESSO (NOVO, EXISTENTE OU VINCULADO) ---
            processo_action = request.POST.get(f'processo_{i}_action')
            num_processo_arquivo = request.POST.get(f'processo_{i}_numero')
            processo_obj = None

            if processo_action == 'vincular_existente':
                processo_id = request.POST.get(f'processo_{i}_id_vincular')
                if processo_id:
                    processo_obj = Processo.objects.get(pk=processo_id)
                    # Se o processo vinculado não tinha número, atualiza com o do arquivo
                    if not processo_obj.numero_processo and num_processo_arquivo:
                        processo_obj.numero_processo = num_processo_arquivo
                        processo_obj.save()

            if not processo_obj:  # Se a ação for 'do_arquivo' ou a vinculação falhar
                processo_obj, _ = Processo.objects.get_or_create(
                    numero_processo=num_processo_arquivo,
                    defaults={'advogado_responsavel': request.user, 'status_processo': 'ATIVO'}
                )

            # --- 2. PROCESSAR AS PARTES E A MOVIMENTAÇÃO ---
            if import_type == 'audiencias':
                clientes_principais_ids = request.POST.getlist(f'processo_{i}_cliente_principal')

                # Loop para processar todas as partes enviadas para este item
                for j in range(100):
                    parte_action = request.POST.get(f'processo_{i}_parte_{j}_action')
                    if not parte_action: break

                    cliente_obj = None
                    if parte_action == 'vincular_cliente':
                        cliente_id = request.POST.get(f'processo_{i}_parte_{j}_id_vincular')
                        if cliente_id: cliente_obj = Cliente.objects.get(pk=cliente_id)
                    else:  # 'usar_nome'
                        nome_editado = request.POST.get(f'processo_{i}_parte_{j}_nome_editado')
                        if nome_editado: cliente_obj, _ = Cliente.objects.get_or_create(nome_completo=nome_editado)

                    if cliente_obj:
                        is_cliente_principal = (str(cliente_obj.pk) in clientes_principais_ids)
                        polo = request.POST.get(f'processo_{i}_parte_{j}_polo')
                        tipo_participacao = 'AUTOR' if 'ativo' in polo.lower() or 'autor' in polo.lower() else 'REU'

                        ParteProcesso.objects.update_or_create(
                            processo=processo_obj, cliente=cliente_obj,
                            defaults={'tipo_participacao': tipo_participacao,
                                      'is_cliente_do_processo': is_cliente_principal}
                        )

                tipo_mov_pk = request.POST.get(f'audiencia_{i}_tipo_movimentacao')
                if tipo_mov_pk:
                    data_str = request.POST.get(f'audiencia_{i}_data')
                    hora_str = request.POST.get(f'audiencia_{i}_hora')
                    Movimentacao.objects.create(
                        processo=processo_obj,
                        titulo=request.POST.get(f'audiencia_{i}_titulo'),
                        tipo_movimentacao_id=tipo_mov_pk,
                        data_prazo_final=datetime.strptime(data_str, '%d/%m/%Y').date() if data_str else None,
                        hora_prazo=datetime.strptime(hora_str, '%H:%M').time() if hora_str else None,
                        detalhes=request.POST.get(f'audiencia_{i}_detalhes'),
                        responsavel=request.user, status='PENDENTE'
                    )

            elif import_type == 'movimentacoes':
                # Loop para processar todas as partes do grupo
                for j in range(100):
                    parte_action = request.POST.get(f'movimentacao_{i}_parte_{j}_action')
                    if not parte_action: break

                    cliente_obj = None
                    if parte_action == 'vincular_cliente':
                        cliente_id = request.POST.get(f'movimentacao_{i}_parte_{j}_id_vincular')
                        if cliente_id: cliente_obj = Cliente.objects.get(pk=cliente_id)
                    else:  # 'usar_nome'
                        nome_editado = request.POST.get(f'movimentacao_{i}_parte_{j}_nome_editado')
                        if nome_editado: cliente_obj, _ = Cliente.objects.get_or_create(nome_completo=nome_editado)

                    if cliente_obj:
                        ParteProcesso.objects.update_or_create(
                            processo=processo_obj, cliente=cliente_obj,
                            defaults={'tipo_participacao': 'AUTOR', 'is_cliente_do_processo': True}
                        )

                tipo_mov_pk = request.POST.get(f'movimentacao_{i}_tipo')
                if tipo_mov_pk:
                    tipo_mov_obj = TipoMovimentacao.objects.get(pk=tipo_mov_pk)
                    prazo_str = request.POST.get(f'movimentacao_{i}_prazo')
                    Movimentacao.objects.create(
                        processo=processo_obj,
                        titulo=f"Prazo: {tipo_mov_obj.nome}",
                        tipo_movimentacao=tipo_mov_obj,
                        data_prazo_final=datetime.strptime(prazo_str, '%d/%m/%Y').date() if prazo_str else None,
                        detalhes=f"Intimação via Projudi.\nData da Postagem: {request.POST.get(f'movimentacao_{i}_postagem')}\nData da Intimação: {request.POST.get(f'movimentacao_{i}_intimacao')}",
                        responsavel=request.user, status='PENDENTE'
                    )

        messages.success(request, 'Dados selecionados foram importados com sucesso!')
        return JsonResponse({'status': 'success'})

    except Exception as e:
        if settings.DEBUG:
            return JsonResponse({'status': 'error', 'message': f'Erro ao processar importação: {str(e)}'}, status=500)
        return JsonResponse({'status': 'error', 'message': 'Ocorreu um erro inesperado ao salvar os dados.'},
                            status=500)


@login_required
@staff_member_required  # Garante que apenas usuários da equipe possam acessar
def excluir_clientes_em_massa(request):
    """
    Exclui todos os clientes (ou pessoas) que não possuem nenhum processo
    ou serviço vinculado. Ação restrita a superusuários.
    """
    # Dupla verificação de segurança: apenas superusuários podem executar a ação.
    if not request.user.is_superuser:
        return HttpResponseForbidden("Você não tem permissão para executar esta ação.")

    if request.method == 'POST':
        # Filtra todos os Clientes que não têm participações em processos E não têm serviços.
        cadastros_para_excluir = Cliente.objects.annotate(
            num_processos=Count('participacoes'),
            num_servicos=Count('servicos')
        ).filter(
            num_processos=0,
            num_servicos=0
        )

        # Obtém a contagem de quantos serão excluídos ANTES de deletar.
        count = cadastros_para_excluir.count()

        if count > 0:
            cadastros_para_excluir.delete()
            return JsonResponse({
                'status': 'success',
                'message': f'{count} cadastros sem vínculos foram excluídos com sucesso.'
            })
        else:
            return JsonResponse({
                'status': 'info',
                'message': 'Nenhum cadastro sem vínculos foi encontrado para exclusão.'
            })

    # Redireciona se a requisição não for POST
    return redirect('gestao:lista_clientes')


@login_required
def global_search(request):
    """
    Realiza uma busca geral e sem acentos em múltiplos modelos
    e retorna os resultados em formato JSON para ser consumido por AJAX.
    """
    query = request.GET.get('q', '')
    results = []

    if len(query) > 2:  # A busca só é acionada com 3 ou mais caracteres
        unaccented_query = unidecode(query)

        # Busca em Processos
        processos = Processo.objects.filter(
            Q(numero_processo__icontains=query) |
            Q(descricao_caso__icontains=query)
        )[:5]
        for processo in processos:
            results.append({
                'text': f"{processo.descricao_caso|truncatechars:40}",
                'subtext': f"Proc. {processo.numero_processo}",
                'type': 'Processo',
                'icon': 'bi-folder-fill',
                'url': processo.get_absolute_url()
            })

        # Busca em Clientes e Pessoas (com anotação para busca sem acento)
        clientes = Cliente.objects.annotate(
            nome_unaccent=Func(F('nome_completo'), function='unaccent')
        ).filter(
            Q(nome_unaccent__icontains=unaccented_query) |
            Q(cpf_cnpj__icontains=query)
        )[:5]
        for cliente in clientes:
            # Distingue entre 'Cliente' e 'Pessoa' para o tipo
            tipo_cadastro = "Cliente" if cliente.is_cliente else "Pessoa"
            results.append({
                'text': cliente.nome_completo,
                'subtext': cliente.cpf_cnpj or "Documento não informado",
                'type': tipo_cadastro,
                'icon': 'bi-person-fill',
                'url': cliente.get_absolute_url()
            })

        # Busca em Serviços
        servicos = Servico.objects.filter(descricao__icontains=query)[:5]
        for servico in servicos:
            results.append({
                'text': servico.descricao,
                'subtext': f"Cliente: {servico.cliente.nome_completo}",
                'type': 'Serviço',
                'icon': 'bi-briefcase-fill',
                'url': servico.get_absolute_url()
            })

    return JsonResponse(results, safe=False)


logger = logging.getLogger(__name__)


# Função auxiliar
def remove_accents(input_str):
    if not input_str: return ""
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])


@login_required
def update_agenda_partial(request):
    """
    VERSÃO DEFINITIVA - CORRIGE O ERRO 500 EM AUDIÊNCIAS
    - Trata a lista vazia ANTES da paginação para evitar o erro "Página menor que 1".
    - Mantém a lógica correta do Dashboard de exibir todas as pendências do usuário.
    """
    try:
        list_type = request.GET.get('list_type', 'audiencias')
        page_number = request.GET.get('page', 1)
        per_page = int(request.GET.get('per_page', 5))

        hoje = timezone.now().date()
        usuario = request.user

        filtro_processos_usuario = Q(processo__advogado_responsavel=usuario) | Q(processo__advogados_envolvidos=usuario)

        base_query = Movimentacao.objects.filter(
            (Q(responsavel=usuario) | filtro_processos_usuario),
            status__in=['PENDENTE', 'EM_ANDAMENTO'],
            data_prazo_final__gt=hoje,
        ).select_related(
            'processo', 'tipo_movimentacao'
        ).prefetch_related(
            'processo__partes__cliente'
        ).distinct().order_by('processo__numero_processo', 'data_prazo_final', 'hora_prazo')

        # Filtra entre audiências e prazos
        all_items = []
        tipos_de_audiencia = ['audiencia', 'audiência', 'conciliação', 'conciliacao', 'instrução', 'instrucao']
        for mov in base_query:
            is_audiencia = any(termo in remove_accents(mov.titulo.lower()) for termo in tipos_de_audiencia) or \
                           (mov.tipo_movimentacao and any(
                               termo in remove_accents(mov.tipo_movimentacao.nome.lower()) for termo in
                               tipos_de_audiencia))

            if (list_type == 'audiencias' and is_audiencia) or (list_type == 'prazos' and not is_audiencia):
                all_items.append(mov)

        # =======================================================================
        # === CORREÇÃO CRÍTICA: Tratar a lista vazia ANTES de paginar =========
        # Se não houver itens (ex: nenhuma audiência futura), nós já paramos
        # aqui e retornamos uma lista vazia, evitando o erro de paginação.
        # =======================================================================
        paginator = Paginator(all_items, per_page)
        page_obj = paginator.get_page(page_number)

        # Se a página atual não tiver itens (seja por ser uma página vazia ou a lista total ser vazia)
        # nós renderizamos o template com a lista vazia e retornamos.
        if not page_obj.object_list:
            partial_template = (
                'gestao/partials/_item_agenda_audiencia_lista.html' if list_type == 'audiencias' else 'gestao/partials/_item_pendencia.html')
            html_content = render_to_string(
                'gestao/partials/_agenda_list_with_pagination.html',
                {'page_obj': page_obj, 'list_type': list_type, 'per_page': per_page,
                 'partial_template': partial_template, 'hoje': hoje},
                request=request
            )
            return JsonResponse({'success': True, 'html': html_content})

        # Prepara a lista final de itens para o template (apenas se houver itens)
        lista_final = []
        for mov in page_obj.object_list:
            try:
                numero_processo_str = mov.processo.numero_processo or "Proc. s/ Nº"
                nome_parte_str = mov.processo.get_cliente_principal_display()

                item_data = {
                    'pk': mov.pk, 'data': mov.data_prazo_final, 'hora': mov.hora_prazo, 'titulo': mov.titulo,
                    'status': mov.get_status_display(), 'hoje': hoje, 'link_referencia': mov.link_referencia
                }

                if list_type == 'audiencias':
                    item_data['tipo'] = 'audiencia'
                    item_data.update({
                        'numero_processo': numero_processo_str,
                        'nome_parte': nome_parte_str,
                        'processo_pk': mov.processo.pk
                    })
                else:  # Prazos
                    item_data['tipo'] = 'prazo_processo'
                    item_data.update({'objeto_str': f"Proc: {numero_processo_str} - {nome_parte_str}"})

                lista_final.append(item_data)
            except Exception as e:
                logger.error(f"FALHA AO PROCESSAR ITEM DA AGENDA (Movimentacao ID: {mov.pk}): {e}")
                continue

        # Recria o Paginator com a lista processada (lista_final)
        paginator = Paginator(lista_final, per_page)
        page_obj = paginator.get_page(page_number)

        partial_template = (
            'gestao/partials/_item_agenda_audiencia_lista.html' if list_type == 'audiencias' else 'gestao/partials/_item_pendencia.html')

        html_content = render_to_string(
            'gestao/partials/_agenda_list_with_pagination.html',
            {
                'page_obj': page_obj, 'list_type': list_type,
                'per_page': per_page, 'partial_template': partial_template,
                'hoje': hoje
            },
            request=request
        )
        return JsonResponse({'success': True, 'html': html_content})

    except Exception as e:
        logger.error(f"ERRO CRÍTICO NA VIEW update_agenda_partial: {e}")
        return JsonResponse({'success': False, 'error': f"Ocorreu um erro interno: {e}"}, status=500)


@require_POST
@login_required
def concluir_item_agenda_ajax(request, tipo, pk):
    """
    Marca um item da agenda (Movimentacao ou MovimentacaoServico) como 'CONCLUIDA'
    e retorna uma resposta JSON.
    """
    try:
        if tipo == 'processo':
            item = get_object_or_404(Movimentacao, pk=pk, responsavel=request.user)
        elif tipo == 'servico_task':
            item = get_object_or_404(MovimentacaoServico, pk=pk, responsavel=request.user)
        else:
            return JsonResponse({'success': False, 'error': 'Tipo de item inválido'}, status=400)

        item.status = 'CONCLUIDA'
        item.save()

        return JsonResponse({'success': True})

    except Http404:
        return JsonResponse({'success': False, 'error': 'Item não encontrado ou você não tem permissão'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def painel_despesas(request):
    """
    Exibe um painel dedicado ao gerenciamento de despesas.
    """
    hoje = timezone.now().date()
    primeiro_dia_mes = hoje.replace(day=1)
    ultimo_dia_mes = (primeiro_dia_mes + relativedelta(months=1)) - timedelta(days=1)

    # Anota todos os lançamentos de despesa com seu status calculado
    despesas = LancamentoFinanceiro.objects.filter(tipo='DESPESA').annotate(
        total_pago=Coalesce(Sum('pagamentos__valor_pago'), Decimal(0), output_field=DecimalField())
    ).annotate(
        saldo_devedor_calc=F('valor') - F('total_pago'),
        status_calculado=Case(
            When(valor__lte=F('total_pago'), then=Value('PAGO')),
            When(data_vencimento__lt=hoje, then=Value('ATRASADO')),
            default=Value('A_PAGAR'),
            output_field=CharField()
        )
    )

    # KPI: Total Vencido
    total_vencido = despesas.filter(
        status_calculado='ATRASADO'
    ).aggregate(total=Coalesce(Sum('saldo_devedor_calc'), Decimal(0)))['total']

    # KPI: A Pagar este Mês
    a_pagar_mes = despesas.filter(
        status_calculado='A_PAGAR',
        data_vencimento__range=[primeiro_dia_mes, ultimo_dia_mes]
    ).aggregate(total=Coalesce(Sum('saldo_devedor_calc'), Decimal(0)))['total']

    # Aqui você pode adicionar no futuro a lógica para popular as tabelas
    # de lançamentos pontuais e recorrentes que estão nas abas.

    context = {
        'titulo_pagina': "Gestão de Despesas",
        'total_vencido': total_vencido,
        'a_pagar_mes': a_pagar_mes,
    }
    return render(request, 'gestao/financeiro/painel_despesas.html', context)


def global_search(request):
    """
    Realiza uma busca geral e sem acentos em múltiplos modelos
    e retorna os resultados em formato JSON para ser consumido por AJAX.
    """
    query = request.GET.get('q', '')
    results = []

    if len(query) > 2:  # A busca só é acionada com 3 ou mais caracteres
        unaccented_query = unidecode(query)

        # Busca em Processos
        processos = Processo.objects.filter(
            Q(numero_processo__icontains=query) |
            Q(descricao_caso__icontains=query)
        )[:5]
        for processo in processos:
            results.append({
                'text': f"{processo.descricao_caso|truncatechars:40}",
                'subtext': f"Proc. {processo.numero_processo}",
                'type': 'Processo',
                'icon': 'bi-folder-fill',
                'url': processo.get_absolute_url()
            })

        # Busca em Clientes e Pessoas (com anotação para busca sem acento)
        clientes = Cliente.objects.annotate(
            nome_unaccent=Func(F('nome_completo'), function='unaccent')
        ).filter(
            Q(nome_unaccent__icontains=unaccented_query) |
            Q(cpf_cnpj__icontains=query)
        )[:5]
        for cliente in clientes:
            # Distingue entre 'Cliente' e 'Pessoa' para o tipo
            tipo_cadastro = "Cliente" if cliente.is_cliente else "Pessoa"
            results.append({
                'text': cliente.nome_completo,
                'subtext': cliente.cpf_cnpj or "Documento não informado",
                'type': tipo_cadastro,
                'icon': 'bi-person-fill',
                'url': cliente.get_absolute_url()
            })

        # Busca em Serviços
        servicos = Servico.objects.filter(descricao__icontains=query)[:5]
        for servico in servicos:
            results.append({
                'text': servico.descricao,
                'subtext': f"Cliente: {servico.cliente.nome_completo}",
                'type': 'Serviço',
                'icon': 'bi-briefcase-fill',
                'url': servico.get_absolute_url()
            })

    return JsonResponse(results, safe=False)
