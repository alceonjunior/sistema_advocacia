import django_filters
from django.db import models
from django.db.models import Q
from django import forms
from django.contrib.auth import get_user_model

from .models import Processo, TipoServico, Cliente, Servico, AreaProcesso

User = get_user_model()


class ProcessoFilter(django_filters.FilterSet):
    # Campo para busca em vários campos do modelo
    busca_geral = django_filters.CharFilter(
        method='filtro_busca_geral',
        label='Buscar por Nº, Assunto ou Parte'
    )

    # ==========================================================
    # ↓↓↓ O FILTRO DE ORDENAÇÃO É DEFINIDO AQUI... ↓↓↓
    # ==========================================================
    ordering = django_filters.OrderingFilter(
        # Tupla de campos pelos quais se pode ordenar
        fields=(
            ('data_distribuicao', 'data_distribuicao'),  # Adiciona opção para ordenar por data
            ('valor_causa', 'valor_causa'),  # Adiciona opção para ordenar por valor
        ),
        # Labels amigáveis para as opções no formulário
        field_labels={
            'data_distribuicao': 'Data (Mais Antiga)',
            '-data_distribuicao': 'Data (Mais Recente)',  # O '-' indica ordem decrescente
            'valor_causa': 'Valor da Causa (Menor)',
            '-valor_causa': 'Valor da Causa (Maior)',
        },
        label='Ordenar por'
    )

    class Meta:
        model = Processo
        # ==========================================================
        # ↓↓↓ ...MAS O CAMPO 'ordering' NÃO DEVE SER LISTADO AQUI. ↓↓↓
        # ==========================================================
        # A lista 'fields' é apenas para filtros que correspondem diretamente
        # a campos no modelo 'Processo'.
        fields = ['status_processo', 'tipo_acao__area', 'advogado_responsavel']

    # O método __init__ para o filtro padrão continua o mesmo
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'status_processo' not in self.data:
            self.form.initial['status_processo'] = 'ATIVO'
            self.queryset = self.queryset.filter(status_processo='ATIVO')

    # A função de busca geral também continua a mesma
    def filtro_busca_geral(self, queryset, name, value):
        return queryset.filter(
            Q(numero_processo__icontains=value) |
            Q(descricao_caso__icontains=value) |
            Q(partes__cliente__nome_completo__icontains=value)
        ).distinct()


class ServicoFilter(django_filters.FilterSet):
    """Filtro para a lista de serviços."""
    busca_geral = django_filters.CharFilter(
        method='filtro_geral_servico',
        label="Buscar por Descrição ou Cliente",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Descrição ou nome do cliente'})
    )
    tipo_servico = django_filters.ModelChoiceFilter(
        queryset=TipoServico.objects.all(),
        label="Tipo de Serviço",
        empty_label="Qualquer Tipo",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    concluido = django_filters.ChoiceFilter(
        choices=[(True, 'Sim'), (False, 'Não')],
        label='Concluído?',
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label="Todos"
    )

    class Meta:
        model = Servico
        fields = ['busca_geral', 'tipo_servico', 'concluido']

    def filtro_geral_servico(self, queryset, name, value):
        return queryset.filter(
            Q(descricao__icontains=value) | Q(cliente__nome_completo__icontains=value)
        )


class ClienteFilter(django_filters.FilterSet):
    """
    Filtro avançado para a listagem de clientes, com busca, filtros
    de status e tipo, e ordenação dinâmica.
    """
    busca_geral = django_filters.CharFilter(
        method='filter_busca_geral',
        label='Buscar por Nome ou CPF/CNPJ',
        widget=forms.TextInput(
            attrs={'class': 'form-control', 'placeholder': 'Digite para buscar...'})
    )
    tipo_pessoa = django_filters.ChoiceFilter(
        choices=Cliente.TIPO_PESSOA_CHOICES,
        label='Tipo de Pessoa',
        empty_label='Qualquer Tipo',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    STATUS_CHOICES = [
        ('ativos', 'Com Casos Ativos (Processo ou Serviço)'),
        ('processos_ativos', 'Com Processos Ativos'),
        ('servicos_ativos', 'Com Serviços Ativos'),
        ('inativos', 'Sem Casos Ativos'),
    ]
    status_casos = django_filters.ChoiceFilter(
        choices=STATUS_CHOICES,
        method='filter_by_status',
        label='Status do Cliente',
        empty_label='Qualquer Status',
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
        label='Ordenar por',
        choices=ORDERING_CHOICES,
        method='filter_ordering',
        empty_label='Padrão',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = Cliente
        fields = ['busca_geral', 'tipo_pessoa', 'status_casos', 'ordering']

    def filter_busca_geral(self, queryset, name, value):
        if value:
            return queryset.filter(
                Q(nome_completo__icontains=value) | Q(cpf_cnpj__icontains=value)
            )
        return queryset

    def filter_by_status(self, queryset, name, value):
        if value == 'ativos':
            return queryset.filter(Q(processos_ativos_count__gt=0) | Q(servicos_ativos_count__gt=0))
        if value == 'processos_ativos':
            return queryset.filter(processos_ativos_count__gt=0)
        if value == 'servicos_ativos':
            return queryset.filter(servicos_ativos_count__gt=0)
        if value == 'inativos':
            return queryset.filter(processos_ativos_count=0, servicos_ativos_count=0)
        return queryset

    def filter_ordering(self, queryset, name, value):
        return queryset.order_by(value)