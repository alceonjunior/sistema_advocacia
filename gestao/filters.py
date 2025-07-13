# gestao/filters.py

import django_filters
from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q, F, Func

# Importa a função unidecode para tratar o valor digitado pelo usuário
from unidecode import unidecode

from .models import Processo, Servico, Cliente, AreaProcesso

User = get_user_model()


# ==============================================================================
# FILTRO PARA PROCESSOS
# ==============================================================================
class ProcessoFilter(django_filters.FilterSet):
    """Filtro para a tela de listagem de processos."""

    # Busca geral que agora também ignora acentos no nome das partes.
    busca_geral = django_filters.CharFilter(
        method='filtro_busca_geral_unaccent',
        label='Buscar por Nº, Assunto ou Parte'
    )

    # Filtro por área do direito, que cascateia para o tipo de ação.
    tipo_acao__area = django_filters.ModelChoiceFilter(
        queryset=AreaProcesso.objects.all(),
        label="Área do Direito"
    )

    ordering = django_filters.OrderingFilter(
        fields=(
            ('data_distribuicao', 'data_distribuicao'),
            ('valor_causa', 'valor_causa'),
        ),
        field_labels={
            'data_distribuicao': 'Data (Mais Antiga)',
            '-data_distribuicao': 'Data (Mais Recente)',
            'valor_causa': 'Valor da Causa (Menor)',
            '-valor_causa': 'Valor da Causa (Maior)',
        },
        label='Ordenar por'
    )

    class Meta:
        model = Processo
        # Campos que o django-filter pode mapear diretamente, sem lógica customizada.
        fields = ['status_processo', 'tipo_acao__area', 'advogado_responsavel']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Define 'ATIVO' como o status padrão ao carregar a página pela primeira vez.
        if 'status_processo' not in self.data:
            self.form.initial['status_processo'] = 'ATIVO'
            self.queryset = self.queryset.filter(status_processo='ATIVO')

    def filtro_busca_geral_unaccent(self, queryset, name, value):
        """
        Método de busca que ignora acentos no nome da parte.
        """
        if not value:
            return queryset

        unaccented_value = unidecode(value)

        # Anota o queryset para criar uma coluna virtual com o nome da parte sem acento.
        queryset_anotado = queryset.annotate(
            nome_parte_unaccent=Func(F('partes__cliente__nome_completo'), function='unaccent')
        )

        return queryset_anotado.filter(
            Q(numero_processo__icontains=value) |
            Q(descricao_caso__icontains=value) |
            Q(nome_parte_unaccent__icontains=unaccented_value)
        ).distinct()


# ==============================================================================
# FILTRO PARA SERVIÇOS
# ==============================================================================
class ServicoFilter(django_filters.FilterSet):
    """Filtro aprimorado para a lista de serviços."""

    busca_geral = django_filters.CharFilter(
        method='filtro_busca_geral_unaccent',
        label='Buscar por Descrição, Cliente ou Tipo',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Digite aqui...'})
    )

    data_inicio_depois_de = django_filters.DateFilter(
        field_name='data_inicio', lookup_expr='gte', label='Iniciado Após',
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )

    data_inicio_antes_de = django_filters.DateFilter(
        field_name='data_inicio', lookup_expr='lte', label='Iniciado Antes de',
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )

    status = django_filters.ChoiceFilter(
        label='Status', choices=(('em_andamento', 'Em Andamento'), ('concluido', 'Concluído')),
        method='filter_status', widget=forms.Select(attrs={'class': 'form-select'}), empty_label="Todos"
    )

    class Meta:
        model = Servico
        fields = ['busca_geral', 'cliente', 'responsavel', 'tipo_servico', 'status']

    def filtro_busca_geral_unaccent(self, queryset, name, value):
        if not value:
            return queryset

        unaccented_value = unidecode(value)
        queryset_anotado = queryset.annotate(
            nome_cliente_unaccent=Func(F('cliente__nome_completo'), function='unaccent')
        )
        return queryset_anotado.filter(
            Q(descricao__icontains=value) |
            Q(nome_cliente_unaccent__icontains=unaccented_value) |
            Q(tipo_servico__nome__icontains=value)
        )

    def filter_status(self, queryset, name, value):
        if value == 'em_andamento':
            return queryset.filter(concluido=False)
        if value == 'concluido':
            return queryset.filter(concluido=True)
        return queryset


# ==============================================================================
# FILTRO PARA CLIENTES E PESSOAS (CORRIGIDO E APERFEIÇOADO)
# ==============================================================================
class ClienteFilter(django_filters.FilterSet):
    """
    Filtro avançado e reutilizável para as listagens de Clientes e Pessoas.
    """
    busca_geral = django_filters.CharFilter(
        method='filtro_geral_unaccent',
        label="Buscar (Nome, CPF/CNPJ, E-mail)",
        widget=forms.TextInput(
            attrs={'class': 'form-control', 'placeholder': 'Digite para buscar...'})
    )

    tipo_pessoa = django_filters.ChoiceFilter(
        choices=Cliente.TIPO_PESSOA_CHOICES,
        label='Tipo de Pessoa', empty_label='Qualquer Tipo',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    estado = django_filters.ChoiceFilter(
        choices=Cliente.ESTADOS_BRASILEIROS_CHOICES,
        field_name='estado', label='Estado (UF)', empty_label='Todos os Estados',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    STATUS_CHOICES = [
        ('ativos', 'Com Casos Ativos (Processo ou Serviço)'),
        ('processos_ativos', 'Com Processos Ativos'),
        ('servicos_ativos', 'Com Serviços Ativos'),
        ('inativos', 'Sem Casos Ativos'),
    ]
    status_casos = django_filters.ChoiceFilter(
        choices=STATUS_CHOICES, method='filter_by_status',
        label='Status dos Casos', empty_label='Qualquer Status',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    ORDERING_CHOICES = [
        ('nome_completo', 'Nome (A-Z)'),
        ('-nome_completo', 'Nome (Z-A)'),
        ('-data_cadastro', 'Mais Recentes'),
        ('data_cadastro', 'Mais Antigos'),
        ('-processos_ativos_count', 'Mais Processos'),
        ('-servicos_ativos_count', 'Mais Serviços'),
    ]
    ordering = django_filters.ChoiceFilter(
        label='Ordenar por', choices=ORDERING_CHOICES,
        method='filter_ordering', empty_label='Padrão',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = Cliente
        fields = ['busca_geral', 'tipo_pessoa', 'estado', 'status_casos', 'ordering']

    def filtro_geral_unaccent(self, queryset, name, value):
        if not value:
            return queryset

        unaccented_value = unidecode(value)
        queryset_anotado = queryset.annotate(
            nome_completo_unaccent=Func(F('nome_completo'), function='unaccent')
        )
        return queryset_anotado.filter(
            Q(nome_completo_unaccent__icontains=unaccented_value) |
            Q(cpf_cnpj__icontains=value) |
            Q(email__icontains=value)
        ).distinct()

    def filter_by_status(self, queryset, name, value):
        if value == 'ativos':
            return queryset.filter(Q(processos_ativos_count__gt=0) | Q(servicos_ativos_count__gt=0)).distinct()
        if value == 'processos_ativos':
            return queryset.filter(processos_ativos_count__gt=0)
        if value == 'servicos_ativos':
            return queryset.filter(servicos_ativos_count__gt=0)
        if value == 'inativos':
            return queryset.filter(processos_ativos_count=0, servicos_ativos_count=0)
        return queryset

    def filter_ordering(self, queryset, name, value):
        expression = value[0] if isinstance(value, list) else value
        return queryset.order_by(expression)