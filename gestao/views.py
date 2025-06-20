# gestao/views.py

# Imports do Django
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from datetime import date
import datetime

# Imports de Filtros e Formulários deste App
from .filters import ProcessoFilter, ServicoFilter, ClienteFilter
from .forms import (
    ProcessoForm, MovimentacaoForm, PagamentoForm, ServicoForm,
    ClienteForm, TipoServicoForm, ServicoEditForm, MovimentacaoServicoForm,
    ContratoHonorariosForm, ServicoConcluirForm, ProcessoCreateForm, ParteProcessoFormSet,
    CalculoForm,ModeloDocumentoForm, DocumentoForm
)

from .services import ServicoIndices
from .calculators import CalculadoraMonetaria


# Imports dos Modelos deste App
from .models import (
    Processo, Movimentacao, LancamentoFinanceiro, Pagamento,
    Servico, MovimentacaoServico, Cliente, TipoServico, CalculoJudicial, ModeloDocumento, Documento,
)

from django.template import Context, Template # Adicione este import

from .utils import data_por_extenso


# =================================================================
# VIEWS PRINCIPAIS E DASHBOARD
# =================================================================

@login_required
def dashboard(request):
    """
    Exibe o painel principal com cartões de resumo, prazos futuros e
    uma lista unificada de tarefas pendentes.
    """
    hoje = timezone.now().date()
    proximos_30_dias = hoje + datetime.timedelta(days=30)

    processos_ativos_count = Processo.objects.filter(status_processo='ATIVO').count()
    servicos_ativos_count = Servico.objects.filter(concluido=False, ativo=True).count()

    # Lógica para Tarefas e Serviços Pendentes (Unificado)
    lista_pendencias = []
    status_pendente = ['PENDENTE', 'EM_ANDAMENTO']

    tarefas_processos = Movimentacao.objects.filter(responsavel=request.user, status__in=status_pendente)
    for tarefa in tarefas_processos:
        lista_pendencias.append({
            'tipo': 'processo_tarefa',
            'titulo': tarefa.titulo,
            'objeto_pai': f"Proc: {tarefa.processo.numero_processo or 'N/A'}",
            'url_objeto_pai': reverse('detalhe_processo', args=[tarefa.processo.pk]),
            'status': tarefa.get_status_display(),
            'data_ordem': tarefa.data_criacao
        })

    tarefas_servicos = MovimentacaoServico.objects.filter(responsavel=request.user, status__in=status_pendente)
    for tarefa in tarefas_servicos:
        lista_pendencias.append({
            'tipo': 'servico_tarefa',
            'titulo': tarefa.titulo,
            'objeto_pai': f"Serviço: {tarefa.servico.descricao[:30]}...",
            'url_objeto_pai': reverse('detalhe_servico', args=[tarefa.servico.pk]),
            'status': tarefa.get_status_display(),
            'data_ordem': tarefa.data_criacao
        })

    servicos_pendentes = Servico.objects.filter(responsavel=request.user, concluido=False)
    for servico in servicos_pendentes:
        lista_pendencias.append({
            'tipo': 'servico_geral',
            'titulo': servico.descricao,
            'objeto_pai': f"Cliente: {servico.cliente.nome_completo}",
            'url_objeto_pai': reverse('detalhe_servico', args=[servico.pk]),
            'status': 'Em Andamento',
            'data_ordem': servico.data_inicio
        })

    tarefas_pendentes = sorted(lista_pendencias, key=lambda x: str(x['data_ordem']), reverse=True)
    tarefas_pendentes_count = len(tarefas_pendentes)

    proximos_prazos = Movimentacao.objects.filter(
        responsavel=request.user, data_prazo_final__isnull=False,
        data_prazo_final__gte=hoje, data_prazo_final__lte=proximos_30_dias,
        status__in=['PENDENTE', 'EM_ANDAMENTO']
    ).order_by('data_prazo_final')

    context = {
        'processos_ativos_count': processos_ativos_count,
        'servicos_ativos_count': servicos_ativos_count,
        'tarefas_pendentes_count': tarefas_pendentes_count,
        'proximos_prazos': proximos_prazos,
        'tarefas_pendentes': tarefas_pendentes,
    }
    return render(request, 'gestao/dashboard.html', context)


# =================================================================
# VIEWS DE CRIAÇÃO (ADD)
# =================================================================

@login_required
@require_POST
def adicionar_servico(request):
    """Processa o formulário de adição de um novo serviço e seu contrato de honorários."""
    form_servico = ServicoForm(request.POST)
    form_contrato = ContratoHonorariosForm(request.POST)

    if form_servico.is_valid() and form_contrato.is_valid():
        servico_instance = form_servico.save()
        contrato_instance = form_contrato.save(commit=False)
        contrato_instance.content_object = servico_instance
        contrato_instance.cliente = servico_instance.cliente
        contrato_instance.save()
        return redirect('detalhe_servico', pk=servico_instance.pk)

    # Em caso de falha, o ideal seria redirecionar com uma mensagem de erro.
    # Por simplicidade, redirecionamos para o dashboard.
    # messages.error(request, 'Houve um erro ao salvar o serviço. Verifique os dados.')
    return redirect('dashboard')


@login_required
def adicionar_processo(request):
    """Exibe e processa o formulário para adicionar um novo processo e suas partes."""
    if request.method == 'POST':
        form = ProcessoCreateForm(request.POST)
        formset = ParteProcessoFormSet(request.POST, prefix='partes')
        if form.is_valid() and formset.is_valid():
            processo = form.save()
            formset.instance = processo
            formset.save()
            return redirect('detalhe_processo', pk=processo.pk)
    else:
        form = ProcessoCreateForm()
        formset = ParteProcessoFormSet(prefix='partes')

    context = {'form': form, 'formset': formset}
    return render(request, 'gestao/adicionar_processo.html', context)


# =================================================================
# VIEWS DE LISTAGEM E DETALHE
# =================================================================

@login_required
@login_required
def lista_processos(request):
    """
    Exibe a lista de processos, agora com estatísticas dinâmicas e
    suporte a filtragem via AJAX.
    """
    base_queryset = Processo.objects.all() if request.user.is_superuser else Processo.objects.filter(
        Q(advogado_responsavel=request.user) | Q(advogado_responsavel__isnull=True)
    )

    # Prepara o queryset com prefetch para otimizar o acesso aos nomes das partes
    processo_filter = ProcessoFilter(request.GET,
                                     queryset=base_queryset.select_related(
                                         'tipo_acao', 'advogado_responsavel'
                                     ).prefetch_related('partes__cliente'))

    # Calcula as estatísticas a partir do queryset JÁ FILTRADO
    qs_filtrado = processo_filter.qs
    stats = {
        'total': qs_filtrado.count(),
        'ativos': qs_filtrado.filter(status_processo='ATIVO').count(),
        'suspensos': qs_filtrado.filter(status_processo='SUSPENSO').count(),
        'arquivados': qs_filtrado.filter(status_processo='ARQUIVADO').count(),
    }

    # Se a requisição for AJAX, retorna apenas o template parcial com a lista
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'gestao/partials/_lista_processos_partial.html', {'filter': processo_filter})

    # Para requisições normais, retorna a página completa com o filtro e as estatísticas
    context = {
        'filter': processo_filter,
        'stats': stats
    }
    return render(request, 'gestao/lista_processos.html', context)


@login_required
def detalhe_processo(request, pk):
    """
    Exibe os detalhes de um processo, lida com a adição de novas movimentações
    e prepara o contexto com os formulários e dados necessários para a página.
    """
    # Busca o objeto principal da página, o processo.
    # Adicionamos prefetch_related para otimizar a busca dos documentos vinculados.
    processo = get_object_or_404(Processo.objects.prefetch_related('documentos'), pk=pk)

    # Lida com a submissão do formulário de uma nova movimentação.
    if request.method == 'POST' and 'submit_movimentacao' in request.POST:
        form_movimentacao = MovimentacaoForm(request.POST)
        if form_movimentacao.is_valid():
            nova_movimentacao = form_movimentacao.save(commit=False)
            nova_movimentacao.processo = processo
            nova_movimentacao.save()
            # Redireciona para a mesma página para evitar reenvio do formulário.
            return redirect('detalhe_processo', pk=processo.pk)
    else:
        # Se não for POST, cria um formulário de movimentação em branco.
        form_movimentacao = MovimentacaoForm()

    # --- CORREÇÃO APLICADA AQUI ---
    # Busca todos os modelos de documentos disponíveis no banco de dados.
    # Esta linha define a variável que estava faltando.
    todos_modelos = ModeloDocumento.objects.all()

    # Monta o contexto final que será enviado para o template.
    context = {
        'processo': processo,
        'form_movimentacao': form_movimentacao,
        'form_pagamento': PagamentoForm(),  # Formulário para o modal de pagamento.
        'todos_modelos': todos_modelos,  # Lista de modelos para a nova funcionalidade.
    }

    return render(request, 'gestao/detalhe_processo.html', context)


@login_required
def lista_servicos(request):
    """Exibe a lista de todos os serviços extrajudiciais com filtros dinâmicos."""
    base_queryset = Servico.objects.select_related('cliente', 'tipo_servico', 'responsavel').all()
    servico_filter = ServicoFilter(request.GET, queryset=base_queryset)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'gestao/partials/_lista_servicos_partial.html', {'filter': servico_filter})

    context = {'filter': servico_filter}
    return render(request, 'gestao/lista_servicos.html', context)


@login_required
def detalhe_servico(request, pk):
    """Exibe os detalhes de um serviço e processa a adição de novas tarefas."""
    servico = get_object_or_404(Servico, pk=pk)
    if request.method == 'POST':
        form_movimentacao = MovimentacaoServicoForm(request.POST)
        if form_movimentacao.is_valid():
            nova_movimentacao = form_movimentacao.save(commit=False)
            nova_movimentacao.servico = servico
            nova_movimentacao.responsavel = request.user
            nova_movimentacao.save()
            return redirect('detalhe_servico', pk=servico.pk)
    else:
        form_movimentacao = MovimentacaoServicoForm()

    context = {
        'servico': servico,
        'form_movimentacao': form_movimentacao,
        'form_pagamento': PagamentoForm(),
    }
    return render(request, 'gestao/detalhe_servico.html', context)


# =================================================================
# VIEWS DE MODAL (AJAX)
# =================================================================

@require_POST
@login_required
def adicionar_cliente_modal(request):
    """Processa a adição de um novo Cliente via modal e retorna JSON."""
    form = ClienteForm(request.POST)
    if form.is_valid():
        cliente = form.save()
        return JsonResponse({
            'status': 'success',
            'pk': cliente.pk,
            'nome': str(cliente)  # Usa a representação string do modelo
        })
    # CORREÇÃO: Retorna os erros do formulário diretamente. status=400 indica um Bad Request.
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
    # CORREÇÃO: Padroniza o retorno de erro e o status HTTP.
    return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)


# =================================================================
# DEMAIS VIEWS (CRUD, Financeiro, etc.)
# =================================================================
# A seguir, as demais views do seu arquivo, que não necessitam de alteração
# para o problema específico dos modais.

@login_required
def editar_processo(request, pk):
    processo = get_object_or_404(Processo, pk=pk)
    form = ProcessoForm(request.POST or None, instance=processo)
    if form.is_valid():
        form.save()
        return redirect('detalhe_processo', pk=processo.pk)
    return render(request, 'gestao/editar_processo.html', {'form': form, 'processo': processo})


@login_required
def editar_servico(request, pk):
    servico = get_object_or_404(Servico, pk=pk)
    form = ServicoEditForm(request.POST or None, instance=servico)
    if form.is_valid():
        form.save()
        return redirect('detalhe_servico', pk=servico.pk)
    return render(request, 'gestao/editar_servico.html', {'form': form, 'servico': servico})


@login_required
def editar_movimentacao(request, pk):
    movimentacao = get_object_or_404(Movimentacao, pk=pk)
    form = MovimentacaoForm(request.POST or None, instance=movimentacao)
    if form.is_valid():
        form.save()
        return redirect('detalhe_processo', pk=movimentacao.processo.pk)
    return render(request, 'gestao/editar_movimentacao.html', {'form': form, 'movimentacao': movimentacao})


@login_required
def excluir_movimentacao(request, pk):
    movimentacao = get_object_or_404(Movimentacao, pk=pk)
    if request.method == 'POST':
        processo_pk = movimentacao.processo.pk
        movimentacao.delete()
        return redirect('detalhe_processo', pk=processo_pk)
    return render(request, 'gestao/excluir_movimentacao_confirm.html', {'movimentacao': movimentacao})


@login_required
def editar_movimentacao_servico(request, pk):
    movimentacao = get_object_or_404(MovimentacaoServico, pk=pk)
    form = MovimentacaoServicoForm(request.POST or None, instance=movimentacao)
    if form.is_valid():
        form.save()
        return redirect('detalhe_servico', pk=movimentacao.servico.pk)
    return render(request, 'gestao/editar_movimentacao_servico.html', {'form': form, 'movimentacao': movimentacao})


@require_POST
@login_required
def excluir_movimentacao_servico(request, pk):
    movimentacao = get_object_or_404(MovimentacaoServico, pk=pk)
    servico_pk = movimentacao.servico.pk
    movimentacao.delete()
    return redirect('detalhe_servico', pk=servico_pk)


@require_POST
@login_required
def concluir_servico(request, pk):
    servico = get_object_or_404(Servico, pk=pk)
    form = ServicoConcluirForm(request.POST, instance=servico)
    if form.is_valid():
        servico_concluido = form.save(commit=False)
        servico_concluido.concluido = True
        if not servico_concluido.data_encerramento:
            servico_concluido.data_encerramento = timezone.now().date()
        servico_concluido.save()
    return redirect('detalhe_servico', pk=pk)


@require_POST
@login_required
def concluir_movimentacao_servico(request, pk):
    movimentacao = get_object_or_404(MovimentacaoServico, pk=pk)
    movimentacao.status = 'CONCLUIDA'
    movimentacao.save()
    return redirect('detalhe_servico', pk=movimentacao.servico.pk)


@require_POST
@login_required
def concluir_movimentacao(request, pk):
    movimentacao = get_object_or_404(Movimentacao, pk=pk)
    movimentacao.status = 'CONCLUIDA'
    movimentacao.save()
    return redirect('detalhe_processo', pk=movimentacao.processo.pk)


@login_required
def adicionar_contrato(request, processo_pk=None, servico_pk=None):
    parent_object = None
    if processo_pk:
        parent_object = get_object_or_404(Processo, pk=processo_pk)
    elif servico_pk:
        parent_object = get_object_or_404(Servico, pk=servico_pk)

    if not parent_object:
        return redirect('dashboard')

    if request.method == 'POST':
        form = ContratoHonorariosForm(request.POST)
        if form.is_valid():
            contrato = form.save(commit=False)
            contrato.content_object = parent_object

            if isinstance(parent_object, Processo):
                autor_principal = parent_object.partes.filter(tipo_participacao='AUTOR').first()
                if not autor_principal:
                    form.add_error(None, "Um processo deve ter um cliente no Polo Ativo para criar um contrato.")
                    return render(request, 'gestao/adicionar_contrato.html',
                                  {'form': form, 'parent_object': parent_object})
                contrato.cliente = autor_principal.cliente
            elif isinstance(parent_object, Servico):
                contrato.cliente = parent_object.cliente

            contrato.save()
            return redirect(parent_object.get_absolute_url())
    else:
        form = ContratoHonorariosForm()

    return render(request, 'gestao/adicionar_contrato.html', {'form': form, 'parent_object': parent_object})


@require_POST
@login_required
def adicionar_pagamento(request, pk):
    lancamento = get_object_or_404(LancamentoFinanceiro, pk=pk)
    form = PagamentoForm(request.POST)
    if form.is_valid():
        pagamento = form.save(commit=False)
        pagamento.lancamento = lancamento
        pagamento.save()
    return redirect(
        lancamento.processo.get_absolute_url() if lancamento.processo else lancamento.servico.get_absolute_url())


@require_POST
@login_required
def editar_pagamento(request, pk):
    pagamento = get_object_or_404(Pagamento, pk=pk)
    form = PagamentoForm(request.POST, instance=pagamento)
    if form.is_valid():
        form.save()
    return redirect(
        pagamento.lancamento.processo.get_absolute_url() if pagamento.lancamento.processo else pagamento.lancamento.servico.get_absolute_url())


@require_POST
@login_required
def excluir_pagamento(request, pk):
    pagamento = get_object_or_404(Pagamento, pk=pk)
    redirect_url = pagamento.lancamento.processo.get_absolute_url() if pagamento.lancamento.processo else pagamento.lancamento.servico.get_absolute_url()
    pagamento.delete()
    return redirect(redirect_url)


@login_required
def gerenciar_partes(request, processo_pk):
    processo = get_object_or_404(Processo, pk=processo_pk)
    if request.method == 'POST':
        formset = ParteProcessoFormSet(request.POST, instance=processo, prefix='partes')
        if formset.is_valid():
            formset.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True})
            return redirect('detalhe_processo', pk=processo.pk)
        elif request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'errors': formset.errors}, status=400)

    formset = ParteProcessoFormSet(instance=processo, prefix='partes')
    context = {
        'processo': processo,
        'formset': formset,
        'is_modal': request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    }
    return render(request, 'gestao/gerenciar_partes.html', context)


@login_required
def detalhe_processo_partes_partial(request, processo_pk):
    processo = get_object_or_404(Processo, pk=processo_pk)
    return render(request, 'gestao/partials/_card_partes_envolvidas.html', {'processo': processo})


@login_required
def lista_clientes(request):
    """
    Exibe a lista de clientes, anotando a contagem de processos e serviços ATIVOS
    para determinar se a exclusão é permitida.
    """
    base_queryset = Cliente.objects.annotate(
        processos_ativos_count=Count('participacoes__processo',
                                     filter=Q(participacoes__processo__status_processo='ATIVO'), distinct=True),
        servicos_ativos_count=Count('servicos', filter=Q(servicos__concluido=False), distinct=True)
    ).order_by('nome_completo')

    cliente_filter = ClienteFilter(request.GET, queryset=base_queryset)

    # A lógica para requisições AJAX permanece a mesma
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'gestao/partials/_lista_clientes_partial.html', {'filter': cliente_filter})

    # A view principal também permanece a mesma
    context = {
        'filter': cliente_filter,
        'form': ClienteForm()
    }
    return render(request, 'gestao/lista_clientes.html', context)


@require_POST
@login_required
def salvar_cliente(request, pk=None):
    instance = get_object_or_404(Cliente, pk=pk) if pk else None
    form = ClienteForm(request.POST, instance=instance)
    if form.is_valid():
        form.save()
        return JsonResponse({'status': 'success', 'message': 'Cliente salvo com sucesso!'})
    return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)


@login_required
def get_cliente_json(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    data = {
        'nome_completo': cliente.nome_completo,
        'tipo_pessoa': cliente.tipo_pessoa,
        'cpf_cnpj': cliente.cpf_cnpj,
        'email': cliente.email,
        'telefone_principal': cliente.telefone_principal,
    }
    return JsonResponse(data)


@require_POST
@login_required
def excluir_cliente(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    try:
        cliente.delete()
        return JsonResponse({'status': 'success', 'message': 'Cliente excluído com sucesso!'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


login_required


# def pagina_de_calculos(request, processo_pk):
#     """
#     View principal que exibe a página de cálculos, listando
#     o histórico de cálculos já salvos e o formulário para um novo cálculo.
#     """
#     processo = get_object_or_404(Processo, pk=processo_pk)
#     calculos_salvos = processo.calculos.all().order_by('-data_calculo')
#
#     # --- ALTERAÇÃO AQUI ---
#     # Cria uma instância do formulário para permitir um novo cálculo imediatamente.
#     form = CalculoForm()
#
#     contexto = {
#         'processo': processo,
#         'calculos_salvos': calculos_salvos,
#         'form': form,  # Envia o formulário no contexto
#         'resultado': None,  # Garante que a seção de resultado não apareça inicialmente
#     }
#     return render(request, 'gestao/calculo_judicial.html', contexto)


@login_required
def realizar_calculo(request, processo_pk, calculo_pk=None):
    """
    Processa e exibe o formulário de cálculo. Agora com simulação automática ao carregar.
    """
    processo = get_object_or_404(Processo, pk=processo_pk)
    calculos_salvos = processo.calculos.all().order_by('-data_calculo')
    contexto = {
        'processo': processo,
        'calculos_salvos': calculos_salvos,
        'calculo_carregado': None,
        'resultado': None,
        'form_data': None,
        'erro': None,
    }

    if request.method == 'POST':
        form = CalculoForm(request.POST)
        if form.is_valid():
            dados = form.cleaned_data
            contexto['form_data'] = dados

            # Usa a função auxiliar para calcular
            resultado, erro = _perform_calculation(dados)
            contexto['resultado'] = resultado
            contexto['erro'] = erro

            # Salva no banco apenas se o cálculo foi bem-sucedido
            if resultado:
                memoria_calculo_json = []
                if resultado.get('memorial'):
                    memoria_calculo_json = [
                        {'termo_inicial': l['termo_inicial'].isoformat(), 'termo_final': l['termo_final'].isoformat(),
                         'variacao_periodo': str(l['variacao_periodo']),
                         'valor_atualizado_mes': str(l['valor_atualizado_mes'])} for l in resultado['memorial']]

                CalculoJudicial.objects.create(
                    processo=processo, responsavel=request.user, descricao=dados['descricao'],
                    valor_original=dados['valor_original'], data_inicio_correcao=dados['data_inicio'],
                    data_fim_correcao=dados['data_fim'], indice_correcao=dados['indice'],
                    correcao_pro_rata=dados.get('correcao_pro_rata', False),
                    juros_percentual=dados.get('juros_taxa'), juros_tipo=dados['juros_tipo'],
                    juros_periodo=dados['juros_periodo'], juros_data_inicio=dados.get('juros_data_inicio'),
                    juros_data_fim=dados.get('juros_data_fim'), multa_percentual=dados.get('multa_percentual'),
                    multa_sobre_juros=dados.get('multa_sobre_juros', False),
                    honorarios_percentual=dados.get('honorarios_percentual'),
                    valor_corrigido=resultado['resumo']['valor_corrigido_total'],
                    valor_final=resultado['resumo']['valor_final'], memoria_calculo=memoria_calculo_json
                )
                contexto['calculos_salvos'] = processo.calculos.all().order_by('-data_calculo')

        contexto['form'] = form

    else:  # GET
        initial_data = {}
        if 'form_initial_data' in request.session:
            initial_data = request.session.pop('form_initial_data')
        elif calculo_pk:
            calculo_carregado = get_object_or_404(CalculoJudicial, pk=calculo_pk, processo=processo)
            contexto['calculo_carregado'] = calculo_carregado
            initial_data = {
                'descricao': calculo_carregado.descricao,
                'valor_original': calculo_carregado.valor_original,
                'data_inicio': calculo_carregado.data_inicio_correcao,
                'data_fim': calculo_carregado.data_fim_correcao,  # <-- Carrega a data final ORIGINAL no formulário
                'indice': calculo_carregado.indice_correcao, 'correcao_pro_rata': calculo_carregado.correcao_pro_rata,
                'juros_taxa': calculo_carregado.juros_percentual, 'juros_tipo': calculo_carregado.juros_tipo,
                'juros_periodo': calculo_carregado.juros_periodo,
                'juros_data_inicio': calculo_carregado.juros_data_inicio,
                'juros_data_fim': calculo_carregado.juros_data_fim,
                'multa_percentual': calculo_carregado.multa_percentual,
                'multa_sobre_juros': calculo_carregado.multa_sobre_juros,
                'honorarios_percentual': calculo_carregado.honorarios_percentual, 'gerar_memorial': True,
            }

            # --- NOVA LÓGICA DE SIMULAÇÃO AUTOMÁTICA ---
            # Prepara os dados para o recálculo, mas atualiza a data final para hoje
            dados_para_recalculo = initial_data.copy()
            dados_para_recalculo['data_fim'] = date.today()

            # Roda o cálculo com a data de hoje (sem salvar)
            resultado, erro = _perform_calculation(dados_para_recalculo)
            contexto['resultado'] = resultado
            contexto['erro'] = erro
            # Usa os dados do recálculo para exibir o resumo correto
            contexto['form_data'] = dados_para_recalculo

        form = CalculoForm(initial=initial_data)
        contexto['form'] = form

    return render(request, 'gestao/calculo_judicial.html', contexto)


def _perform_calculation(dados):
    """
    Recebe um dicionário de dados limpos do formulário e retorna o resultado e um erro (se houver).
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
            juros_taxa=dados.get('juros_taxa') or 0, juros_tipo=dados['juros_tipo'],
            juros_periodo=dados['juros_periodo'], juros_data_inicio=dados.get('juros_data_inicio'),
            juros_data_fim=dados.get('juros_data_fim'), correcao_pro_rata=dados.get('correcao_pro_rata', False),
            multa_taxa=dados.get('multa_percentual') or 0, multa_sobre_juros=dados.get('multa_sobre_juros', False),
            honorarios_taxa=dados.get('honorarios_percentual') or 0
        )
        resultado['resumo']['indice_display_name'] = indice_selecionado_display

        if not dados.get('gerar_memorial'):
            resultado['memorial'] = None

        return resultado, None  # Retorna (resultado, None) em caso de sucesso
    except (ConnectionError, ValueError, KeyError) as e:
        return None, f"Ocorreu um erro durante o cálculo: {e}"  # Retorna (None, erro) em caso de falha


@login_required
@require_POST
def atualizar_calculo_hoje(request, calculo_pk):
    """
    Prepara os dados de um cálculo salvo para serem recalculados,
    atualizando a data final para hoje e colocando na sessão.
    """
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
        'multa_percentual': str(calculo.multa_percentual or ''),
        'multa_sobre_juros': calculo.multa_sobre_juros,
        'honorarios_percentual': str(calculo.honorarios_percentual or ''),
        'gerar_memorial': True,
    }
    request.session['form_initial_data'] = form_data

    return redirect('novo_calculo', processo_pk=calculo.processo.pk)


@require_POST
@login_required
def excluir_calculo(request, calculo_pk):
    """
    Exclui um único cálculo judicial do banco de dados.
    """
    # Usamos o select_related para pegar o processo_pk sem uma query extra
    calculo = get_object_or_404(CalculoJudicial.objects.select_related('processo'), pk=calculo_pk)
    processo_pk = calculo.processo.pk
    calculo.delete()
    # Redireciona de volta para a página principal de cálculos daquele processo
    return redirect('pagina_de_calculos', processo_pk=processo_pk)


@require_POST
@login_required
def excluir_todos_calculos(request, processo_pk):
    """
    Exclui TODOS os cálculos judiciais associados a um processo.
    """
    # Garante que o processo existe antes de tentar apagar os cálculos
    processo = get_object_or_404(Processo, pk=processo_pk)
    processo.calculos.all().delete()
    return redirect('pagina_de_calculos', processo_pk=processo.pk)


@login_required
def lista_modelos(request):
    modelos = ModeloDocumento.objects.all()
    return render(request, 'gestao/modelos/lista_modelos.html', {'modelos': modelos})


# Lista de placeholders que será usada nas views de criação/edição de modelos.
# Esta lista pode ser expandida no futuro.
VARIAVEIS_DOCUMENTO = {
    'Cliente': [
        {'label': 'Nome Completo', 'valor': '{{ cliente.nome_completo }}'},
        {'label': 'CPF/CNPJ', 'valor': '{{ cliente.cpf_cnpj }}'},
        {'label': 'E-mail', 'valor': '{{ cliente.email }}'},
        {'label': 'Telefone Principal', 'valor': '{{ cliente.telefone_principal }}'},
        # Adicionar mais campos do cliente conforme necessário (Nacionalidade, Estado Civil, etc.)
    ],
    'Processo': [
        {'label': 'Número do Processo', 'valor': '{{ processo.numero_processo }}'},
        {'label': 'Tipo da Ação', 'valor': '{{ processo.tipo_acao.nome }}'},
        {'label': 'Vara/Comarca', 'valor': '{{ processo.vara_comarca_orgao }}'},
        {'label': 'Valor da Causa (formatado)', 'valor': '{{ processo.valor_causa|floatformat:2|intcomma }}'},
        {'label': 'Polo Ativo (Nomes)', 'valor': '{{ processo.get_polo_ativo_display }}'},
        {'label': 'Polo Passivo (Nomes)', 'valor': '{{ processo.get_polo_passivo_display }}'},
    ],
    'Advogado': [
        {'label': 'Nome do Adv. Responsável', 'valor': '{{ processo.advogado_responsavel.get_full_name }}'},
        # Adicionar mais campos do perfil do advogado se existirem (OAB, etc.)
    ],
    'Geral': [
        {'label': 'Data Atual por Extenso', 'valor': '{{ data_extenso }}'},
        {'label': 'Cidade do Escritório', 'valor': '{{ cidade_escritorio }}'},
    ]
}


@login_required
def adicionar_modelo(request):
    if request.method == 'POST':
        form = ModeloDocumentoForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('lista_modelos')
    else:
        form = ModeloDocumentoForm()

    context = {
        'form': form,
        'titulo_pagina': 'Adicionar Novo Modelo',
        'variaveis': VARIAVEIS_DOCUMENTO  # Injetando as variáveis no contexto
    }
    return render(request, 'gestao/modelos/form_modelo.html', context)


@login_required
def editar_modelo(request, pk):
    modelo = get_object_or_404(ModeloDocumento, pk=pk)
    if request.method == 'POST':
        form = ModeloDocumentoForm(request.POST, instance=modelo)
        if form.is_valid():
            form.save()
            return redirect('lista_modelos')
    else:
        form = ModeloDocumentoForm(instance=modelo)

    context = {
        'form': form,
        'titulo_pagina': 'Editar Modelo',
        'variaveis': VARIAVEIS_DOCUMENTO  # Injetando as variáveis no contexto
    }
    return render(request, 'gestao/modelos/form_modelo.html', context)


@require_POST
@login_required
def excluir_modelo(request, pk):
    modelo = get_object_or_404(ModeloDocumento, pk=pk)
    modelo.delete()
    return redirect('lista_modelos')


@login_required
def gerar_documento(request, processo_pk, modelo_pk):
    """
    Gera o conteúdo de um documento a partir de um modelo e um processo,
    e exibe em um formulário para edição e salvamento.
    """
    processo = get_object_or_404(Processo, pk=processo_pk)
    modelo = get_object_or_404(ModeloDocumento, pk=modelo_pk)

    # Monta o contexto de variáveis para o template
    cliente_principal = processo.partes.filter(tipo_participacao='AUTOR').first().cliente if processo.partes.filter(
        tipo_participacao='AUTOR').exists() else None

    # Validação para garantir que o cliente principal existe
    if not cliente_principal:
        # messages.error(request, "Não é possível gerar documentos. O processo não possui um cliente no polo ativo.")
        return redirect('detalhe_processo', pk=processo.pk)


    contexto_variaveis = Context({
        'cliente': cliente_principal,
        'processo': processo,
        'data_extenso': data_por_extenso(date.today()),
        'cidade_escritorio': 'Sua Cidade, UF'  # Idealmente viria de um settings
    })

    # Renderiza o conteúdo do modelo com as variáveis
    conteudo_renderizado = Template(modelo.conteudo).render(contexto_variaveis)

    # Preenche o formulário com os dados gerados
    form = DocumentoForm(initial={
        'titulo': f"{modelo.titulo} - {cliente_principal.nome_completo}",
        'conteudo': conteudo_renderizado
    })

    if request.method == 'POST':
        form = DocumentoForm(request.POST)
        if form.is_valid():
            documento = form.save(commit=False)
            documento.processo = processo
            documento.modelo_origem = modelo
            documento.save()
            return redirect('detalhe_processo', pk=processo.pk)

    return render(request, 'gestao/documentos/form_documento.html', {
        'form': form,
        'processo': processo,
        'titulo_pagina': 'Gerar Documento'
    })


@login_required
def editar_documento(request, pk):
    """ Edita um documento já salvo. """
    documento = get_object_or_404(Documento, pk=pk)
    if request.method == 'POST':
        form = DocumentoForm(request.POST, instance=documento)
        if form.is_valid():
            form.save()
            return redirect('detalhe_processo', pk=documento.processo.pk)
    else:
        form = DocumentoForm(instance=documento)

    return render(request, 'gestao/documentos/form_documento.html', {
        'form': form,
        'processo': documento.processo,
        'titulo_pagina': 'Editar Documento'
    })
