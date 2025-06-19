# gestao/filters.py
import django_filters
from django.db import models  # <<< ADICIONE ESTA LINHA
from .models import Processo, TipoServico, Cliente, Servico
from django import forms # << ADICIONE forms


class ProcessoFilter(django_filters.FilterSet):
    # O campo do formulário não muda
    busca_geral = django_filters.CharFilter(method='filtro_geral', label="Buscar por Nº do Processo ou Parte")

    class Meta:
        model = Processo
        fields = ['status_processo', 'tipo_acao__area']

    def filtro_geral(self, queryset, name, value):
        """
        Método de busca corrigido.
        Agora, a busca pelo nome da parte é feita através do relacionamento
        Processo -> ParteProcesso -> Cliente.
        """
        # A correção principal está na linha abaixo:
        # Trocamos 'cliente__nome_completo' por 'partes__cliente__nome_completo'
        return queryset.filter(
            models.Q(numero_processo__icontains=value) |
            models.Q(partes__cliente__nome_completo__icontains=value)
        ).distinct() # Adicionamos .distinct() para evitar processos duplicados nos resultados


# ===================================================================
# === NOVO CÓDIGO PARA FILTRAR SERVIÇOS =============================
# ===================================================================
class ServicoFilter(django_filters.FilterSet):
    """Filtro para a lista de serviços."""
    busca_geral = django_filters.CharFilter(
        method='filtro_geral_servico',
        label="Buscar por Descrição ou Cliente",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Descrição ou nome do cliente'})
    )

    cliente = django_filters.ModelChoiceFilter(
        queryset=Cliente.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    tipo_servico = django_filters.ModelChoiceFilter(
        queryset=TipoServico.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    data_inicio_depois_de = django_filters.DateFilter(
        field_name='data_inicio',
        lookup_expr='gte',
        label='Iniciados Após',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )

    data_inicio_antes_de = django_filters.DateFilter(
        field_name='data_inicio',
        lookup_expr='lte',
        label='Iniciados Antes de',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )

    concluido = django_filters.ChoiceFilter(
        choices=[(True, 'Sim'), (False, 'Não')],
        label='Concluído?',
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label="Todos"  # Permite ver concluídos e não concluídos
    )

    class Meta:
        model = Servico
        fields = ['busca_geral', 'cliente', 'tipo_servico', 'concluido']

    def filtro_geral_servico(self, queryset, name, value):
        return queryset.filter(
            models.Q(descricao__icontains=value) | models.Q(cliente__nome_completo__icontains=value)
        )

class ClienteFilter(django_filters.FilterSet):
    busca_geral = django_filters.CharFilter(
        method='filtro_geral_cliente',
        label="Buscar por Nome ou CPF/CNPJ"
    )

    class Meta:
        model = Cliente
        fields = ['tipo_pessoa']

    def filtro_geral_cliente(self, queryset, name, value):
        return queryset.filter(
            models.Q(nome_completo__icontains=value) | models.Q(cpf_cnpj__icontains=value)
        )
