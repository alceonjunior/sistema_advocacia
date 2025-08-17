# -*- coding: utf-8 -*-

# ==============================================================================
# IMPORTS
# ==============================================================================
# Otimização: Imports foram reorganizados por tipo (Standard Library, Third-Party, Django, Local App)
# e duplicatas/redundâncias foram removidas para maior clareza e eficiência.
from __future__ import annotations

# --- Standard Library ---
import json
import logging
import locale
import itertools
import re
import calendar
from datetime import date, datetime, timedelta
from decimal import Decimal
from operator import attrgetter
import unicodedata

# --- Third-Party Libraries ---
from dateutil.relativedelta import relativedelta
from django.forms import inlineformset_factory
from unidecode import unidecode

# --- Django Core ---
from django.apps import apps
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator
from django.db import transaction
from django import forms
from django.db.models import (
    Q, Case, CharField, DateField, DecimalField, F, OuterRef, Subquery, Sum,
    Value, When, Func, Count,
)
from django.db.models.functions import Coalesce
from django.http import (
    Http404, HttpResponse, HttpResponseBadRequest, JsonResponse, HttpResponseForbidden, HttpRequest
)
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404, redirect, render
from django.template import Context, Template
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
#from weasyprint import HTML
from decimal import Decimal, ROUND_HALF_UP

# --- Local Application ---
from . import models
from .calculators import CalculadoraMonetaria
from .encoders import DecimalEncoder
from .filters import ClienteFilter, ProcessoFilter, ServicoFilter
from .forms import (
    AreaProcessoForm, CalculoForm, ClienteForm, ClienteModalForm,
    ContratoHonorariosForm, CustomUserChangeForm, CustomUserCreationForm,
    DocumentoForm, EscritorioConfiguracaoForm, IncidenteForm,
    ModeloDocumentoForm, MovimentacaoForm, MovimentacaoServicoForm,
    PagamentoForm, ParteProcessoFormSet, ProcessoCreateForm, ProcessoForm,
    RecursoForm, ServicoConcluirForm, ServicoEditForm, ServicoForm,
    TipoAcaoForm, TipoServicoForm, UsuarioPerfilForm, GerarDocumentoForm,
    LancamentoFinanceiroForm, DespesaRecorrenteVariavelForm,
    DespesaRecorrenteFixaForm, DespesaPontualForm, DespesaTipoForm, CalculoJudicialForm, FaseCalculoFormSet,
    FaseCalculoForm, LancamentoFormSet, CorrecaoFormSet, JurosFormSet, TipoMovimentacaoForm, TipoMovimentacaoAddForm,
    TipoMovimentacaoEditForm,
)
from .models import (
    AreaProcesso, CalculoJudicial, FaseCalculo, Cliente, Documento, EscritorioConfiguracao,
    Incidente, LancamentoFinanceiro, ModeloDocumento, Movimentacao,
    MovimentacaoServico, Pagamento, Processo, Recurso, Servico, TipoAcao,
    TipoServico, UsuarioPerfil, ContratoHonorarios, ParteProcesso, TipoMovimentacao, CalculoLancamento, CalculoRascunho,
)
from .services.indices.catalog import INDICE_CATALOG, public_catalog_for_api
from .services.indices.resolver import ServicoIndices, calcular
from .nfse_service import NFSEService
from .services.calculo import CalculoEngine
from .utils import data_por_extenso, valor_por_extenso
from decimal import InvalidOperation

from decimal import InvalidOperation
from typing import Any, Dict, List

from django.http import  HttpRequest
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required

from .services.indices.providers import ServicoIndices
from .services.indices.catalog import INDICE_CATALOG

# ==============================================================================
# CONFIGURAÇÕES E CONSTANTES GLOBAIS
# ==============================================================================

# Configura o logger para registrar erros e informações importantes.
logger = logging.getLogger(__name__)

# Mapeamento de permissões para exibição estruturada na interface de configurações.
# Facilita a manutenção e a apresentação das permissões aos administradores.
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
        {'codename': 'change_escritorioconfiguracao', 'label': 'Alterar Configurações'},
        {'codename': 'view_user', 'label': 'Visualizar Usuários'},
        {'codename': 'add_user', 'label': 'Adicionar Usuários'},
        {'codename': 'change_user', 'label': 'Editar Usuários'},
        {'codename': 'delete_user', 'label': 'Excluir Usuários'},
    ]
}


# ==============================================================================
# FUNÇÕES AUXILIARES (HELPERS)
# ==============================================================================

def _preparar_dados_financeiros(lancamentos_qs):
    """
    Agrupa lançamentos financeiros por status (regulares vs. inadimplentes) e,
    dentro de cada grupo, por ano e mês de vencimento.

    Args:
        lancamentos_qs (QuerySet): QuerySet de objetos LancamentoFinanceiro.

    Returns:
        tuple: Uma tupla contendo dois dicionários:
               (regulares_agrupados, inadimplentes_agrupados).
    """
    hoje = timezone.now().date()

    # Anota o total pago e o status calculado diretamente no queryset.
    lancamentos_com_status = lancamentos_qs.annotate(
        total_pago_calc=Coalesce(Sum('pagamentos__valor_pago'), Decimal(0))
    ).annotate(
        status_calc=Case(
            When(valor__lte=F('total_pago_calc'), then=Value('PAGO')),
            When(data_vencimento__lt=hoje, then=Value('ATRASADO')),
            When(total_pago_calc__gt=0, then=Value('PARCIAL')),
            default=Value('A_PAGAR'),
            output_field=CharField()
        )
    )

    status_map = {
        'PAGO': 'Pago',
        'ATRASADO': 'Atrasado',
        'PARCIAL': 'Parcialmente Pago',
        'A_PAGAR': 'A Pagar',
    }

    lancamentos_regulares = []
    lancamentos_inadimplentes = []

    for lanc in lancamentos_com_status:
        # Adiciona o status display para uso no template.
        lanc.status_display = status_map.get(lanc.status_calc, '')

        if lanc.status_calc == 'ATRASADO':
            lancamentos_inadimplentes.append(lanc)
        else:
            lancamentos_regulares.append(lanc)

    def _agrupar(lancamentos):
        """Função interna para agrupar uma lista de lançamentos."""
        # Garante a ordenação por data para o itertools.groupby funcionar corretamente.
        sorted_lancamentos = sorted(lancamentos, key=attrgetter('data_vencimento'))
        grupos = {}
        for ano, itens_ano in itertools.groupby(sorted_lancamentos, key=attrgetter('data_vencimento.year')):
            grupos[ano] = {}
            for mes, itens_mes in itertools.groupby(itens_ano,
                                                    key=lambda l: l.data_vencimento.strftime('%B').capitalize()):
                grupos[ano][mes] = list(itens_mes)
        return grupos

    return _agrupar(lancamentos_regulares), _agrupar(lancamentos_inadimplentes)


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


def _perform_calculation(dados):
    """
    Encapsula a lógica de cálculo judicial, separando-a da view.

    Args:
        dados (dict): Dicionário com os dados do formulário de cálculo.

    Returns:
        tuple: Uma tupla (resultado, erro). Se o cálculo for bem-sucedido,
               'resultado' contém o dicionário com os valores e 'erro' é None.
               Caso contrário, 'resultado' é None e 'erro' contém a mensagem.
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
            juros_taxa=dados.get('juros_taxa') or 0,
            juros_tipo=dados.get('juros_tipo', 'SIMPLES'),
            juros_periodo=dados.get('juros_periodo', 'MENSAL'),
            juros_data_inicio=dados.get('juros_data_inicio'),
            juros_data_fim=dados.get('juros_data_fim'),
            correcao_pro_rata=dados.get('correcao_pro_rata', False),
            multa_taxa=dados.get('multa_percentual') or 0,
            multa_sobre_juros=dados.get('multa_sobre_juros', False),
            honorarios_taxa=dados.get('honorarios_percentual') or 0
        )
        resultado['resumo']['indice_display_name'] = indice_selecionado_display
        if not dados.get('gerar_memorial'):
            resultado['memorial'] = None
        return resultado, None
    except Exception as e:
        logger.error(f"Erro ao executar cálculo judicial: {e}", exc_info=True)
        return None, f"Ocorreu um erro inesperado durante o cálculo: {e}"


def remove_accents(input_str):
    """
    Remove acentos de uma string, útil para buscas case-insensitive e accent-insensitive.

    Args:
        input_str (str): A string de entrada.

    Returns:
        str: A string sem acentos.
    """
    if not input_str:
        return ""
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])


# ==============================================================================
# SEÇÃO: DASHBOARD E VIEWS PRINCIPAIS
# ==============================================================================

@login_required
def dashboard(request):
    """
    Renderiza o dashboard principal do usuário.

    Esta view agrega informações vitais para o dia a dia do advogado, incluindo:
    - KPIs (Indicadores Chave de Performance) sobre processos e serviços ativos.
    - "Foco do Dia": Tarefas e prazos vencidos ou que vencem hoje.
    - "Visão Geral da Agenda": Próximas audiências, prazos e tarefas.
    - "Pulso do Escritório": As últimas movimentações nos processos do usuário.

    A lógica foi ajustada para que o usuário veja todos os casos em que está
    envolvido, seja como responsável principal ou como colaborador.
    """
    # --- 1. Configurações Iniciais e Consultas de Base ---
    usuario = request.user
    hoje = timezone.now().date()
    status_aberto = ['PENDENTE', 'EM_ANDAMENTO']

    # Filtro que inclui processos onde o usuário é responsável OU colaborador.
    # .distinct() evita duplicatas se o usuário for ambos.
    filtro_processos_usuario = Q(advogado_responsavel=usuario) | Q(advogados_envolvidos=usuario)
    processos_usuario_qs = Processo.objects.filter(filtro_processos_usuario).distinct()

    # --- 2. Consultas para KPIs e Listas do Dashboard ---
    processos_ativos_qs = processos_usuario_qs.filter(status_processo='ATIVO')
    servicos_ativos_qs = Servico.objects.filter(responsavel=usuario, concluido=False)
    ultimas_movimentacoes = Movimentacao.objects.filter(
        processo__in=processos_usuario_qs
    ).select_related('processo', 'responsavel').order_by('-data_criacao')[:5]

    # --- 3. Lógica para o "Foco do Dia" (Vencidos e Para Hoje) ---
    agenda_foco = []

    # Prazos e audiências de processos (apenas do responsável pela tarefa)
    movs_processo_foco = Movimentacao.objects.filter(
        responsavel=usuario, status__in=status_aberto, data_prazo_final__lte=hoje
    ).select_related('processo')
    for mov in movs_processo_foco:
        agenda_foco.append({
            'pk': mov.pk, 'tipo': 'processo', 'data': mov.data_prazo_final,
            'hora': mov.hora_prazo, 'titulo': mov.titulo,
            'objeto_str': f"Proc: {mov.processo.numero_processo}",
            'url': reverse('gestao:detalhe_processo', args=[mov.processo.pk])
        })

    # Tarefas de serviços (apenas do responsável pela tarefa)
    movs_servico_foco = MovimentacaoServico.objects.filter(
        responsavel=usuario, status__in=status_aberto, prazo_final__lte=hoje
    ).select_related('servico__cliente')
    for tarefa in movs_servico_foco:
        agenda_foco.append({
            'pk': tarefa.pk, 'tipo': 'servico_task', 'data': tarefa.prazo_final,
            'hora': None, 'titulo': tarefa.titulo,
            'objeto_str': f"Serviço: {tarefa.servico.descricao}",
            'url': reverse('gestao:detalhe_servico', args=[tarefa.servico.pk])
        })

    # Prazo final de serviços (apenas do responsável pelo serviço)
    servicos_prazo_foco = Servico.objects.filter(
        responsavel=usuario, concluido=False, prazo__lte=hoje
    ).select_related('cliente')
    for servico in servicos_prazo_foco:
        agenda_foco.append({
            'pk': servico.pk, 'tipo': 'servico_main', 'data': servico.prazo,
            'hora': None, 'titulo': "Prazo final do serviço",
            'objeto_str': servico.descricao,
            'url': reverse('gestao:detalhe_servico', args=[servico.pk])
        })

    # Ordena e separa os itens do "Foco do Dia"
    agenda_foco.sort(key=lambda x: (x['data'], x['hora'] or datetime.min.time()))
    itens_vencidos = [item for item in agenda_foco if item['data'] < hoje]
    itens_para_hoje = [item for item in agenda_foco if item['data'] == hoje]

    # --- 4. Contexto para o Template ---
    context = {
        'titulo_pagina': 'Dashboard',
        'hoje': hoje,
        # KPIs
        'processos_ativos_count': processos_ativos_qs.count(),
        'servicos_ativos_count': servicos_ativos_qs.count(),
        'total_pendencias': len(agenda_foco),
        # Listas para o Dashboard
        'itens_vencidos': itens_vencidos,
        'itens_para_hoje': itens_para_hoje,
        'ultimas_movimentacoes': ultimas_movimentacoes,
        # Listas completas para os Modais Gerenciais
        'lista_processos_ativos': processos_ativos_qs,
        'lista_servicos_ativos': servicos_ativos_qs,
        'lista_total_pendencias': agenda_foco,
        # Formulários para os modais de edição rápida
        'form_movimentacao': MovimentacaoForm(initial={'responsavel': usuario}),
        'form_movimentacao_servico': MovimentacaoServicoForm(),
        'form_edit': ServicoEditForm(),
    }

    return render(request, 'gestao/dashboard.html', context)


@login_required
def global_search(request):
    """
    Realiza uma busca global e assíncrona em todo o sistema.

    Busca por clientes, processos e serviços com base no termo fornecido,
    retornando um JSON formatado para exibição em um dropdown de resultados.
    A busca é otimizada para performance, limitando o número de resultados.
    """
    query = request.GET.get('q', '').strip()
    results = []

    if len(query) >= 3:
        # Utiliza unidecode para buscas que ignoram acentos.
        unaccented_query = unidecode(query)

        # 1. Busca em Clientes (por nome ou CPF/CNPJ)
        clientes_qs = Cliente.objects.annotate(
            nome_unaccent=Func(F('nome_completo'), function='unaccent')
        ).filter(
            Q(nome_unaccent__icontains=unaccented_query) | Q(cpf_cnpj__icontains=query)
        ).select_related('perfil').prefetch_related('participacoes__processo')[:5]

        for cliente in clientes_qs:
            processos_do_cliente = [
                {
                    'text': f"Proc. {p.processo.numero_processo or 'N/I'}",
                    'url': p.processo.get_absolute_url()
                }
                for p in cliente.participacoes.all() if p.processo
            ]
            results.append({
                'text': cliente.nome_completo,
                'subtext': cliente.cpf_cnpj or "Pessoa",
                'type': 'Cliente', 'icon': 'bi-person-fill',
                'url': cliente.get_absolute_url(),
                'children': processos_do_cliente
            })

        # 2. Busca em Processos (por número ou descrição)
        processos_qs = Processo.objects.filter(
            Q(numero_processo__icontains=query) | Q(descricao_caso__icontains=query)
        ).exclude(partes__cliente__in=clientes_qs).select_related('advogado_responsavel')[:5]

        for processo in processos_qs:
            results.append({
                'text': f"Proc. {processo.numero_processo or 'N/I'}",
                'subtext': processo.descricao_caso,
                'type': 'Processo', 'icon': 'bi-folder-fill',
                'url': processo.get_absolute_url()
            })

        # 3. Busca em Serviços (por descrição ou nome do cliente)
        servicos_qs = Servico.objects.filter(
            Q(descricao__icontains=query) | Q(cliente__nome_completo__icontains=query)
        ).select_related('cliente')[:5]

        for servico in servicos_qs:
            results.append({
                'text': servico.descricao,
                'subtext': f"Cliente: {servico.cliente.nome_completo}",
                'type': 'Serviço', 'icon': 'bi-briefcase-fill',
                'url': servico.get_absolute_url()
            })

    return JsonResponse(results, safe=False)


# ==============================================================================
# SEÇÃO: PROCESSOS (LISTAGEM, DETALHES, CRUD)
# ==============================================================================

@login_required
def lista_processos(request):
    """
    Exibe a lista paginada e filtrável de processos.

    A view inclui:
    - Filtros por status, cliente, tipo de ação, etc.
    - Estatísticas gerais (total, ativos, suspensos, arquivados).
    - Anotação do próximo prazo pendente para cada processo.
    - Suporte a requisições AJAX para atualização parcial da lista.
    """
    # Apenas superusuários veem todos; demais usuários veem apenas os seus.
    if request.user.is_superuser:
        base_queryset = Processo.objects.all()
    else:
        base_queryset = Processo.objects.filter(
            Q(advogado_responsavel=request.user) | Q(advogados_envolvidos=request.user)
        ).distinct()

    # Subquery para buscar a data do próximo prazo não concluído.
    proximo_prazo_subquery = Movimentacao.objects.filter(
        processo=OuterRef('pk'),
        status__in=['PENDENTE', 'EM_ANDAMENTO'],
        data_prazo_final__isnull=False
    ).order_by('data_prazo_final').values('data_prazo_final')[:1]

    # Otimização: Usa select_related, prefetch_related e a subquery anotada.
    annotated_queryset = base_queryset.annotate(
        proximo_prazo=Subquery(proximo_prazo_subquery, output_field=DateField())
    ).select_related(
        'tipo_acao__area', 'advogado_responsavel'
    ).prefetch_related('partes__cliente')

    processo_filter = ProcessoFilter(request.GET, queryset=annotated_queryset)

    # Lógica para requisições AJAX (HTMX/Fetch)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'gestao/partials/_lista_processos_partial.html', {
            'filter': processo_filter,
            'today': date.today()
        })

    # Estatísticas para os cards no topo da página.
    stats = {
        'total': base_queryset.count(),
        'ativos': base_queryset.filter(status_processo='ATIVO').count(),
        'suspensos': base_queryset.filter(status_processo='SUSPENSO').count(),
        'arquivados': base_queryset.filter(status_processo='ARQUIVADO').count(),
    }

    context = {
        'titulo_pagina': 'Meus Processos',
        'filter': processo_filter,
        'stats': stats,
        'today': date.today()
    }
    return render(request, 'gestao/lista_processos.html', context)


@login_required
def detalhe_processo(request, pk):
    """
    Exibe o painel de detalhes completo de um processo específico.

    Esta view centraliza todas as informações de um processo, incluindo:
    - Dados gerais do processo.
    - Partes envolvidas.
    - Histórico de movimentações (com cálculo de dias restantes/vencidos).
    - Detalhes financeiros (contratos, lançamentos, pagamentos).
    - Documentos, recursos e incidentes associados.
    - Formulários para adicionar novas informações (movimentações, etc.).
    """
    # Otimização: prefetch_related e select_related para reduzir queries.
    processo = get_object_or_404(
        Processo.objects.prefetch_related(
            'partes__cliente', 'documentos', 'movimentacoes__responsavel', 'movimentacoes__tipo_movimentacao',
            'recursos', 'incidentes', 'advogados_envolvidos', 'lancamentos__pagamentos'
        ).select_related('tipo_acao__area', 'advogado_responsavel'),
        pk=pk
    )

    # --- Lógica para requisições POST (submissão de formulários da página) ---
    if request.method == 'POST':
        # Âncora para redirecionar o usuário à aba correta após a ação.
        redirect_anchor = ''
        if 'submit_movimentacao' in request.POST:
            form = MovimentacaoForm(request.POST)
            if form.is_valid():
                movimentacao = form.save(commit=False)
                movimentacao.processo = processo
                movimentacao.save()
                messages.success(request, "Movimentação adicionada com sucesso.")
                redirect_anchor = '#movimentacoes-pane'
        # Adicionar outras lógicas de POST (recurso, incidente) aqui se necessário.

        redirect_url = f"{reverse('gestao:detalhe_processo', args=[pk])}{redirect_anchor}"
        return redirect(redirect_url)

    # --- Lógica para requisições GET (exibição da página) ---
    # Prepara dados das movimentações com cálculo de dias.
    movimentacoes = processo.movimentacoes.all().order_by('-data_criacao')
    today = timezone.now().date()
    for mov in movimentacoes:
        mov.dias_restantes = (mov.data_prazo_final - today).days if mov.data_prazo_final else None

    # Prepara dados financeiros.
    lancamentos_qs = processo.lancamentos.all()
    regulares_agrupados, inadimplentes_agrupados = _preparar_dados_financeiros(lancamentos_qs)
    valor_total_contratado = lancamentos_qs.aggregate(total=Sum('valor'))['total'] or Decimal('0.00')
    total_recebido = Pagamento.objects.filter(lancamento__in=lancamentos_qs).aggregate(total=Sum('valor_pago'))[
                         'total'] or Decimal('0.00')

    # Prepara dados para o cálculo de prazo no frontend.
    tipos_movimentacao = TipoMovimentacao.objects.all()
    dados_tipos_movimentacao = {
        tm.id: {'dias_prazo': tm.sugestao_dias_prazo, 'tipo_contagem': tm.tipo_contagem_prazo}
        for tm in tipos_movimentacao if tm.sugestao_dias_prazo is not None
    }

    context = {
        'titulo_pagina': f"Processo {processo.numero_processo}",
        'processo': processo,
        'movimentacoes': movimentacoes,
        'lancamentos_regulares_agrupados': regulares_agrupados,
        'lancamentos_inadimplentes_agrupados': inadimplentes_agrupados,
        'todos_modelos': ModeloDocumento.objects.all().order_by('titulo'),
        'form_movimentacao': MovimentacaoForm(initial={'responsavel': request.user}),
        'dados_tipos_movimentacao_json': json.dumps(dados_tipos_movimentacao),
        'form_recurso': RecursoForm(),
        'form_incidente': IncidenteForm(),
        'form_pagamento': PagamentoForm(),
        'resumo_financeiro_processo': {
            'valor_total_contratado': valor_total_contratado,
            'total_recebido': total_recebido,
            'saldo_devedor': valor_total_contratado - total_recebido,
        }
    }

    # Evita cache para garantir que os dados estejam sempre atualizados.
    response = render(request, 'gestao/detalhe_processo.html', context)
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


@login_required
def adicionar_processo(request):
    """
    Renderiza e processa o formulário de criação de um novo processo.

    Utiliza um formset para permitir a adição de múltiplas partes (autores, réus)
    juntamente com os dados principais do processo em uma única submissão.
    """
    if request.method == 'POST':
        form = ProcessoCreateForm(request.POST)
        formset = ParteProcessoFormSet(request.POST, prefix='partes')
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                processo = form.save()
                formset.instance = processo
                formset.save()
            messages.success(request, f"Processo {processo.numero_processo} criado com sucesso!")
            return redirect('gestao:detalhe_processo', pk=processo.pk)
    else:
        form = ProcessoCreateForm(initial={'advogado_responsavel': request.user})
        formset = ParteProcessoFormSet(prefix='partes', queryset=ParteProcesso.objects.none())

    # Prepara dados de clientes para o seletor (Select2).
    all_clients = Cliente.objects.all().order_by('nome_completo')
    clients_data = [{"id": c.pk, "text": str(c)} for c in all_clients]

    context = {
        'titulo_pagina': 'Adicionar Novo Processo',
        'form': form,
        'formset': formset,
        'all_clients_json': json.dumps(clients_data),
        'form_cliente_modal': ClienteModalForm(),
    }
    return render(request, 'gestao/adicionar_processo.html', context)


@login_required
def editar_processo(request, pk):
    """
    Renderiza e processa o formulário de edição de um processo existente.

    Permite a alteração dos dados gerais do processo e também o gerenciamento
    de advogados colaboradores (adicionar/remover).
    """
    processo = get_object_or_404(Processo, pk=pk)

    if request.method == 'POST':
        form = ProcessoForm(request.POST, instance=processo)
        if form.is_valid():
            form.save()
            messages.success(request, "Processo atualizado com sucesso!")
            return redirect('gestao:detalhe_processo', pk=processo.pk)
    else:
        form = ProcessoForm(instance=processo)

    # Lógica para o componente de gerenciamento de colaboradores.
    colaboradores_no_processo = processo.advogados_envolvidos.all()
    advogado_responsavel_id = processo.advogado_responsavel.id if processo.advogado_responsavel else None

    colaboradores_disponiveis = User.objects.filter(is_active=True).exclude(
        pk__in=[c.pk for c in colaboradores_no_processo]
    )
    if advogado_responsavel_id:
        colaboradores_disponiveis = colaboradores_disponiveis.exclude(pk=advogado_responsavel_id)

    context = {
        'titulo_pagina': f'Editar Processo {processo.numero_processo}',
        'form': form,
        'processo': processo,
        'colaboradores_no_processo': colaboradores_no_processo,
        'colaboradores_disponiveis': colaboradores_disponiveis,
    }
    return render(request, 'gestao/editar_processo.html', context)


@require_POST
@login_required
def arquivar_processo(request, pk):
    """Muda o status de um processo para 'ARQUIVADO'."""
    processo = get_object_or_404(Processo, pk=pk)
    processo.status_processo = 'ARQUIVADO'
    processo.save()
    messages.info(request, f"Processo {processo.numero_processo} foi arquivado.")
    return redirect('gestao:lista_processos')


@require_POST
@login_required
def desarquivar_processo(request, pk):
    """Muda o status de um processo 'ARQUIVADO' de volta para 'ATIVO'."""
    processo = get_object_or_404(Processo, pk=pk)
    if processo.status_processo == 'ARQUIVADO':
        processo.status_processo = 'ATIVO'
        processo.save()
        messages.info(request, f"Processo {processo.numero_processo} foi reativado.")
    return redirect('gestao:detalhe_processo', pk=pk)


# ==============================================================================
# SEÇÃO: PARTES DO PROCESSO (AJAX)
# ==============================================================================

@login_required
def gerenciar_partes(request, processo_pk):
    """
    Gerencia (adiciona/edita/remove) as partes de um processo via AJAX.

    Esta view é projetada para ser chamada a partir de um modal, retornando
    JSON para indicar sucesso ou HTML com erros para re-renderização do formulário.
    """
    processo = get_object_or_404(Processo.objects.prefetch_related('partes__cliente'), pk=processo_pk)

    if request.method == 'POST':
        formset = ParteProcessoFormSet(request.POST, instance=processo, prefix='partes')
        if formset.is_valid():
            formset.save()
            return JsonResponse({'success': True})
        else:
            # Se inválido, renderiza o formset com erros e devolve o HTML.
            context = {'processo': processo, 'formset': formset, 'is_modal': True}
            form_html = render_to_string('gestao/gerenciar_partes.html', context, request=request)
            return JsonResponse({'success': False, 'form_html': form_html}, status=400)

    # Requisição GET: apenas exibe o formulário.
    formset = ParteProcessoFormSet(instance=processo, prefix='partes')
    context = {
        'processo': processo,
        'formset': formset,
        'is_modal': True
    }
    return render(request, 'gestao/gerenciar_partes.html', context)


@login_required
def detalhe_processo_partes_partial(request, processo_pk):
    """
    View auxiliar que retorna apenas o HTML do card de partes envolvidas.

    Utilizada para atualizar dinamicamente o card na página de detalhes do processo
    via AJAX após a edição bem-sucedida das partes em um modal.
    """
    processo = get_object_or_404(Processo.objects.prefetch_related('partes__cliente'), pk=processo_pk)
    return render(request, 'gestao/partials/_card_partes_envolvidas.html', {'processo': processo})


# ==============================================================================
# SEÇÃO: MOVIMENTAÇÕES DE PROCESSO (CRUD + AJAX)
# ==============================================================================

@require_POST
@login_required
def concluir_movimentacao(request, pk):
    """Marca uma movimentação de processo como 'CONCLUÍDA'."""
    movimentacao = get_object_or_404(Movimentacao, pk=pk)
    movimentacao.status = 'CONCLUIDA'
    movimentacao.save()
    messages.success(request, f"A movimentação '{movimentacao.titulo}' foi concluída.")
    redirect_url = reverse('gestao:detalhe_processo', kwargs={'pk': movimentacao.processo.pk}) + '#movimentacoes-pane'
    return redirect(redirect_url)


@login_required
def editar_movimentacao(request, pk):
    """Renderiza a página para editar uma movimentação de processo."""
    movimentacao = get_object_or_404(Movimentacao, pk=pk)
    if request.method == 'POST':
        form = MovimentacaoForm(request.POST, instance=movimentacao)
        if form.is_valid():
            form.save()
            messages.success(request, "Movimentação atualizada com sucesso.")
            return redirect('gestao:detalhe_processo', pk=movimentacao.processo.pk)
    else:
        form = MovimentacaoForm(instance=movimentacao)
    context = {
        'titulo_pagina': 'Editar Movimentação',
        'form': form,
        'movimentacao': movimentacao
    }
    return render(request, 'gestao/editar_movimentacao.html', context)


@require_POST
@login_required
def editar_movimentacao_ajax(request, pk):
    """Processa a edição de uma movimentação de processo via AJAX."""
    movimentacao = get_object_or_404(Movimentacao, pk=pk)
    form = MovimentacaoForm(request.POST, instance=movimentacao)
    if form.is_valid():
        form.save()
        messages.success(request, 'Movimentação atualizada com sucesso!')
        return JsonResponse({'status': 'success'})
    else:
        return JsonResponse({'status': 'error', 'errors': form.errors.get_json_data()}, status=400)


@require_POST
@login_required
def excluir_movimentacao(request, pk):
    """Exclui uma movimentação de processo."""
    movimentacao = get_object_or_404(Movimentacao, pk=pk)
    processo_pk = movimentacao.processo.pk
    titulo_mov = movimentacao.titulo
    movimentacao.delete()
    messages.warning(request, f"A movimentação '{titulo_mov}' foi excluída.")
    return redirect('gestao:detalhe_processo', pk=processo_pk)


@login_required
def get_movimentacao_json(request, pk):
    """
    Retorna os dados de uma movimentação em formato JSON.

    Usado para popular dinamicamente formulários de edição em modais.
    A lógica foi robustecida para evitar erros caso o cliente principal
    do processo não esteja definido.
    """
    try:
        mov = get_object_or_404(
            Movimentacao.objects.select_related(
                'processo', 'responsavel', 'tipo_movimentacao'
            ).prefetch_related('processo__partes__cliente'),
            pk=pk
        )

        # Busca o cliente principal de forma segura.
        cliente_principal = mov.processo.get_cliente_principal()
        cliente_nome = cliente_principal.nome_completo if cliente_principal else ""
        cliente_telefone = ''.join(
            filter(str.isdigit, cliente_principal.telefone_principal or "")) if cliente_principal else ""

        data = {
            'pk': mov.pk,
            'titulo': mov.titulo,
            'tipo_movimentacao_id': mov.tipo_movimentacao_id,
            'detalhes': mov.detalhes,
            'link_referencia': mov.link_referencia,
            'responsavel_id': mov.responsavel_id,
            'status': mov.status,
            'hora_prazo': mov.hora_prazo.strftime('%H:%M') if mov.hora_prazo else '',
            'data_publicacao': mov.data_publicacao.strftime('%Y-%m-%d') if mov.data_publicacao else '',
            'data_intimacao': mov.data_intimacao.strftime('%Y-%m-%d') if mov.data_intimacao else '',
            'data_inicio_prazo': mov.data_inicio_prazo.strftime('%Y-%m-%d') if mov.data_inicio_prazo else '',
            'data_prazo_final': mov.data_prazo_final.strftime('%Y-%m-%d') if mov.data_prazo_final else '',
            'dias_prazo': mov.dias_prazo or '',
            'cliente_nome': cliente_nome,
            'cliente_telefone': cliente_telefone,
            'remetente_nome': request.user.get_full_name() or request.user.username,
        }
        return JsonResponse(data)

    except ObjectDoesNotExist:
        return JsonResponse({'error': 'Movimentação não encontrada'}, status=404)
    except Exception as e:
        logger.error(f"Erro em get_movimentacao_json (pk={pk}): {e}", exc_info=True)
        return JsonResponse({'error': f'Ocorreu um erro interno no servidor.'}, status=500)


# ==============================================================================
# SEÇÃO: SERVIÇOS EXTRAJUDICIAIS (LISTAGEM, DETALHES, CRUD)
# ==============================================================================

@login_required
def lista_servicos(request):
    """
    Exibe um painel de controle para os serviços extrajudiciais.

    A view apresenta uma lista filtrável de serviços, anotada com dados financeiros
    como valor total, total pago e percentual de pagamento, facilitando a
    visão geral da saúde financeira de cada serviço.
    """
    base_queryset = Servico.objects.select_related(
        'cliente', 'tipo_servico', 'responsavel'
    ).annotate(
        valor_total=Coalesce(Sum('lancamentos__valor'), Decimal('0.00')),
        total_pago=Coalesce(Sum('lancamentos__pagamentos__valor_pago'), Decimal('0.00'))
    ).order_by('-data_inicio')

    servico_filter = ServicoFilter(request.GET, queryset=base_queryset)

    # Calcula o percentual pago para cada serviço filtrado.
    servicos_filtrados = servico_filter.qs
    for servico in servicos_filtrados:
        servico.percentual_pago = (servico.total_pago / servico.valor_total * 100) if servico.valor_total > 0 else 0

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'gestao/partials/_lista_servicos_partial.html',
                      {'servicos': servicos_filtrados, 'today': date.today()})

    context = {
        'titulo_pagina': 'Serviços Extrajudiciais',
        'filter': servico_filter,
        'servicos': servicos_filtrados,
        'form_edit': ServicoEditForm()
    }
    return render(request, 'gestao/lista_servicos.html', context)


@login_required
def detalhe_servico(request, pk):
    """
    Exibe o painel de detalhes completo de um serviço extrajudicial.

    Similar à tela de detalhes do processo, esta view concentra todas as informações
    relevantes de um serviço, incluindo:
    - Dados gerais e status do serviço.
    - Histórico de andamentos (tarefas).
    - Painel financeiro detalhado com resumo, lançamentos e pagamentos.
    - Lógica de prazo inteligente que informa o status do prazo final.
    """
    servico = get_object_or_404(
        Servico.objects.prefetch_related(
            'movimentacoes_servico__responsavel', 'lancamentos__pagamentos'
        ).select_related('cliente', 'tipo_servico', 'responsavel'),
        pk=pk
    )

    # --- Lógica POST para adicionar novos andamentos ---
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

    # --- Lógica GET para exibição ---
    # Lógica Financeira
    lancamentos_qs = servico.lancamentos.all()
    regulares_agrupados, inadimplentes_agrupados = _preparar_dados_financeiros(lancamentos_qs)
    valor_total = lancamentos_qs.aggregate(total=Sum('valor'))['total'] or Decimal('0.00')
    total_pago = Pagamento.objects.filter(lancamento__in=lancamentos_qs).aggregate(total=Sum('valor_pago'))[
                     'total'] or Decimal('0.00')
    percentual_pago = (total_pago / valor_total * 100) if valor_total > 0 else 0

    # Lógica de Prazo
    info_prazo = {}
    if servico.prazo and not servico.concluido:
        delta = servico.prazo - timezone.now().date()
        if delta.days < 0:
            info_prazo = {'status': 'VENCIDO', 'texto': f"Vencido há {abs(delta.days)} dia(s)"}
        elif delta.days == 0:
            info_prazo = {'status': 'VENCE_HOJE', 'texto': "Vence Hoje!"}
        else:
            info_prazo = {'status': 'EM_DIA', 'texto': f"Restam {delta.days} dia(s)"}

    context = {
        'titulo_pagina': f"Serviço: {servico.descricao}",
        'servico': servico,
        'movimentacoes': servico.movimentacoes_servico.all().order_by('-data_atividade', '-data_criacao'),
        'form_movimentacao_servico': form_movimentacao,
        'form_pagamento': PagamentoForm(),
        'today': timezone.now().date(),
        'info_prazo': info_prazo,
        'financeiro': {
            'valor_total': valor_total,
            'total_pago': total_pago,
            'saldo_devedor': valor_total - total_pago,
            'percentual_pago': round(percentual_pago, 2),
            'percentual_pago_css': f"{min(percentual_pago, Decimal('100.0')):.2f}".replace(",", "."),
            'form_concluir': ServicoConcluirForm(initial={'data_encerramento': timezone.now().date()}),
        },
        'lancamentos_regulares_agrupados': regulares_agrupados,
        'lancamentos_inadimplentes_agrupados': inadimplentes_agrupados
    }

    # Evita cache para garantir dados sempre atualizados.
    response = render(request, 'gestao/detalhe_servico.html', context)
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


@login_required
def adicionar_servico_view(request):
    """
    Renderiza a página com o assistente (wizard) para adicionar um novo serviço.

    A página contém formulários para o serviço em si, para o contrato de honorários
    associado (opcional), e modais para criação rápida de clientes e tipos de serviço.
    """
    context = {
        'titulo_pagina': 'Adicionar Novo Serviço',
        'form_servico': ServicoForm(prefix='servico'),
        'form_contrato': ContratoHonorariosForm(prefix='contrato'),
        'form_cliente_modal': ClienteModalForm(),
        'form_tipo_servico': TipoServicoForm(),
    }
    return render(request, 'gestao/adicionar_servico.html', context)


@require_POST
@login_required
@transaction.atomic
def salvar_servico_ajax(request):
    """
    Processa a submissão do wizard de criação de serviço via AJAX.

    Valida e salva o serviço e, opcionalmente, o contrato de honorários,
    garantindo que toda a operação seja atômica (ou tudo é salvo, ou nada é).
    Retorna uma resposta JSON com o status da operação.
    """
    try:
        data = json.loads(request.body)
        servico_data = data.get('servico', {})
        contrato_data = data.get('contrato', {})
        has_contrato = data.get('has_contrato', False)

        form_servico = ServicoForm(servico_data)
        form_contrato = ContratoHonorariosForm(contrato_data) if has_contrato else None

        servico_is_valid = form_servico.is_valid()
        contrato_is_valid = not has_contrato or (form_contrato and form_contrato.is_valid())

        if servico_is_valid and contrato_is_valid:
            novo_servico = form_servico.save()

            if has_contrato and form_contrato.cleaned_data.get('valor_pagamento_fixo'):
                contrato = form_contrato.save(commit=False)
                contrato.content_object = novo_servico
                contrato.cliente = novo_servico.cliente
                contrato.save()

            return JsonResponse({
                'status': 'success',
                'redirect_url': novo_servico.get_absolute_url()
            })
        else:
            errors = {}
            errors.update(form_servico.errors.get_json_data())
            if has_contrato and form_contrato:
                errors.update(form_contrato.errors.get_json_data())
            return JsonResponse({'status': 'error', 'errors': errors}, status=400)

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'errors': {'Requisição': 'Formato de dados inválido.'}}, status=400)
    except Exception as e:
        logger.error(f"Erro inesperado em salvar_servico_ajax: {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'errors': {'Servidor': f'Ocorreu um erro interno: {e}'}}, status=500)


@login_required
def editar_servico(request, pk):
    """Renderiza a página para editar um serviço extrajudicial."""
    servico = get_object_or_404(Servico, pk=pk)
    if request.method == 'POST':
        form = ServicoEditForm(request.POST, instance=servico)
        if form.is_valid():
            form.save()
            messages.success(request, "Serviço atualizado com sucesso.")
            return redirect('gestao:detalhe_servico', pk=servico.pk)
    else:
        form = ServicoEditForm(instance=servico)
    return render(request, 'gestao/editar_servico.html', {'form': form, 'servico': servico})


@require_POST
@login_required
def editar_servico_ajax(request, pk):
    """Processa a edição de um serviço via AJAX (geralmente de um modal)."""
    servico = get_object_or_404(Servico, pk=pk)
    form = ServicoEditForm(request.POST, instance=servico)
    if form.is_valid():
        form.save()
        messages.success(request, 'Serviço atualizado com sucesso!')
        return JsonResponse({'status': 'success'})
    else:
        return JsonResponse({'status': 'error', 'errors': form.errors.get_json_data()}, status=400)


@require_POST
@login_required
@transaction.atomic
def excluir_servico(request, pk):
    """
    Exclui um serviço e todos os seus dados relacionados.

    A operação é atômica e também remove contratos, lançamentos financeiros,
    pagamentos e andamentos associados ao serviço.
    """
    servico = get_object_or_404(Servico, pk=pk)
    servico_nome = str(servico)

    # A exclusão em cascata configurada nos modelos cuidará dos objetos relacionados.
    # Exclusão explícita de ContratoHonorarios se o relacionamento for genérico.
    content_type = ContentType.objects.get_for_model(servico)
    ContratoHonorarios.objects.filter(content_type=content_type, object_id=servico.pk).delete()

    servico.delete()

    messages.success(request, f'O serviço "{servico_nome}" e seus vínculos foram excluídos com sucesso.')
    return redirect('gestao:lista_servicos')


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
        messages.success(request, f"Serviço '{servico.descricao}' concluído.")
    else:
        messages.error(request, "Não foi possível concluir o serviço. Verifique os dados.")
    return redirect('gestao:detalhe_servico', pk=pk)


@login_required
def get_servico_json(request, pk):
    """Retorna os dados de um serviço em JSON para popular modais de edição."""
    try:
        servico = get_object_or_404(Servico, pk=pk)
        data = {
            'pk': servico.pk,
            'responsavel': servico.responsavel_id,
            'descricao': servico.descricao,
            'codigo_servico_municipal': servico.codigo_servico_municipal,
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


# ==============================================================================
# SEÇÃO: MOVIMENTAÇÕES DE SERVIÇO (CRUD + AJAX)
# ==============================================================================

@require_POST
@login_required
def adicionar_movimentacao_servico_ajax(request, servico_pk):
    """Salva um novo andamento de serviço enviado via AJAX."""
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
def editar_movimentacao_servico(request, pk):
    """Renderiza a página para editar um andamento de serviço."""
    movimentacao = get_object_or_404(MovimentacaoServico, pk=pk)
    form = MovimentacaoServicoForm(request.POST or None, instance=movimentacao)
    if form.is_valid():
        form.save()
        messages.success(request, "Andamento do serviço atualizado.")
        return redirect('gestao:detalhe_servico', pk=movimentacao.servico.pk)
    return render(request, 'gestao/editar_movimentacao_servico.html', {'form': form, 'movimentacao': movimentacao})


@require_POST
@login_required
def editar_movimentacao_servico_ajax(request, pk):
    """Processa a edição de um andamento de serviço via AJAX."""
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
def excluir_movimentacao_servico(request, pk):
    """Exclui um andamento de serviço."""
    movimentacao = get_object_or_404(MovimentacaoServico, pk=pk)
    servico_pk = movimentacao.servico.pk
    titulo_mov = movimentacao.titulo
    movimentacao.delete()
    messages.warning(request, f"O andamento '{titulo_mov}' foi excluído.")
    return redirect('gestao:detalhe_servico', pk=servico_pk)


@require_POST
@login_required
def concluir_movimentacao_servico(request, pk):
    """Marca um andamento de serviço como 'CONCLUIDA'."""
    movimentacao = get_object_or_404(MovimentacaoServico, pk=pk)
    movimentacao.status = 'CONCLUIDA'
    movimentacao.save()
    messages.success(request, f"A atividade '{movimentacao.titulo}' foi concluída.")
    return redirect('gestao:detalhe_servico', pk=movimentacao.servico.pk)


@login_required
def get_movimentacao_servico_json(request, pk):
    """Retorna os dados de um andamento de serviço em JSON."""
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


# ==============================================================================
# SEÇÃO: CLIENTES E PESSOAS (CRUD)
# ==============================================================================

@login_required
def lista_clientes(request):
    """
    Exibe a lista de CLIENTES ATIVOS com filtros e estatísticas.

    A view anota cada cliente com a contagem de processos e serviços (ativos e
    totais) para fornecer uma visão rápida do volume de trabalho e histórico.
    """
    status_baixados = ['ARQUIVADO', 'EXTINTO', 'ENCERRADO']
    base_queryset = Cliente.objects.filter(is_cliente=True).annotate(
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
    cliente_filter = ClienteFilter(request.GET, queryset=base_queryset)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'gestao/partials/_lista_clientes_partial.html', {'filter': cliente_filter})

    stats = {
        'total_clientes': base_queryset.count(),
        'clientes_ativos': base_queryset.filter(
            Q(processos_ativos_count__gt=0) | Q(servicos_ativos_count__gt=0)).distinct().count(),
    }
    context = {
        'filter': cliente_filter,
        'stats': stats,
        'form': ClienteForm(),
        'titulo_pagina': 'Painel de Clientes'
    }
    return render(request, 'gestao/lista_clientes.html', context)


@login_required
def lista_pessoas(request):
    """
    Exibe a lista de TODAS AS PESSOAS CADASTRADAS (clientes e não-clientes).

    Similar à `lista_clientes`, mas abrange todos os registros no modelo `Cliente`,
    independentemente do campo `is_cliente`.
    """
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
    cliente_filter = ClienteFilter(request.GET, queryset=base_queryset)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'gestao/partials/_lista_clientes_partial.html', {'filter': cliente_filter})

    stats = {
        'total_pessoas': base_queryset.count(),
        'pessoas_ativas': base_queryset.filter(
            Q(processos_ativos_count__gt=0) | Q(servicos_ativos_count__gt=0)).distinct().count(),
    }
    context = {
        'filter': cliente_filter,
        'stats': stats,
        'form': ClienteForm(),
        'titulo_pagina': 'Painel de Pessoas'
    }
    return render(request, 'gestao/lista_clientes.html', context)


@login_required
def detalhe_cliente(request, pk):
    """
    Exibe a página de detalhes de um cliente e permite a edição dos seus dados.
    """
    cliente = get_object_or_404(Cliente, pk=pk)
    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            messages.success(request, "Dados do cliente atualizados com sucesso.")
            return redirect('gestao:detalhe_cliente', pk=cliente.pk)
    else:
        form = ClienteForm(instance=cliente)

    context = {
        'titulo_pagina': f'Detalhes de {cliente.nome_completo}',
        'cliente': cliente,
        'form': form
    }
    return render(request, 'gestao/detalhe_cliente.html', context)


@login_required
def adicionar_cliente_page(request):
    """Renderiza e processa a página completa de cadastro de um novo cliente/pessoa."""
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            cliente = form.save()
            messages.success(request, f'Cadastro de "{cliente.nome_completo}" realizado com sucesso!')
            return redirect('gestao:detalhe_cliente', pk=cliente.pk)
        else:
            messages.error(request, 'Não foi possível salvar. Por favor, corrija os erros abaixo.')
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


@require_POST
@login_required
def excluir_cliente(request, pk):
    """
    Exclui um cliente via AJAX, somente se ele não tiver vínculos.

    Realiza uma verificação de segurança para impedir a exclusão de clientes
    associados a processos ou serviços, prevenindo a perda de dados históricos.
    """
    cliente = get_object_or_404(Cliente, pk=pk)
    if cliente.participacoes.exists() or cliente.servicos.exists():
        return JsonResponse({
            'status': 'error',
            'message': 'Não é possível excluir, pois este cadastro está vinculado a processos ou serviços.'
        }, status=400)
    try:
        nome_cliente = cliente.nome_completo
        cliente.delete()
        return JsonResponse({'status': 'success', 'message': f'Cadastro de "{nome_cliente}" excluído com sucesso!'})
    except Exception as e:
        logger.error(f"Erro ao excluir cliente (pk={pk}): {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': f'Ocorreu um erro inesperado: {str(e)}'}, status=500)


@login_required
@staff_member_required
def excluir_clientes_em_massa(request):
    """
    Exclui todos os cadastros de pessoas que não possuem nenhum vínculo.

    Ação administrativa restrita a superusuários para limpeza de banco de dados.
    """
    if not request.user.is_superuser:
        return HttpResponseForbidden("Acesso negado.")

    if request.method == 'POST':
        cadastros_para_excluir = Cliente.objects.annotate(
            num_processos=Count('participacoes'),
            num_servicos=Count('servicos')
        ).filter(num_processos=0, num_servicos=0)

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
    return redirect('gestao:lista_clientes')


@login_required
def get_cliente_json(request, pk):
    """Retorna os dados de um cliente em JSON para popular formulários."""
    cliente = get_object_or_404(Cliente, pk=pk)
    data = {
        'nome_completo': cliente.nome_completo, 'tipo_pessoa': cliente.tipo_pessoa,
        'cpf_cnpj': cliente.cpf_cnpj, 'email': cliente.email,
        'telefone_principal': cliente.telefone_principal,
        'data_nascimento': cliente.data_nascimento.strftime('%Y-%m-%d') if cliente.data_nascimento else None,
        'nacionalidade': cliente.nacionalidade, 'estado_civil': cliente.estado_civil,
        'profissao': cliente.profissao, 'cep': cliente.cep, 'logradouro': cliente.logradouro,
        'numero': cliente.numero, 'complemento': cliente.complemento, 'bairro': cliente.bairro,
        'cidade': cliente.cidade, 'estado': cliente.estado,
        'representante_legal': cliente.representante_legal,
        'cpf_representante_legal': cliente.cpf_representante_legal,
    }
    return JsonResponse(data)


@login_required
def get_all_clients_json(request):
    """Retorna uma lista de todos os clientes formatada para Select2."""
    clientes = Cliente.objects.all().order_by('nome_completo')
    client_data = [{"id": cliente.pk, "text": str(cliente)} for cliente in clientes]
    return JsonResponse(client_data, safe=False)


# ==============================================================================
# SEÇÃO: FINANCEIRO (PAINEL, CONTRATOS, PAGAMENTOS, DESPESAS)
# ==============================================================================

@login_required
def painel_financeiro(request):
    """
    Renderiza o painel financeiro geral.

    Apresenta uma visão consolidada das finanças do escritório, incluindo:
    - KPIs de receitas, despesas e saldo no período selecionado.
    - Análise de inadimplência.
    - Listagens de contas a pagar e a receber.
    - Análise de faturamento por cliente.
    """
    hoje = timezone.now().date()
    data_inicio_str = request.GET.get('data_inicio', hoje.replace(day=1).strftime('%Y-%m-%d'))
    data_fim_default = (hoje.replace(day=1) + relativedelta(months=1)) - timedelta(days=1)
    data_fim_str = request.GET.get('data_fim', data_fim_default.strftime('%Y-%m-%d'))

    try:
        data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
        data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
    except ValueError:
        messages.error(request, "Formato de data inválido. Use AAAA-MM-DD.")
        return redirect('gestao:painel_financeiro')

    # Consulta base com status calculado para todos os lançamentos
    lancamentos_com_status = LancamentoFinanceiro.objects.annotate(
        total_pago=Coalesce(Sum('pagamentos__valor_pago'), Decimal(0))
    ).annotate(
        status_calculado=Case(
            When(valor__lte=F('total_pago'), then=Value('PAGO')),
            When(data_vencimento__lt=hoje, then=Value('ATRASADO')),
            When(total_pago__gt=0, then=Value('PARCIAL')),
            default=Value('A_PAGAR'),
            output_field=CharField()
        )
    )

    # Filtra lançamentos e pagamentos para o período selecionado
    lancamentos_periodo = lancamentos_com_status.filter(data_vencimento__range=[data_inicio, data_fim])
    pagamentos_periodo = Pagamento.objects.filter(data_pagamento__range=[data_inicio, data_fim])

    # KPIs
    total_recebido = \
    pagamentos_periodo.filter(lancamento__tipo='RECEITA').aggregate(total=Coalesce(Sum('valor_pago'), Decimal(0)))[
        'total']
    total_pago_despesas = \
    pagamentos_periodo.filter(lancamento__tipo='DESPESA').aggregate(total=Coalesce(Sum('valor_pago'), Decimal(0)))[
        'total']
    saldo_realizado = total_recebido - total_pago_despesas
    previsao_receitas = lancamentos_periodo.filter(tipo='RECEITA').aggregate(total=Coalesce(Sum('valor'), Decimal(0)))[
        'total']
    previsao_despesas = lancamentos_periodo.filter(tipo='DESPESA').aggregate(total=Coalesce(Sum('valor'), Decimal(0)))[
        'total']

    # Inadimplência
    inadimplentes = lancamentos_com_status.filter(status_calculado='ATRASADO').order_by('data_vencimento')
    total_inadimplencia = sum(lanc.valor - lanc.total_pago for lanc in inadimplentes)

    context = {
        'titulo_pagina': "Painel Financeiro",
        'form_lancamento': LancamentoFinanceiroForm(),
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'saldo_realizado': saldo_realizado,
        'previsao_receitas': previsao_receitas,
        'previsao_despesas': previsao_despesas,
        'total_inadimplencia': total_inadimplencia,
        'inadimplentes': inadimplentes,
        'contas_a_pagar': lancamentos_periodo.filter(tipo='DESPESA',
                                                     status_calculado__in=['A_PAGAR', 'PARCIAL']).order_by(
            'data_vencimento'),
        'contas_a_receber': lancamentos_periodo.filter(tipo='RECEITA',
                                                       status_calculado__in=['A_PAGAR', 'PARCIAL']).order_by(
            'data_vencimento'),
    }
    return render(request, 'gestao/financeiro/painel_financeiro.html', context)


@login_required
def adicionar_contrato(request, processo_pk=None, servico_pk=None):
    """
    Adiciona um contrato de honorários a um processo ou a um serviço.
    """
    parent_object = None
    redirect_url_with_hash = ""

    if processo_pk:
        parent_object = get_object_or_404(Processo.objects.prefetch_related('partes__cliente'), pk=processo_pk)
        redirect_url_with_hash = f"{parent_object.get_absolute_url()}#financeiro-pane"
    elif servico_pk:
        parent_object = get_object_or_404(Servico, pk=servico_pk)
        redirect_url_with_hash = f"{parent_object.get_absolute_url()}#financeiro-tab-pane"

    if not parent_object:
        messages.error(request, "Objeto de origem (processo ou serviço) não encontrado.")
        return redirect('gestao:dashboard')

    if request.method == 'POST':
        form = ContratoHonorariosForm(request.POST)
        if form.is_valid():
            contrato = form.save(commit=False)
            contrato.content_object = parent_object

            if isinstance(parent_object, Processo):
                cliente_principal = parent_object.get_cliente_principal()
                if not cliente_principal:
                    form.add_error(None, "O processo deve ter um cliente principal definido para criar um contrato.")
                else:
                    contrato.cliente = cliente_principal
            elif isinstance(parent_object, Servico):
                contrato.cliente = parent_object.cliente

            if not form.errors:
                contrato.save()
                messages.success(request, "Contrato de honorários criado com sucesso.")
                return redirect(redirect_url_with_hash)
    else:
        form = ContratoHonorariosForm()

    context = {
        'titulo_pagina': 'Adicionar Contrato de Honorários',
        'form': form,
        'parent_object': parent_object,
    }
    return render(request, 'gestao/adicionar_contrato.html', context)


@require_POST
@login_required
def adicionar_pagamento(request, pk):
    """Adiciona um pagamento a um lançamento financeiro via AJAX."""
    lancamento = get_object_or_404(LancamentoFinanceiro.objects.select_related('processo', 'servico'), pk=pk)
    form = PagamentoForm(request.POST)

    if form.is_valid():
        pagamento = form.save(commit=False)
        pagamento.lancamento = lancamento
        pagamento.save()
        success = True
        errors = None
        messages.success(request, f"Pagamento de {pagamento.valor_pago} registrado.")
    else:
        success = False
        errors = form.errors.as_json()

    # Define a URL de redirecionamento com a âncora correta.
    if lancamento.processo:
        redirect_url = reverse('gestao:detalhe_processo', kwargs={'pk': lancamento.processo.pk}) + '#financeiro-pane'
    elif lancamento.servico:
        redirect_url = reverse('gestao:detalhe_servico', kwargs={'pk': lancamento.servico.pk}) + '#financeiro-tab-pane'
    else:
        redirect_url = reverse('gestao:painel_financeiro')

    return JsonResponse({'success': success, 'redirect_url': redirect_url, 'errors': errors})


@require_POST
@login_required
def editar_pagamento(request, pk):
    """Edita um pagamento existente via AJAX."""
    pagamento = get_object_or_404(Pagamento.objects.select_related('lancamento__processo', 'lancamento__servico'),
                                  pk=pk)
    form = PagamentoForm(request.POST, instance=pagamento)

    if form.is_valid():
        form.save()
        success = True
        errors = None
        messages.success(request, "Pagamento atualizado.")
    else:
        success = False
        errors = form.errors.as_json()

    if pagamento.lancamento.processo:
        redirect_url = reverse('gestao:detalhe_processo',
                               kwargs={'pk': pagamento.lancamento.processo.pk}) + '#financeiro-pane'
    elif pagamento.lancamento.servico:
        redirect_url = reverse('gestao:detalhe_servico',
                               kwargs={'pk': pagamento.lancamento.servico.pk}) + '#financeiro-tab-pane'
    else:
        redirect_url = reverse('gestao:painel_financeiro')

    return JsonResponse({'success': success, 'redirect_url': redirect_url, 'errors': errors})


@require_POST
@login_required
def excluir_pagamento(request, pk):
    """Exclui um pagamento existente via AJAX."""
    pagamento = get_object_or_404(Pagamento.objects.select_related('lancamento__processo', 'lancamento__servico'),
                                  pk=pk)
    valor_pago = pagamento.valor_pago
    lancamento = pagamento.lancamento

    pagamento.delete()
    messages.warning(request, f"Pagamento de {valor_pago} foi excluído.")

    if lancamento.processo:
        redirect_url = reverse('gestao:detalhe_processo', kwargs={'pk': lancamento.processo.pk}) + '#financeiro-pane'
    elif lancamento.servico:
        redirect_url = reverse('gestao:detalhe_servico', kwargs={'pk': lancamento.servico.pk}) + '#financeiro-tab-pane'
    else:
        redirect_url = reverse('gestao:painel_financeiro')

    return JsonResponse({'success': True, 'redirect_url': redirect_url})


@login_required
def imprimir_recibo(request, pagamento_pk):
    """Gera uma página de recibo de pagamento formatada para impressão."""
    pagamento = get_object_or_404(
        Pagamento.objects.select_related(
            'lancamento__cliente', 'lancamento__processo', 'lancamento__servico'
        ), pk=pagamento_pk
    )
    escritorio = EscritorioConfiguracao.objects.first()

    context = {
        'pagamento': pagamento,
        'escritorio': escritorio,
        'data_emissao_extenso': data_por_extenso(timezone.now().date()),
        'valor_extenso': valor_por_extenso(pagamento.valor_pago),
    }
    return render(request, 'gestao/recibo_pagamento.html', context)


@login_required
def painel_despesas(request):
    """Exibe um painel dedicado ao gerenciamento de despesas."""
    hoje = timezone.now().date()
    primeiro_dia_mes = hoje.replace(day=1)
    ultimo_dia_mes = (primeiro_dia_mes + relativedelta(months=1)) - timedelta(days=1)

    despesas = LancamentoFinanceiro.objects.filter(tipo='DESPESA').annotate(
        total_pago=Coalesce(Sum('pagamentos__valor_pago'), Decimal(0))
    ).annotate(
        saldo_devedor_calc=F('valor') - F('total_pago'),
        status_calculado=Case(
            When(valor__lte=F('total_pago'), then=Value('PAGO')),
            When(data_vencimento__lt=hoje, then=Value('ATRASADO')),
            default=Value('A_PAGAR'),
            output_field=CharField()
        )
    )

    total_vencido = \
    despesas.filter(status_calculado='ATRASADO').aggregate(total=Coalesce(Sum('saldo_devedor_calc'), Decimal(0)))[
        'total']
    a_pagar_mes = \
    despesas.filter(status_calculado='A_PAGAR', data_vencimento__range=[primeiro_dia_mes, ultimo_dia_mes]).aggregate(
        total=Coalesce(Sum('saldo_devedor_calc'), Decimal(0)))['total']

    context = {
        'titulo_pagina': "Gestão de Despesas",
        'total_vencido': total_vencido,
        'a_pagar_mes': a_pagar_mes,
        'despesas_vencidas': despesas.filter(status_calculado='ATRASADO').order_by('data_vencimento'),
        'despesas_a_pagar_mes': despesas.filter(status_calculado='A_PAGAR',
                                                data_vencimento__range=[primeiro_dia_mes, ultimo_dia_mes]).order_by(
            'data_vencimento'),
    }
    return render(request, 'gestao/financeiro/painel_despesas.html', context)


@login_required
@transaction.atomic
def adicionar_despesa_wizard(request):
    """
    Controla o fluxo do wizard para adicionar diferentes tipos de despesa.
    O estado do wizard é mantido na sessão.
    Após salvar, redireciona para a tela de origem.
    """
    STEP_SELECT_TYPE = 'select_type'
    STEP_FILL_DETAILS = 'fill_details'

    current_step = request.session.get('despesa_wizard_step', STEP_SELECT_TYPE)
    despesa_type = request.session.get('despesa_type', None)
    categoria = request.session.get('despesa_categoria', None)

    if request.method == 'POST':
        if 'reset_wizard' in request.POST:
            for key in ['despesa_wizard_step', 'despesa_type', 'despesa_categoria', 'despesa_wizard_next_url']:
                request.session.pop(key, None)
            return redirect('gestao:adicionar_despesa_wizard')

        if current_step == STEP_SELECT_TYPE:
            form_type = DespesaTipoForm(request.POST)
            if form_type.is_valid():
                request.session['despesa_type'] = form_type.cleaned_data['tipo_despesa']
                request.session['despesa_categoria'] = form_type.cleaned_data['categoria']
                request.session['despesa_wizard_step'] = STEP_FILL_DETAILS
                request.session['despesa_wizard_next_url'] = request.META.get('HTTP_REFERER',
                                                                              reverse('gestao:painel_financeiro'))
                return redirect('gestao:adicionar_despesa_wizard')

        elif current_step == STEP_FILL_DETAILS and despesa_type:
            FormClass = {'pontual': DespesaPontualForm, 'recorrente_fixa': DespesaRecorrenteFixaForm,
                         'recorrente_variavel': DespesaRecorrenteVariavelForm}.get(despesa_type)
            if not FormClass:
                messages.error(request, "Tipo de despesa inválido.")
                request.session['despesa_wizard_step'] = STEP_SELECT_TYPE
                return redirect('gestao:adicionar_despesa_wizard')

            form_detail = FormClass(request.POST)
            if form_detail.is_valid():
                cliente_selecionado = form_detail.cleaned_data.get('cliente')
                try:
                    if despesa_type in ['pontual', 'recorrente_variavel']:
                        LancamentoFinanceiro.objects.create(
                            descricao=form_detail.cleaned_data['descricao'],
                            valor=form_detail.cleaned_data['valor'],
                            data_vencimento=form_detail.cleaned_data['data_vencimento'],
                            tipo='DESPESA', categoria=categoria, cliente=cliente_selecionado,
                        )
                    elif despesa_type == 'recorrente_fixa':
                        data_inicio = form_detail.cleaned_data['data_inicio_recorrencia']
                        data_fim = form_detail.cleaned_data.get('data_fim_recorrencia') or (
                                    date.today() + relativedelta(years=5))
                        dia_vencimento = form_detail.cleaned_data['dia_vencimento_recorrente']

                        data_corrente = data_inicio
                        while data_corrente <= data_fim:
                            try:
                                data_vencimento_mensal = data_corrente.replace(day=dia_vencimento)
                            except ValueError:
                                _, ultimo_dia_mes = calendar.monthrange(data_corrente.year, data_corrente.month)
                                data_vencimento_mensal = data_corrente.replace(day=ultimo_dia_mes)

                            if data_vencimento_mensal >= data_inicio and data_vencimento_mensal <= data_fim:
                                LancamentoFinanceiro.objects.create(
                                    descricao=f"{form_detail.cleaned_data['descricao']} ({data_vencimento_mensal.strftime('%m/%Y')})",
                                    valor=form_detail.cleaned_data['valor_recorrente'],
                                    data_vencimento=data_vencimento_mensal,
                                    tipo='DESPESA', categoria=categoria, cliente=cliente_selecionado,
                                )
                            data_corrente += relativedelta(months=1)

                    messages.success(request, f'Despesa ({despesa_type}) salva com sucesso!')
                    next_url = request.session.pop('despesa_wizard_next_url', reverse('gestao:painel_financeiro'))
                    for key in ['despesa_wizard_step', 'despesa_type', 'despesa_categoria']:
                        request.session.pop(key, None)
                    return redirect(next_url)
                except Exception as e:
                    messages.error(request, f'Erro ao salvar despesa: {e}.')

    # Lógica GET ou formulários inválidos
    context = {'titulo_pagina': "Adicionar Nova Despesa"}
    if current_step == STEP_SELECT_TYPE:
        context['form_type'] = DespesaTipoForm(initial={'tipo_despesa': despesa_type, 'categoria': categoria})
        context['current_step'] = STEP_SELECT_TYPE
    elif current_step == STEP_FILL_DETAILS:
        FormClass = {'pontual': DespesaPontualForm, 'recorrente_fixa': DespesaRecorrenteFixaForm,
                     'recorrente_variavel': DespesaRecorrenteVariavelForm}.get(despesa_type)
        context['form_detail'] = FormClass(request.POST if request.method == 'POST' else None)
        context['despesa_type'] = despesa_type
        if categoria:
            context['categoria_selecionada'] = dict(LancamentoFinanceiro.CATEGORIA_CHOICES).get(categoria, categoria)
        context['current_step'] = STEP_FILL_DETAILS

    return render(request, 'gestao/financeiro/adicionar_despesa_wizard.html', context)


# ==============================================================================
# SEÇÃO: DOCUMENTOS E MODELOS
# ==============================================================================

# Constante para as variáveis disponíveis na criação de modelos.
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
    context = {'modelos': modelos, 'titulo_pagina': 'Modelos de Documentos'}
    return render(request, 'gestao/modelos/lista_modelos.html', context)


@login_required
def adicionar_modelo(request):
    """Exibe e processa o formulário para adicionar um novo modelo de documento."""
    if request.method == 'POST':
        form = ModeloDocumentoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Modelo criado com sucesso.")
            return redirect('gestao:lista_modelos')
    else:
        form = ModeloDocumentoForm()
    context = {'form': form, 'titulo_pagina': 'Adicionar Novo Modelo', 'variaveis': VARIAVEIS_DOCUMENTO}
    return render(request, 'gestao/modelos/form_modelo.html', context)


@login_required
def editar_modelo(request, pk):
    """Exibe e processa o formulário para editar um modelo de documento."""
    modelo = get_object_or_404(ModeloDocumento, pk=pk)
    if request.method == 'POST':
        form = ModeloDocumentoForm(request.POST, instance=modelo)
        if form.is_valid():
            form.save()
            messages.success(request, "Modelo atualizado com sucesso.")
            return redirect('gestao:lista_modelos')
    else:
        form = ModeloDocumentoForm(instance=modelo)
    context = {
        'form': form, 'modelo': modelo,
        'titulo_pagina': 'Editar Modelo', 'variaveis': VARIAVEIS_DOCUMENTO
    }
    return render(request, 'gestao/modelos/form_modelo.html', context)


@require_POST
@login_required
def excluir_modelo(request, pk):
    """Exclui um modelo de documento."""
    modelo = get_object_or_404(ModeloDocumento, pk=pk)
    titulo_modelo = modelo.titulo
    modelo.delete()
    messages.warning(request, f"Modelo '{titulo_modelo}' excluído.")
    return redirect('gestao:lista_modelos')


@login_required
def gerar_documento(request, processo_pk, modelo_pk):
    """
    Gera um novo documento a partir de um modelo para um processo.
    """
    processo = get_object_or_404(Processo, pk=processo_pk)
    modelo = get_object_or_404(ModeloDocumento, pk=modelo_pk)
    cliente_principal = processo.get_cliente_principal()
    escritorio = EscritorioConfiguracao.objects.first()

    contexto_variaveis = Context({
        'cliente': cliente_principal,
        'processo': processo,
        'data_extenso': data_por_extenso(date.today()),
        'cidade_escritorio': escritorio.cidade if escritorio else ''
    })

    conteudo_renderizado = Template(modelo.conteudo).render(contexto_variaveis) if modelo.conteudo else ""
    titulo_sugerido = f"{modelo.titulo} - {cliente_principal.nome_completo if cliente_principal else 'Processo'}"

    if request.method == 'POST':
        form = GerarDocumentoForm(request.POST)
        if form.is_valid():
            documento = form.save(commit=False)
            documento.processo = processo
            documento.modelo_origem = modelo
            documento.save()
            return redirect('gestao:imprimir_documento', pk=documento.pk)
    else:
        form = GerarDocumentoForm(initial={'titulo': titulo_sugerido, 'conteudo': conteudo_renderizado})

    context = {
        'form': form, 'processo': processo,
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
            return redirect('gestao:imprimir_documento', pk=documento.pk)
    else:
        form = DocumentoForm(instance=documento)

    context = {
        'form': form, 'processo': documento.processo,
        'titulo_pagina': 'Editar Documento'
    }
    return render(request, 'gestao/documentos/form_documento.html', context)


@login_required
def imprimir_documento(request, pk):
    """Prepara uma página otimizada para a impressão de um documento gerado."""
    documento = get_object_or_404(Documento, pk=pk)
    context = {
        'documento': documento,
        'escritorio': EscritorioConfiguracao.objects.first(),
    }
    return render(request, 'gestao/documentos/imprimir_documento.html', context)


# ==============================================================================
# SEÇÃO: CÁLCULO JUDICIAL
# ==============================================================================

# gestao/views.py

# -*- coding: utf-8 -*-

# ==============================================================================
# IMPORTS
# ==============================================================================
# Otimização: Imports foram reorganizados por tipo (Standard Library, Third-Party, Django, Local App)
# e duplicatas/redundâncias foram removidas para maior clareza e eficiência.

# --- Standard Library ---
import json
import logging
import locale
import itertools
import re
import calendar
from datetime import date, datetime, timedelta
from decimal import Decimal
from operator import attrgetter
import unicodedata

# --- Third-Party Libraries ---
from dateutil.relativedelta import relativedelta
from django.forms import inlineformset_factory
from unidecode import unidecode

# --- Django Core ---
from django.apps import apps
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import (
    Q, Case, CharField, DateField, DecimalField, F, OuterRef, Subquery, Sum,
    Value, When, Func, Count,
)
from django.db.models.functions import Coalesce
from django.http import (
    Http404, HttpResponse, HttpResponseBadRequest, JsonResponse, HttpResponseForbidden
)
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404, redirect, render
from django.template import Context, Template
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

# --- Local Application ---
from . import models
from .calculators import CalculadoraMonetaria
from .encoders import DecimalEncoder
from .filters import ClienteFilter, ProcessoFilter, ServicoFilter
from .forms import (
    AreaProcessoForm, CalculoForm, ClienteForm, ClienteModalForm,
    ContratoHonorariosForm, CustomUserChangeForm, CustomUserCreationForm,
    DocumentoForm, EscritorioConfiguracaoForm, IncidenteForm,
    ModeloDocumentoForm, MovimentacaoForm, MovimentacaoServicoForm,
    PagamentoForm, ParteProcessoFormSet, ProcessoCreateForm, ProcessoForm,
    RecursoForm, ServicoConcluirForm, ServicoEditForm, ServicoForm,
    TipoAcaoForm, TipoServicoForm, UsuarioPerfilForm, GerarDocumentoForm,
    LancamentoFinanceiroForm, DespesaRecorrenteVariavelForm,
    DespesaRecorrenteFixaForm, DespesaPontualForm, DespesaTipoForm, CalculoJudicialForm, FaseCalculoFormSet,
    FaseCalculoForm,
)
from .models import (
    AreaProcesso, CalculoJudicial,FaseCalculo, Cliente, Documento, EscritorioConfiguracao,
    Incidente, LancamentoFinanceiro, ModeloDocumento, Movimentacao,
    MovimentacaoServico, Pagamento, Processo, Recurso, Servico, TipoAcao,
    TipoServico, UsuarioPerfil, ContratoHonorarios, ParteProcesso, TipoMovimentacao,
)
from .services.indices.resolver import ServicoIndices


from .nfse_service import NFSEService
from .utils import data_por_extenso, valor_por_extenso

# ... (O restante do arquivo views.py permanece o mesmo) ...

# ==============================================================================
# SEÇÃO: CÁLCULO JUDICIAL
# ==============================================================================
@login_required
def realizar_calculo(request, processo_pk, calculo_pk=None):
    """
    View refatorada para criar, carregar, calcular e salvar um Cálculo Judicial.
    Utiliza múltiplos formsets para lançamentos, correções e juros.
    """
    processo = get_object_or_404(Processo, pk=processo_pk)
    calculo_instance = get_object_or_404(CalculoJudicial, pk=calculo_pk) if calculo_pk else None

    lancamentos_existentes = []
    if calculo_instance:
        lancamentos_existentes = list(calculo_instance.lancamentos.values('id', 'descricao', 'valor'))

    if request.method == 'POST':
        form = CalculoJudicialForm(request.POST, instance=calculo_instance)
        lancamento_formset = LancamentoFormSet(request.POST, instance=calculo_instance, prefix='lancamento')
        correcao_formset = CorrecaoFormSet(request.POST, instance=calculo_instance, prefix='correcao')
        juros_formset = JurosFormSet(request.POST, instance=calculo_instance, prefix='juros')

        if form.is_valid() and lancamento_formset.is_valid() and correcao_formset.is_valid() and juros_formset.is_valid():
            with transaction.atomic():
                calculo_principal = form.save(commit=False)
                calculo_principal.processo = processo
                calculo_principal.responsavel = request.user

                # Se não houver lançamentos, usa o valor_base para criar um
                if not lancamento_formset.get_queryset().exists() and not any(
                        f.cleaned_data for f in lancamento_formset if f.has_changed()):
                    valor_base = form.cleaned_data.get('valor_base')
                    if valor_base and valor_base > 0:
                        calculo_principal.save()  # Salva primeiro para obter um PK
                        CalculoLancamento.objects.create(
                            calculo=calculo_principal,
                            tipo='CREDITO',
                            descricao='Valor Base Informado',
                            valor=valor_base
                        )
                    else:  # Se não tem lançamentos nem valor base, o que calcular?
                        form.add_error('valor_base',
                                       'É necessário informar um Valor Base se não houver lançamentos detalhados.')
                        # Força a saída do bloco 'with' e vai para a renderização de erro.
                        raise transaction.TransactionManagementError()

                if not hasattr(calculo_principal, 'pk') or not calculo_principal.pk:
                    calculo_principal.save()

                lancamento_formset.instance = calculo_principal
                lancamentos = lancamento_formset.save()

                correcao_formset.instance = calculo_principal
                correcoes = correcao_formset.save()

                juros_formset.instance = calculo_principal
                regras_juros = juros_formset.save()

                # try:
                #     # CHAMADA À CALCULADORA (a ser implementada ou ajustada)
                #     calculadora = CalculadoraMonetaria()
                #     resultado_calculo = calculadora.calcular_detalhado(
                #         calculo_principal, lancamentos, correcoes, regras_juros
                #     )

                #     calculo_principal.valor_final_calculado = resultado_calculo['resumo']['valor_final']
                #     calculo_principal.memoria_calculo_json = json.dumps(resultado_calculo, cls=DecimalEncoder)
                #     calculo_principal.save()

                messages.success(request,
                                 'Cálculo salvo com sucesso! A funcionalidade de cálculo está em desenvolvimento.')
                return redirect('gestao:realizar_calculo', processo_pk=processo.pk, calculo_pk=calculo_principal.pk)

                # except Exception as e:
                #     logger.error(f"Erro na execução do cálculo para o ID {calculo_principal.pk}: {e}", exc_info=True)
                #     messages.error(request, f'Ocorreu um erro durante o cálculo: {e}')
        else:
            messages.error(request, 'Por favor, corrija os erros indicados no formulário.')

    else:  # GET
        form = CalculoJudicialForm(instance=calculo_instance)
        lancamento_formset = LancamentoFormSet(instance=calculo_instance, prefix='lancamento')
        correcao_formset = CorrecaoFormSet(instance=calculo_instance, prefix='correcao')
        juros_formset = JurosFormSet(instance=calculo_instance, prefix='juros')

    contexto = {
        'processo': processo,
        'form': form,
        'lancamento_formset': lancamento_formset,
        'correcao_formset': correcao_formset,
        'juros_formset': juros_formset,
        'lancamentos_existentes': json.dumps(lancamentos_existentes),
        'calculo_carregado': calculo_instance,
        # 'resultado': resultado, # A ser implementado com a calculadora
    }
    return render(request, 'gestao/calculo_judicial.html', contexto)


@require_POST
@login_required
def atualizar_calculo_hoje(request, calculo_pk):
    """Prepara os dados de um cálculo para serem recalculados com a data atual."""
    calculo = get_object_or_404(CalculoJudicial, pk=calculo_pk)
    form_data = {f.name: getattr(calculo, f.name) for f in CalculoJudicial._meta.fields if hasattr(calculo, f.name)}
    form_data['data_fim'] = date.today()
    form_data['descricao'] = f"Cópia de '{calculo.descricao}' (Atualizado)"
    request.session['form_initial_data'] = {k: (v.isoformat() if isinstance(v, date) else str(v)) for k, v in
                                            form_data.items()}
    return redirect('gestao:realizar_calculo', processo_pk=calculo.processo.pk)


@require_POST
@login_required
def excluir_calculo(request, calculo_pk):
    """Exclui um cálculo judicial específico."""
    calculo = get_object_or_404(CalculoJudicial, pk=calculo_pk)
    processo_pk = calculo.processo.pk
    calculo.delete()
    messages.warning(request, "Cálculo excluído.")
    return redirect('gestao:pagina_de_calculos', processo_pk=processo_pk)


@require_POST
@login_required
def excluir_todos_calculos(request, processo_pk):
    """Exclui TODOS os cálculos judiciais associados a um processo."""
    processo = get_object_or_404(Processo, pk=processo_pk)
    count = processo.calculos.count()
    processo.calculos.all().delete()
    messages.warning(request, f"{count} cálculo(s) foram excluídos.")
    return redirect('gestao:realizar_calculo', processo_pk=processo_pk)


# ==============================================================================
# SEÇÃO: VIEWS DE CONFIGURAÇÃO E USUÁRIOS
# ==============================================================================

@login_required
@staff_member_required
def configuracoes(request):
    """
    Página central de configurações do sistema.

    Renderiza e processa todos os formulários e dados necessários para as abas de
    configuração, incluindo Escritório, Usuários, Cadastros Auxiliares e Permissões.
    """
    config, _ = EscritorioConfiguracao.objects.get_or_create(pk=1)

    # Trata a submissão do formulário de dados do escritório
    if request.method == 'POST' and 'salvar_escritorio' in request.POST:
        form_escritorio = EscritorioConfiguracaoForm(request.POST, request.FILES, instance=config)
        if form_escritorio.is_valid():
            form_escritorio.save()
            messages.success(request, 'Configurações do escritório salvas com sucesso!')
            return redirect('gestao:configuracoes')
    else:
        form_escritorio = EscritorioConfiguracaoForm(instance=config)

    # Prepara a paginação para a lista de usuários
    users_list = User.objects.all().order_by('first_name').prefetch_related('groups')
    paginator = Paginator(users_list, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    # Estrutura as permissões para serem exibidas de forma organizada no template
    perm_codenames = [p['codename'] for mod_perms in PERMISSOES_MAPEADAS.values() for p in mod_perms]
    perm_map = {p.codename: p for p in Permission.objects.filter(codename__in=perm_codenames)}
    perm_estruturadas = {
        mod: [{'id': perm_map[p['codename']].id, 'label': p['label']}
              for p in perms if p['codename'] in perm_map]
        for mod, perms in PERMISSOES_MAPEADAS.items()
    }

    # --- CORREÇÃO DO ERRO TypeError ---
    # Busca todos os Tipos de Ação e os agrupa em um dicionário pela chave primária da Área.
    # O template usará este dicionário para iterar corretamente.
    todos_tipos_acao = TipoAcao.objects.select_related('area').order_by('area__nome', 'nome')
    tipos_acao_por_area = {}
    for tipo_acao in todos_tipos_acao:
        if tipo_acao.area_id not in tipos_acao_por_area:
            tipos_acao_por_area[tipo_acao.area_id] = []
        tipos_acao_por_area[tipo_acao.area_id].append(tipo_acao)
    # --- FIM DA CORREÇÃO ---

    # Monta o dicionário de contexto final para o template
    context = {
        'titulo_pagina': 'Configurações',
        'form_escritorio': form_escritorio,
        'configuracao_escritorio': config,
        'usuarios': page_obj,
        'grupos': Group.objects.order_by('name'),
        'permissoes_estruturadas': perm_estruturadas,

        # Formulários para os modais e forms de cadastros auxiliares
        'form_tipo_servico': TipoServicoForm(),
        'form_area_processo': AreaProcessoForm(),
        'form_tipo_acao': TipoAcaoForm(),
        'form_tipo_movimentacao': TipoMovimentacaoForm(),

        # Querysets com os itens para listar em cada aba de cadastro
        'tipos_servico': TipoServico.objects.all().order_by('nome'),
        'areas_processo': AreaProcesso.objects.all().order_by('nome'),
        'tipos_acao': tipos_acao_por_area,  # Passa o dicionário já agrupado
        'tipos_movimentacao': TipoMovimentacao.objects.all().order_by('-favorito', 'nome'),
    }
    return render(request, 'gestao/configuracoes.html', context)


@login_required
@transaction.atomic
def adicionar_usuario(request):
    """Renderiza e processa o formulário de criação de um novo usuário e seu perfil."""
    if request.method == 'POST':
        user_form = CustomUserCreationForm(request.POST)
        profile_form = UsuarioPerfilForm(request.POST, request.FILES)
        if user_form.is_valid() and profile_form.is_valid():
            user = user_form.save()  # O sinal post_save cria o perfil
            # Atualiza o perfil recém-criado com os dados do formulário
            profile_form_with_instance = UsuarioPerfilForm(request.POST, request.FILES, instance=user.perfil)
            if profile_form_with_instance.is_valid():
                profile_form_with_instance.save()
            messages.success(request, f'Usuário "{user.username}" criado com sucesso!')
            return redirect('gestao:configuracoes')
    else:
        user_form = CustomUserCreationForm()
        profile_form = UsuarioPerfilForm()

    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'titulo_pagina': 'Adicionar Novo Usuário'
    }
    return render(request, 'gestao/form_usuario.html', context)


@login_required
@transaction.atomic
def editar_usuario(request, user_id):
    """Renderiza e processa o formulário de edição de um usuário e seu perfil."""
    user = get_object_or_404(User, pk=user_id)
    perfil, _ = UsuarioPerfil.objects.get_or_create(user=user)

    if request.method == 'POST':
        user_form = CustomUserChangeForm(request.POST, instance=user)
        profile_form = UsuarioPerfilForm(request.POST, request.FILES, instance=perfil)
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, f'Usuário "{user.username}" atualizado com sucesso!')
            return redirect('gestao:configuracoes')
    else:
        user_form = CustomUserChangeForm(instance=user)
        profile_form = UsuarioPerfilForm(instance=perfil)

    context = {
        'user_form': user_form, 'profile_form': profile_form,
        'usuario_editado': user,
        'titulo_pagina': f'Editar Usuário: {user.username}'
    }
    return render(request, 'gestao/form_usuario.html', context)


@require_POST
@login_required
def ativar_desativar_usuario(request, user_id):
    """Ativa ou desativa uma conta de usuário."""
    user = get_object_or_404(User, pk=user_id)
    if user == request.user:
        messages.error(request, 'Você não pode desativar seu próprio usuário.')
    else:
        user.is_active = not user.is_active
        user.save()
        status = "ativado" if user.is_active else "desativado"
        messages.info(request, f'Usuário "{user.username}" foi {status}.')
    return redirect('gestao:configuracoes')


@login_required
def get_permissoes_grupo_ajax(request, group_id):
    """Retorna as permissões de um grupo em JSON para o frontend."""
    grupo = get_object_or_404(Group, pk=group_id)
    permissoes_ids = list(grupo.permissions.values_list('id', flat=True))
    return JsonResponse({'permissoes_ids': permissoes_ids})

@require_POST
@login_required
def salvar_permissoes_grupo(request, group_id):
    """Salva as permissões selecionadas para um grupo."""
    grupo = get_object_or_404(Group, pk=group_id)
    permissoes_ids = request.POST.getlist('permissoes')
    permissoes = Permission.objects.filter(pk__in=permissoes_ids)
    grupo.permissions.set(permissoes)
    messages.success(request, f'Permissões do grupo "{grupo.name}" salvas com sucesso!')
    return redirect('gestao:configuracoes')


@require_POST
@login_required
def salvar_cadastro_auxiliar_ajax(request, modelo, pk=None):
    """
    View genérica e refatorada para salvar (criar/editar) cadastros auxiliares via AJAX.
    Retorna o HTML do item renderizado para atualização dinâmica da interface.
    """
    try:
        ModelClass = apps.get_model('gestao', modelo)

        # Mapeamento central de modelos para seus respectivos formulários completos
        form_mapping = {
            'TipoServico': TipoServicoForm,
            'AreaProcesso': AreaProcessoForm,
            'TipoAcao': TipoAcaoForm,
            'TipoMovimentacao': TipoMovimentacaoForm,
        }
        FormClass = form_mapping.get(modelo)

        if not FormClass:
            return JsonResponse({'status': 'error', 'message': 'Modelo de cadastro inválido.'}, status=400)

        instance = get_object_or_404(ModelClass, pk=pk) if pk else None

        # Para adicionar um item simples, usamos um formulário dinâmico que só exige o campo 'nome'.
        # Para editar, ou para formulários complexos como TipoAcao, usamos o FormClass completo.
        if not pk and modelo not in ['TipoAcao', 'TipoMovimentacao']:
            # Cria um formulário simples em tempo de execução
            DynamicForm = forms.modelform_factory(ModelClass, fields=['nome'])
            form = DynamicForm(request.POST)
        else:
            form = FormClass(request.POST, instance=instance)

        if form.is_valid():
            instance = form.save()

            # Prepara o contexto para renderizar o template parcial do item
            context = {
                'item': instance,
                'modelo': modelo,
                'form': FormClass(instance=instance)  # Passa um form populado para o modo de edição
            }

            # Escolhe o template parcial correto para renderizar o item
            if modelo == 'TipoAcao':
                template_path = 'gestao/partials/_cadastro_tipo_acao_item.html'
                context['areas_processo'] = AreaProcesso.objects.all()
            elif modelo == 'TipoMovimentacao':
                template_path = 'gestao/partials/_cadastro_tipo_movimentacao_item.html'
            else:
                template_path = 'gestao/partials/_cadastro_auxiliar_list_item.html'

            item_html = render_to_string(template_path, context, request=request)

            return JsonResponse({
                'status': 'success',
                'pk': instance.pk,
                'is_new': pk is None,
                'item_html': item_html
            })
        else:
            return JsonResponse({'status': 'error', 'errors': form.errors.get_json_data()}, status=400)

    except Exception as e:
        logger.error(f"Erro em salvar_cadastro_auxiliar_ajax: {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@require_POST
@login_required
def excluir_cadastro_auxiliar_ajax(request, modelo, pk):
    """View genérica para excluir cadastros auxiliares via AJAX."""
    try:
        ModelClass = apps.get_model('gestao', modelo)
        instance = get_object_or_404(ModelClass, pk=pk)
        instance.delete()
        return JsonResponse({'status': 'success'})
    except Exception:
        return JsonResponse(
            {'status': 'error', 'message': 'Não foi possível excluir. O item pode estar em uso.'}, status=400)


# ==============================================================================
# SEÇÃO: VIEWS PARCIAIS E AJAX DIVERSAS
# ==============================================================================

@login_required
def atualizar_tabela_financeira_partial(request, parent_pk, parent_type):
    """Retorna o HTML parcial da tabela financeira para um processo ou serviço."""
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
        logger.error(f"Erro ao atualizar tabela financeira: {e}", exc_info=True)
        return JsonResponse({'error': f'Erro interno do servidor.'}, status=500)


@login_required
def atualizar_componentes_financeiros_servico(request, pk):
    """Retorna o HTML renderizado para os componentes financeiros de um serviço."""
    servico = get_object_or_404(Servico, pk=pk)
    # Lógica financeira idêntica à de 'detalhe_servico' para consistência
    # ...
    context = {
        # ... (montar contexto financeiro completo como em 'detalhe_servico')
    }
    resumo_html = render_to_string('gestao/partials/_servico_resumo_financeiro.html', context, request=request)
    tabela_html = render_to_string('gestao/partials/_tabela_financeira.html', context, request=request)
    return JsonResponse({'resumo_financeiro_html': resumo_html, 'tabela_financeira_html': tabela_html})


@login_required
def atualizar_historico_servico_partial(request, servico_pk):
    """Retorna apenas o HTML renderizado da timeline de andamentos de um serviço."""
    servico = get_object_or_404(Servico, pk=servico_pk)
    movimentacoes = servico.movimentacoes_servico.all().order_by('-data_atividade', '-data_criacao')
    return render(request, 'gestao/partials/_historico_movimentacoes_servico.html', {'movimentacoes': movimentacoes})


@require_POST
@login_required
def adicionar_tipo_servico_modal(request):
    """Processa a adição de um novo Tipo de Serviço via modal e retorna JSON."""
    form = TipoServicoForm(request.POST)
    if form.is_valid():
        tipo_servico = form.save()
        return JsonResponse({'status': 'success', 'pk': tipo_servico.pk, 'nome': str(tipo_servico)})
    return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)


@require_POST
@login_required
def adicionar_cliente_modal(request):
    """Processa a adição de um novo Cliente via modal e retorna JSON."""
    form = ClienteModalForm(request.POST)
    if form.is_valid():
        cliente = form.save()
        return JsonResponse({'status': 'success', 'pk': cliente.pk, 'nome': str(cliente)})
    return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)


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
    """Marca um item da agenda (movimentação de processo ou serviço) como 'CONCLUIDA'."""
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
        return JsonResponse({'success': False, 'error': 'Item não encontrado ou sem permissão'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ==============================================================================
# SEÇÃO: IMPORTAÇÃO PROJUDI E NFS-e
# ==============================================================================

@login_required
def importacao_projudi_view(request):
    """Renderiza a página de importação de dados do Projudi."""
    todos_processos = Processo.objects.select_related('advogado_responsavel').prefetch_related(
        'partes__cliente').order_by('-data_distribuicao')
    context = {
        'titulo_pagina': "Importador Inteligente do Projudi",
        'todos_processos': todos_processos,
    }
    return render(request, 'gestao/importacao/importar_projudi.html', context)


@require_POST
@login_required
def analisar_dados_projudi_ajax(request):
    """
    Recebe o JSON do Projudi, identifica o tipo (Prazos ou Audiências), processa os dados
    e retorna o HTML de pré-visualização correto.
    """
    try:
        data = json.loads(request.body)
        payload = data.get('payload', [])

        # Validação inicial do payload
        if not isinstance(payload, list) or not payload:
            return JsonResponse(
                {'status': 'error', 'message': 'O JSON está vazio ou não é um formato de lista válido.'}, status=400)

        # Determina o tipo de importação pelo conteúdo do primeiro item
        import_type = 'movimentacoes' if 'parteIntimada' in payload[0] else 'audiencias'

        todos_clientes = Cliente.objects.all().order_by('nome_completo')
        dados_analisados = []

        mapa_polos = {
            'autor': 'AUTOR', 'autora': 'AUTOR', 'requerente': 'AUTOR', 'polo ativo': 'AUTOR', 'exequente': 'AUTOR',
            'réu': 'REU', 'ré': 'REU', 'requerido': 'REU', 'requerida': 'REU', 'polo passivo': 'REU',
            'executado': 'REU',
            'vítima': 'VITIMA', 'terceiro': 'TERCEIRO'
        }

        # --- LÓGICA PARA PRAZOS / MOVIMENTAÇÕES ---
        if import_type == 'movimentacoes':
            movimentacoes_agrupadas = {}
            for mov_data in payload:
                num_processo = mov_data.get('processoRecurso')
                if not num_processo: continue
                chave = (num_processo, mov_data.get('dtPostagem'), mov_data.get('dataIntimacao'), mov_data.get('prazo'))
                if chave not in movimentacoes_agrupadas:
                    movimentacoes_agrupadas[chave] = {'mov_data': mov_data, 'partes_intimadas': set()}
                if mov_data.get('parteIntimada'):
                    movimentacoes_agrupadas[chave]['partes_intimadas'].add(mov_data.get('parteIntimada'))

            for grupo in movimentacoes_agrupadas.values():
                mov_data = grupo['mov_data']
                analise = {'movimentacao': mov_data, 'processo': {}, 'partes': []}
                num_processo = mov_data.get('processoRecurso')
                processo_qs = Processo.objects.filter(numero_processo=num_processo)
                analise['processo'] = {'numero': num_processo, 'existe': processo_qs.exists(),
                                       'id': processo_qs.first().id if processo_qs.exists() else None}

                for parte_completa in grupo['partes_intimadas']:
                    nome_final = parte_completa.strip()
                    poloSugerido = ''
                    last_paren_index = nome_final.rfind('(')
                    if last_paren_index != -1 and nome_final.endswith(')'):
                        nome_bruto = nome_final[:last_paren_index].strip()
                        polo_encontrado = nome_final[last_paren_index + 1:-1].strip().lower()
                        nome_final = nome_bruto.split('representado(a) por')[0].strip()
                        for termo, polo_sistema in mapa_polos.items():
                            if termo in polo_encontrado: poloSugerido = polo_sistema; break
                    cliente_qs = Cliente.objects.filter(nome_completo__iexact=nome_final)
                    analise['partes'].append(
                        {'nome_original': parte_completa, 'nome_sugerido': nome_final, 'polo': poloSugerido,
                         'existe': cliente_qs.exists(),
                         'cliente_id': cliente_qs.first().id if cliente_qs.exists() else None})
                dados_analisados.append(analise)

            contexto_extra = {'todos_tipos_movimentacao': TipoMovimentacao.objects.all().order_by('-favorito', 'nome')}

        # --- LÓGICA PARA AUDIÊNCIAS ---
        elif import_type == 'audiencias':
            for audiencia_data in payload:
                num_processo = audiencia_data.get('processoRecurso')
                if not num_processo: continue
                analise = {'audiencia': audiencia_data, 'processo': {}, 'partes': []}
                processo_qs = Processo.objects.filter(numero_processo=num_processo)
                analise['processo'] = {'numero': num_processo, 'existe': processo_qs.exists()}
                partes_dict = audiencia_data.get('partes')
                if not isinstance(partes_dict, dict): continue
                for polo_str, nomes_partes in partes_dict.items():
                    polo_sistema = 'TERCEIRO'
                    polo_lower = polo_str.lower() if polo_str else ''
                    for termo, polo_map in mapa_polos.items():
                        if termo in polo_lower: polo_sistema = polo_map; break
                    if not isinstance(nomes_partes, list): continue
                    for nome in nomes_partes:
                        if not nome: continue
                        nome_limpo = nome.split('representado(a) por')[0].strip()
                        cliente_qs = Cliente.objects.filter(nome_completo__iexact=nome_limpo)
                        analise['partes'].append(
                            {'nome_sugerido': nome_limpo, 'polo': polo_sistema, 'existe': cliente_qs.exists(),
                             'cliente_id': cliente_qs.first().id if cliente_qs.exists() else None})
                dados_analisados.append(analise)
            contexto_extra = {
                'todos_tipos_movimentacao': TipoMovimentacao.objects.filter(nome__icontains='audiencia').order_by(
                    'nome')}

        else:
            return JsonResponse({'status': 'error', 'message': 'Tipo de dado para importação não reconhecido.'},
                                status=400)

        context = {
            'dados_analisados': dados_analisados,
            'todos_clientes': todos_clientes,
            'csrf_token': get_token(request),
            'import_type': import_type,
            **contexto_extra
        }

        html_preview = render_to_string('gestao/partials/_importacao_projudi_preview.html', context, request=request)
        return JsonResponse({'status': 'success', 'html_preview': html_preview})

    except Exception as e:
        logger.error(f"Erro ao analisar dados do Projudi: {e}", exc_info=True)
        if settings.DEBUG:
            import traceback
            traceback.print_exc()
        return JsonResponse({'status': 'error', 'message': f'Ocorreu um erro interno no servidor: {str(e)}'},
                            status=500)


@require_POST
@login_required
def confirmar_importacao_projudi(request):
    """
    PASSO 2 DO WIZARD:
    Processa os dados revisados do Passo 1, filtrando apenas os itens marcados,
    gera um resumo detalhado e renderiza a página de confirmação.
    """
    indices_para_importar = request.POST.getlist('importar_indice')
    if not indices_para_importar:
        messages.warning(request, "Nenhum item foi selecionado para importação.")
        return redirect('gestao:importacao_projudi')

    import_type = request.POST.get('import_type')
    dados_para_confirmacao = []
    resumo_detalhado = {'movimentacoes': [], 'clientes_envolvidos': []}

    try:
        locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
    except locale.Error:
        locale.setlocale(locale.LC_TIME, 'Portuguese_Brazil.1252')

    for index in indices_para_importar:
        # --- Coleta de dados comuns ---
        partes = []
        i = 0
        while True:
            nome_parte = request.POST.get(f'processo_{index}_parte_{i}_nome')
            if nome_parte is None: break
            partes.append({
                'nome': nome_parte,
                'polo': request.POST.get(f'processo_{index}_parte_{i}_polo'),
                'id_vincular': request.POST.get(f'processo_{index}_parte_{i}_id_vincular')
            })
            i += 1

        item_data = {
            'processo_numero': request.POST.get(f'processo_{index}_numero'),
            'tipo_movimentacao_id': request.POST.get(f'processo_{index}_tipo_movimentacao'),
            'partes': partes
        }

        # --- Coleta de dados específicos e montagem do resumo ---
        if import_type == 'movimentacoes':
            prazo_original = request.POST.get(f'movimentacao_{index}_prazo', '')
            item_data['movimentacao_prazo'] = prazo_original
            item_data['movimentacao_intimacao'] = request.POST.get(f'movimentacao_{index}_intimacao')

            # Resumo da Movimentação
            prazo_calculado = ""
            if 'dias' in prazo_original.lower():
                dias = re.search(r'\d+', prazo_original)
                prazo_calculado = f"{dias.group(0)} dias" if dias else prazo_original
            else:
                try:
                    prazo_calculado = datetime.strptime(prazo_original, '%d de %B de %Y').date().strftime('%d/%m/%Y')
                except (ValueError, TypeError):
                    prazo_calculado = prazo_original

            resumo_detalhado['movimentacoes'].append({
                'numero_processo': item_data['processo_numero'],
                'tipo': TipoMovimentacao.objects.get(pk=item_data['tipo_movimentacao_id']).nome,
                'intimacao': item_data['movimentacao_intimacao'],
                'prazo_final': prazo_calculado
            })

        elif import_type == 'audiencias':
            item_data['audiencia_data'] = request.POST.get(f'audiencia_{index}_data')
            item_data['audiencia_hora'] = request.POST.get(f'audiencia_{index}_hora')
            item_data['audiencia_detalhes'] = request.POST.get(f'audiencia_{index}_detalhes')
            item_data['clientes_principais_indices'] = request.POST.getlist(f'processo_{index}_cliente_principal')

            # Resumo da Audiência
            resumo_detalhado['movimentacoes'].append({
                'numero_processo': item_data['processo_numero'],
                'tipo': TipoMovimentacao.objects.get(pk=item_data['tipo_movimentacao_id']).nome,
                'intimacao': f"{item_data['audiencia_data']} às {item_data['audiencia_hora']}",
                'prazo_final': item_data['audiencia_data']
            })

        # Resumo dos Clientes (comum a ambos)
        for i, parte_data in enumerate(partes):
            status_cliente = ""
            if parte_data.get('id_vincular'):
                status_cliente = "Vinculado a cadastro existente"
            elif not Cliente.objects.filter(nome_completo__iexact=parte_data['nome']).exists():
                status_cliente = "Novo cadastro a ser criado"
            else:
                status_cliente = "Será vinculado ao cadastro com este nome"
            resumo_detalhado['clientes_envolvidos'].append(
                {'nome': parte_data['nome'], 'polo': dict(ParteProcesso.TIPO_CHOICES).get(parte_data['polo']),
                 'status': status_cliente})

        dados_para_confirmacao.append(item_data)

    request.session['dados_importacao_projudi'] = {'import_type': import_type, 'itens': dados_para_confirmacao}
    context = {'resumo': resumo_detalhado, 'total_a_importar': len(indices_para_importar)}
    return render(request, 'gestao/importacao/importacao_projudi_confirmacao.html', context)


@require_POST
@login_required
@transaction.atomic
def executar_importacao_projudi(request):
    """
    PASSO FINAL DO WIZARD:
    Pega os dados da sessão e finalmente os salva no banco de dados.
    Lida com múltiplos clientes principais em audiências.
    """
    dados_sessao = request.session.get('dados_importacao_projudi', {})
    if not dados_sessao:
        messages.error(request, "Nenhum dado para importação. A sessão pode ter expirado.")
        return redirect('gestao:importacao_projudi')

    import_type = dados_sessao.get('import_type')
    itens_para_importar = dados_sessao.get('itens', [])
    sucesso_count = 0
    erro_count = 0

    try:
        locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
    except locale.Error:
        locale.setlocale(locale.LC_TIME, 'Portuguese_Brazil.1252')

    for item in itens_para_importar:
        try:
            # 1. Obter ou Criar o Processo
            processo_obj, _ = Processo.objects.get_or_create(
                numero_processo=item['processo_numero'],
                defaults={'advogado_responsavel': request.user, 'descricao_caso': 'Processo importado via Projudi.'}
            )

            # 2. Obter ou Criar as Partes e associá-las
            for i, parte_data in enumerate(item['partes']):
                if parte_data.get('id_vincular'):
                    cliente_obj = Cliente.objects.get(pk=parte_data['id_vincular'])
                else:
                    cliente_obj, _ = Cliente.objects.get_or_create(
                        nome_completo__iexact=parte_data['nome'],
                        defaults={'nome_completo': parte_data['nome']}
                    )

                is_cliente_principal = False
                if import_type == 'movimentacoes':
                    is_cliente_principal = True
                elif import_type == 'audiencias':
                    is_cliente_principal = str(i) in item.get('clientes_principais_indices', [])

                ParteProcesso.objects.update_or_create(
                    processo=processo_obj, cliente=cliente_obj,
                    defaults={'tipo_participacao': parte_data['polo'], 'is_cliente_do_processo': is_cliente_principal}
                )

            # 3. Criar a Movimentação
            mov = Movimentacao(processo=processo_obj, responsavel=request.user,
                               tipo_movimentacao_id=item['tipo_movimentacao_id'])

            if import_type == 'movimentacoes':
                prazo_str = item.get('movimentacao_prazo', '').strip().lower()
                mov.titulo = f"Intimação via Projudi - Prazo: {prazo_str}"
                if 'dias' in prazo_str:
                    dias = re.search(r'\d+', prazo_str)
                    if dias: mov.dias_prazo = int(dias.group(0))
                else:
                    try:
                        mov.data_prazo_final = datetime.strptime(prazo_str, '%d de %B de %Y').date()
                    except (ValueError, TypeError):
                        mov.detalhes = f"Prazo original: '{prazo_str}'"

                intimacao_str = item.get('movimentacao_intimacao')
                if intimacao_str:
                    try:
                        mov.data_intimacao = datetime.strptime(intimacao_str, '%d/%m/%Y').date()
                    except (ValueError, TypeError):
                        pass

            elif import_type == 'audiencias':
                tipo_mov_nome = TipoMovimentacao.objects.get(pk=item['tipo_movimentacao_id']).nome
                mov.titulo = tipo_mov_nome
                data_str = item.get('audiencia_data')
                hora_str = item.get('audiencia_hora')
                if data_str: mov.data_prazo_final = datetime.strptime(data_str, '%d/%m/%Y').date()
                if hora_str: mov.hora_prazo = datetime.strptime(hora_str, '%H:%M').time()
                mov.detalhes = item.get('audiencia_detalhes', '')

            mov.save()
            sucesso_count += 1
        except Exception as e:
            print(f"Erro ao importar item: {item}. Erro: {e}")
            erro_count += 1

    if 'dados_importacao_projudi' in request.session:
        del request.session['dados_importacao_projudi']

    messages.success(request, f"{sucesso_count} itens importados com sucesso.")
    if erro_count > 0:
        messages.warning(request, f"{erro_count} itens não puderam ser importados.")

    return redirect('gestao:dashboard')

@require_POST
@login_required
def emitir_nfse_view(request, servico_pk):
    """Dispara o serviço de emissão de NFS-e para um serviço."""
    service = NFSEService()
    resultado = service.enviar_rps_para_emissao(servico_pk)
    if resultado['status'] == 'sucesso':
        messages.success(request, resultado['mensagem'])
    else:
        messages.error(request, resultado['mensagem'])
    return redirect('gestao:detalhe_servico', pk=servico_pk)


@require_POST
@login_required
def salvar_cadastro_auxiliar_ajax(request, modelo, pk=None):
    """
    View genérica e refatorada para salvar (criar/editar) cadastros auxiliares via AJAX.
    Retorna o HTML do item renderizado para atualização dinâmica da interface.
    """
    try:
        ModelClass = apps.get_model('gestao', modelo)

        # Mapeamento central de modelos para seus respectivos formulários completos
        form_mapping = {
            'TipoServico': TipoServicoForm,
            'AreaProcesso': AreaProcessoForm,
            'TipoAcao': TipoAcaoForm,
            'TipoMovimentacao': TipoMovimentacaoForm,
        }
        FormClass = form_mapping.get(modelo)

        if not FormClass:
            return JsonResponse({'status': 'error', 'message': 'Modelo de cadastro inválido.'}, status=400)

        instance = get_object_or_404(ModelClass, pk=pk) if pk else None

        # Para adicionar um item simples, usamos um formulário dinâmico que só exige o campo 'nome'.
        # Para editar, ou para formulários complexos como TipoAcao, usamos o FormClass completo.
        if not pk and modelo not in ['TipoAcao']:
            # Cria um formulário simples em tempo de execução
            DynamicForm = forms.modelform_factory(ModelClass, fields=['nome'])
            form = DynamicForm(request.POST)
        else:
            form = FormClass(request.POST, instance=instance)

        if form.is_valid():
            instance = form.save()

            # Prepara o contexto para renderizar o template parcial do item
            context = {
                'item': instance,
                'modelo': modelo,
                'form': FormClass(instance=instance)  # Passa um form populado para o modo de edição
            }

            # Escolhe o template parcial correto para renderizar o item
            if modelo == 'TipoAcao':
                template_path = 'gestao/partials/_cadastro_tipo_acao_item.html'
                # Para TipoAcao, precisamos passar as áreas para o formulário de edição
                context['areas_processo'] = AreaProcesso.objects.all()
            else:
                template_path = 'gestao/partials/_cadastro_auxiliar_list_item.html'

            item_html = render_to_string(template_path, context, request=request)

            return JsonResponse({
                'status': 'success',
                'pk': instance.pk,
                'is_new': pk is None,
                'item_html': item_html
            })
        else:
            return JsonResponse({'status': 'error', 'errors': form.errors.get_json_data()}, status=400)

    except Exception as e:
        logger.error(f"Erro em salvar_cadastro_auxiliar_ajax: {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
def calculo_wizard_view(request: HttpRequest, processo_pk: int | None = None):
    """
    Renderiza a página principal do wizard de cálculo judicial.
    Carrega o catálogo de índices e o passa para o template como JSON.
    """
    processo = None
    if processo_pk:
        processo = get_object_or_404(Processo, pk=processo_pk)

    indices_catalog_json = json.dumps(public_catalog_for_api(), ensure_ascii=False)

    context = {
        'titulo_pagina': 'Calculadora Judicial Completa',
        'processo': processo,
        'indices_catalog_json': indices_catalog_json,
    }
    return render(request, "gestao/calculo_wizard.html", context)


@require_POST
@login_required
@transaction.atomic
def simular_calculo_api(request: HttpRequest):
    """
    Endpoint da API que calcula, salva o resultado e retorna para a interface.
    Inclui uma função robusta para sanitizar os dados recebidos do frontend.
    """

    def sanitize_payload(payload):
        """
        Função interna para limpar e converter dados monetários e de datas
        antes de passá-los para o motor de cálculo.
        """

        def _to_decimal(value: str | int | float | None) -> str:
            """Converte uma string monetária (ex: "1.234,56") para um formato que o Python entende ("1234.56")."""
            if value is None: return '0.00'
            s_value = str(value).strip().replace('.', '').replace(',', '.')
            try:
                # Valida se é um número válido antes de retornar
                float(s_value)
                return s_value
            except (ValueError, TypeError):
                return '0.00'

        for parcela in payload.get('parcelas', []):
            parcela['valor_original'] = _to_decimal(parcela.get('valor_original'))
            for faixa in parcela.get('faixas', []):
                faixa['juros_taxa_mensal'] = _to_decimal(faixa.get('juros_taxa_mensal'))

        extras = payload.get('extras', {})
        if isinstance(extras, dict):
            extras['multa_percentual'] = _to_decimal(extras.get('multa_percentual'))
            extras['honorarios_percentual'] = _to_decimal(extras.get('honorarios_percentual'))

        return payload

    try:
        payload = json.loads(request.body)
        sanitized_payload = sanitize_payload(payload)

        if not sanitized_payload.get('parcelas'):
            return JsonResponse({'status': 'error', 'message': 'Nenhuma parcela foi enviada para cálculo.'}, status=400)

        engine = CalculoEngine(sanitized_payload)
        resultados = engine.run()

        processo_numero = sanitized_payload.get('global', {}).get('numero_processo')
        processo = Processo.objects.filter(numero_processo=processo_numero).first() if processo_numero else None

        resultados['form_data'] = sanitized_payload

        rascunho = CalculoRascunho.objects.create(
            processo=processo,
            descricao=sanitized_payload.get('global', {}).get('observacoes') or "Cálculo gerado pelo Wizard",
            usuario_criacao=request.user,
            ultimo_resultado_json=resultados
        )

        return JsonResponse({
            'status': 'success',
            'data': resultados,
            'rascunho_pk': rascunho.pk
        })

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Erro: O formato dos dados enviados é inválido.'},
                            status=400)
    except Exception as e:
        logger.error(f"Erro inesperado na API de simulação de cálculo: {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': f'Ocorreu um erro inesperado no servidor: {e}'}, status=500)


# ==============================================================================
# VIEWS DA API DE ÍNDICES (RESTAURADAS)
# ==============================================================================

@login_required
def api_indices_catalogo(request: HttpRequest):
    """Retorna o catálogo de índices disponíveis para o frontend."""
    return JsonResponse({"indices": public_catalog_for_api()})


@login_required
def api_indices_valores(request: HttpRequest):
    """Retorna os valores de um índice específico em um período."""
    nome = request.GET.get("indice")
    ini = request.GET.get("inicio")
    fim = request.GET.get("fim")
    if not (nome and ini and fim):
        return HttpResponseBadRequest("Parâmetros obrigatórios: indice, inicio, fim (YYYY-MM-DD).")

    try:
        data_inicio = date.fromisoformat(ini)
        data_fim = date.fromisoformat(fim)
    except Exception:
        return HttpResponseBadRequest("Datas inválidas (use YYYY-MM-DD).")

    svc = ServicoIndices()
    try:
        valores = svc.get_indices_por_periodo(nome, data_inicio, data_fim)
        return JsonResponse({"indice": nome, "valores": valores})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


# @login_required
# def gerar_calculo_pdf(request, rascunho_pk):
#     """
#     Gera um PDF a partir de um resultado de cálculo salvo.
#     """
#     if not HTML:
#         messages.error(request, "A biblioteca 'weasyprint' não está instalada, o que impede a geração de PDFs.")
#         return redirect(request.META.get('HTTP_REFERER', 'gestao:dashboard'))
#
#     rascunho = get_object_or_404(CalculoRascunho.objects.select_related('processo'), pk=rascunho_pk)
#     resultado_json = rascunho.ultimo_resultado_json
#
#     if not resultado_json:
#         messages.error(request, "Não há dados de resultado para gerar o PDF.")
#         return redirect(request.META.get('HTTP_REFERER', 'gestao:dashboard'))
#
#     context = {
#         'rascunho': rascunho,
#         'resultado': resultado_json,
#         'processo': rascunho.processo,
#         'dados_basicos': resultado_json.get('global', {})
#     }
#
#     html_string = render_to_string('gestao/calculo_pdf.html', context)
#     response = HttpResponse(content_type='application/pdf')
#     response['Content-Disposition'] = f'attachment; filename="calculo_judicial_{rascunho.pk}.pdf"'
#
#     HTML(string=html_string).write_pdf(response)
#     return response
#

@login_required
def api_indices_catalogo(request: HttpRequest):
    """
    Retorna o catálogo de índices econômicos disponíveis para o frontend.
    Esta view é essencial para o funcionamento do Wizard de Cálculo.
    """
    try:
        # A função public_catalog_for_api() está em gestao/services/indices/catalog.py
        indices = public_catalog_for_api()
        return JsonResponse({"indices": indices})
    except Exception as e:
        logger.error(f"Erro ao buscar o catálogo de índices: {e}", exc_info=True)
        return JsonResponse({"error": "Não foi possível carregar o catálogo de índices."}, status=500)


@login_required
def api_indices_valores(request: HttpRequest):
    """
    (Opcional/Futuro) Retorna os valores de um índice específico em um período.
    """
    nome = request.GET.get("indice")
    ini = request.GET.get("inicio")
    fim = request.GET.get("fim")
    if not (nome and ini and fim):
        return HttpResponseBadRequest("Parâmetros obrigatórios: indice, inicio, fim (YYYY-MM-DD).")

    try:
        data_inicio = date.fromisoformat(ini)
        data_fim = date.fromisoformat(fim)
    except Exception:
        return HttpResponseBadRequest("Datas inválidas (use YYYY-MM-DD).")

    svc = ServicoIndices()
    try:
        valores = svc.get_indices_por_periodo(nome, data_inicio, data_fim)
        return JsonResponse({"indice": nome, "valores": valores})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)

def _to_decimal_br(v):
    """
    Converte '1.234,56' ou '1234.56' em Decimal('1234.56').
    Aceita int/float/Decimal diretamente.
    """
    if isinstance(v, Decimal):
        return v
    if isinstance(v, (int, float)):
        return Decimal(str(v))
    if not v:
        return Decimal('0')
    s = str(v).strip()
    # troca separador decimal brasileiro -> ponto
    if "," in s and "." in s:
        # remove milhares e troca decimal
        s = s.replace(".", "").replace(",", ".")
    elif "," in s and "." not in s:
        s = s.replace(",", ".")
    try:
        return Decimal(s)
    except Exception:
        return Decimal('0')

def _parse_decimal(value, default=Decimal("0")):
    if value is None:
        return default
    if isinstance(value, (int, float, Decimal)):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return default
    # aceita “1.234,56” e “1,234.56”
    s = str(value).strip().replace(" ", "")
    s = s.replace(".", "").replace(",", ".") if s.count(",") == 1 and s.count(".") >= 1 else s.replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation:
        return default


def _parse_date_br(s):
    # aceita dd/mm/aaaa
    return datetime.strptime(s, "%d/%m/%Y").date()


def _resolver_indice_por_payload(svc: ServicoIndices, payload_val: dict | str | None):
    """
    Recebe:
      - payload_val = {'indice_id': 'SELIC_DIARIA'}  (preferencial)
      - OU payload_val = {'indice': 'SELIC (Taxa diária)'} (fallback)
      - OU payload_val = 'SELIC (Taxa diária)' (compatibilidade legada)
    Retorna um dict: {'id': '...', 'provider': '...', 'params': {...}, 'label': '...'}
    Levanta ValueError se não encontrar.
    """
    if not payload_val:
        raise ValueError("Índice não informado.")

    indice_id = None
    label = None

    if isinstance(payload_val, dict):
        indice_id = payload_val.get("indice_id") or payload_val.get("id") or None
        label = payload_val.get("indice") or payload_val.get("label") or None
    elif isinstance(payload_val, str):
        label = payload_val

    meta = None

    # 1) Tenta por id do catálogo (melhor caminho)
    if indice_id:
        meta = svc.get_meta(indice_id)

    # 2) Se não vier id, tenta casar pelo rótulo/nome
    if not meta and label:
        meta = svc.match_by_label(label)

    # 3) Normalização específica: “SELIC” → opção diária do catálogo
    if not meta and label and "SELIC" in label.upper():
        meta = svc.match_by_label("SELIC (Taxa diária)")

    if not meta:
        raise ValueError(f"Índice inválido: {payload_val!r}")

    # Garante provider e params preenchidos (incluindo 'code' para SGS)
    return {
        "id": meta["id"],
        "provider": meta["provider"],
        "params": dict(meta.get("params", {})),  # cópia defensiva
        "label": meta.get("label") or meta.get("name") or meta["id"],
    }

def _parse_date_smart(s: str) -> date:
    s = (s or "").strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            pass
    raise ValueError(f"Data inválida: '{s}'. Use dd/mm/aaaa.")

def _parse_date_smart(s: str) -> date:
    s = (s or "").strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            pass
    raise ValueError(f"Data inválida: '{s}'. Use dd/mm/aaaa.")


@login_required
@require_POST
def calculo_wizard_calcular(request: HttpRequest):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "erro": "JSON inválido."}, status=400)

    dados_basicos = payload.get("basicos") or {}
    parcelas: List[Dict[str, Any]] = payload.get("parcelas") or []
    extras = payload.get("extras") or {}

    if not parcelas:
        return JsonResponse({"ok": False, "erro": "Inclua ao menos uma parcela."}, status=400)

    svc = ServicoIndices()

    total_corrigido = Decimal("0")
    resultado_parcelas: List[Dict[str, Any]] = []

    try:
        for idx, p in enumerate(parcelas, start=1):
            # valor
            try:
                valor_original = str(p.get("valor") or "0").replace(".", "").replace(",", ".")
                valor_original = Decimal(valor_original)
            except (InvalidOperation, TypeError):
                return JsonResponse({"ok": False, "erro": f"Parcela {idx}: valor inválido."}, status=400)

            # datas
            try:
                data_valor = _parse_date_smart(p.get("data_valor") or p.get("data") or "")
            except ValueError as e:
                return JsonResponse({"ok": False, "erro": f"Parcela {idx}: {e}"}, status=400)

            faixas = p.get("faixas") or []
            valor_corrigido = valor_original

            for j, f in enumerate(faixas, start=1):
                try:
                    inicio = _parse_date_smart(f.get("inicio", ""))
                    fim = _parse_date_smart(f.get("fim", ""))
                except ValueError as e:
                    return JsonResponse({"ok": False, "erro": f"Parcela {idx}, faixa {j}: {e}"}, status=400)

                indice_key = (f.get("indice") or "").strip()
                if not indice_key:
                    return JsonResponse({"ok": False, "erro": f"Parcela {idx}, faixa {j}: selecione um índice."}, status=400)
                if indice_key not in INDICE_CATALOG:
                    return JsonResponse(
                        {"ok": False, "erro": f"Parcela {idx}, faixa {j}: índice inválido '{indice_key}'."},
                        status=400,
                    )

                try:
                    indices = svc.get_indices_por_periodo(indice_key, inicio, fim)
                except Exception as e:
                    return JsonResponse(
                        {"ok": False, "erro": f"Parcela {idx}, faixa {j}: falha ao obter índice ({e})."},
                        status=400,
                    )

                # aplicação de exemplo
                tipo = INDICE_CATALOG[indice_key].get("type", "daily_rate")
                if tipo == "monthly_variation":
                    fator = Decimal("1")
                    for k in sorted(indices.keys()):
                        try:
                            var = (indices[k] or Decimal("0")) / Decimal("100")
                        except Exception:
                            var = Decimal("0")
                        fator *= (Decimal("1") + var)
                    valor_corrigido = (valor_corrigido * fator).quantize(Decimal("0.01"))
                else:
                    fator = Decimal("1")
                    for k in sorted(indices.keys()):
                        try:
                            taxa_aa = (indices[k] or Decimal("0")) / Decimal("100")
                            taxa_dia = taxa_aa / Decimal("252")
                            fator *= (Decimal("1") + taxa_dia)
                        except Exception:
                            continue
                    valor_corrigido = (valor_corrigido * fator).quantize(Decimal("0.01"))

            # extras (passo 3)
            def _to_dec(x) -> Decimal:
                s = str(x or "0").replace(".", "").replace(",", ".")
                return Decimal(s)

            multa_perc = _to_dec(extras.get("multa_perc"))
            honorarios_perc = _to_dec(extras.get("honorarios_perc"))

            if multa_perc:
                valor_corrigido = (valor_corrigido * (Decimal("1") + multa_perc / Decimal("100"))).quantize(Decimal("0.01"))

            valor_final = valor_corrigido
            if honorarios_perc:
                valor_final = (valor_corrigido * (Decimal("1") + honorarios_perc / Decimal("100"))).quantize(Decimal("0.01"))

            total_corrigido += valor_final

            resultado_parcelas.append(
                {
                    "indice": idx,
                    "valor_original": f"{valor_original:.2f}",
                    "valor_corrigido": f"{valor_corrigido:.2f}",
                    "valor_final": f"{valor_final:.2f}",
                    "faixas": faixas,
                }
            )

    except Exception as e:
        # garante JSON legível em qualquer erro não previsto
        return JsonResponse({"ok": False, "erro": f"Falha inesperada: {e}"}, status=400)

    return JsonResponse({"ok": True, "total": f"{total_corrigido:.2f}", "parcelas": resultado_parcelas})

def ajax_calcular(request):
    data = json.loads(request.body.decode('utf-8'))
    return JsonResponse(calcular(data), safe=False)
