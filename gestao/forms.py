# gestao/forms.py
import json
from django import forms
from .models import (
    Movimentacao,
    Processo,
    Pagamento,
    Servico,
    Cliente,
    TipoServico,
    MovimentacaoServico,
    TipoMovimentacao,
    ContratoHonorarios
)
from datetime import date

from django.forms import inlineformset_factory # <<< ADICIONE ESTE IMPORT
from .models import Processo, ParteProcesso # <<< ADICIONE ParteProcesso



class MovimentacaoForm(forms.ModelForm):
    """Formulário para movimentações em Processos."""
    class Meta:
        model = Movimentacao
        fields = [
            'tipo_movimentacao', 'titulo', 'detalhes',
            'data_publicacao', 'dias_prazo', 'data_prazo_final',
            'responsavel', 'status'
        ]
        widgets = {
            'data_publicacao': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'data_prazo_final': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'titulo': forms.TextInput(attrs={'class': 'form-control'}),
            'detalhes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'dias_prazo': forms.NumberInput(attrs={'class': 'form-control'}),
            'tipo_movimentacao': forms.Select(attrs={'class': 'form-select'}),
            'responsavel': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        dias_sugeridos_data = {
            tipo.pk: tipo.sugestao_dias_prazo
            for tipo in self.fields['tipo_movimentacao'].queryset if tipo.sugestao_dias_prazo
        }
        self.fields['tipo_movimentacao'].widget.attrs['data-dias-sugeridos'] = json.dumps(dias_sugeridos_data)


class ProcessoForm(forms.ModelForm):
    """Formulário para editar detalhes de um Processo."""
    class Meta:
        model = Processo
        fields = [
            'status_processo', 'valor_causa', 'advogado_responsavel',
            'vara_comarca_orgao', 'descricao_caso', 'observacoes_internas'
        ]
        widgets = {
            'status_processo': forms.Select(attrs={'class': 'form-select'}),
            'valor_causa': forms.NumberInput(attrs={'class': 'form-control'}),
            'advogado_responsavel': forms.Select(attrs={'class': 'form-select'}),
            'vara_comarca_orgao': forms.TextInput(attrs={'class': 'form-control'}),
            'descricao_caso': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'observacoes_internas': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }


class PagamentoForm(forms.ModelForm):
    """Formulário para registrar pagamentos."""
    class Meta:
        model = Pagamento
        fields = ['data_pagamento', 'valor_pago', 'forma_pagamento', 'observacoes']
        widgets = {
            'data_pagamento': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'valor_pago': forms.NumberInput(attrs={'class': 'form-control'}),
            'forma_pagamento': forms.TextInput(attrs={'class': 'form-control'}),
            'observacoes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class ClienteForm(forms.ModelForm):
    """Formulário para adicionar Cliente via modal."""
    class Meta:
        model = Cliente
        fields = ['nome_completo', 'tipo_pessoa', 'cpf_cnpj', 'email', 'telefone_principal']
        widgets = {
            'nome_completo': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo_pessoa': forms.Select(attrs={'class': 'form-select'}),
            'cpf_cnpj': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'telefone_principal': forms.TextInput(attrs={'class': 'form-control'}),
        }


class TipoServicoForm(forms.ModelForm):
    """Formulário para adicionar Tipo de Serviço via modal."""
    class Meta:
        model = TipoServico
        fields = ['nome']
        widgets = {'nome': forms.TextInput(attrs={'class': 'form-control'})}


class ServicoForm(forms.ModelForm):
    """Formulário para os dados básicos de um NOVO Serviço."""
    class Meta:
        model = Servico
        fields = ['cliente', 'tipo_servico', 'responsavel', 'descricao', 'recorrente', 'prazo']
        widgets = {
            'cliente': forms.Select(attrs={'class': 'form-select'}),
            'tipo_servico': forms.Select(attrs={'class': 'form-select'}),
            'responsavel': forms.Select(attrs={'class': 'form-select'}),
            'descricao': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Elaboração de Contrato Social'}),
            'recorrente': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'prazo': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
        }


class ContratoHonorariosForm(forms.ModelForm):
    """Formulário para os detalhes financeiros de um Serviço ou Processo."""
    class Meta:
        model = ContratoHonorarios
        fields = [
            'descricao', 'valor_pagamento_fixo', 'qtde_pagamentos_fixos',
            'data_primeiro_vencimento', 'percentual_exito'
        ]
        widgets = {
            'descricao': forms.TextInput(attrs={'class': 'form-control'}),
            'valor_pagamento_fixo': forms.NumberInput(attrs={'class': 'form-control'}),
            'qtde_pagamentos_fixos': forms.NumberInput(attrs={'class': 'form-control', 'value': 1}),
            'data_primeiro_vencimento': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'percentual_exito': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class ServicoEditForm(forms.ModelForm):
    """Formulário para EDITAR os detalhes de um Serviço existente."""
    class Meta:
        model = Servico
        fields = [
            'responsavel', 'descricao', 'data_inicio', 'recorrente', 'prazo',
            'data_encerramento', 'concluido', 'ativo'
        ]
        widgets = {
            'responsavel': forms.Select(attrs={'class': 'form-select'}),
            'descricao': forms.TextInput(attrs={'class': 'form-control'}),
            'data_inicio': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'recorrente': forms.CheckboxInput(attrs={'class': 'form-check-input form-switch'}),
            'prazo': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'data_encerramento': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control'}),
            'concluido': forms.CheckboxInput(attrs={'class': 'form-check-input form-switch'}),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input form-switch'}),
        }


class MovimentacaoServicoForm(forms.ModelForm):
    """Formulário para movimentações em Serviços."""
    class Meta:
        model = MovimentacaoServico
        fields = ['titulo', 'detalhes', 'data_atividade', 'responsavel', 'status', 'prazo_final']
        widgets = {
            'titulo': forms.TextInput(attrs={'class': 'form-control'}),
            'detalhes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'data_atividade': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'responsavel': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'prazo_final': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
        }


class ServicoConcluirForm(forms.ModelForm):
    """Formulário específico para concluir um serviço (usado no modal)."""
    class Meta:
        model = Servico
        fields = ['data_encerramento']
        widgets = {
            'data_encerramento': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['data_encerramento'].label = "Data de Conclusão"

# ===================================================================
# === NOVO FORMULÁRIO PARA CRIAR UM PROCESSO ========================
# ===================================================================
class ProcessoCreateForm(forms.ModelForm):
    """Formulário para a criação de um novo Processo."""
    class Meta:
        model = Processo
        # ATENÇÃO: O campo 'cliente' será adicionado aqui futuramente, após a refatoração.
        # Por enquanto, vamos assumir que o cliente será selecionado na tela.
        # Mas como o campo foi removido na proposta anterior, e não implementado,
        # vou me basear na sua ÚLTIMA estrutura de código enviada, onde o campo ainda existe.
        fields = [
            'tipo_acao', 'numero_processo',
            'advogado_responsavel', 'vara_comarca_orgao', 'valor_causa',
            'descricao_caso', 'observacoes_internas'
        ]
        widgets = {
            #'cliente': forms.Select(attrs={'class': 'form-select'}),
            'tipo_acao': forms.Select(attrs={'class': 'form-select'}),
            'numero_processo': forms.TextInput(attrs={'class': 'form-control'}),
            'advogado_responsavel': forms.Select(attrs={'class': 'form-select'}),
            'vara_comarca_orgao': forms.TextInput(attrs={'class': 'form-control'}),
            'valor_causa': forms.NumberInput(attrs={'class': 'form-control'}),
            'descricao_caso': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'observacoes_internas': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['numero_processo'].required = False
        self.fields['valor_causa'].required = False
        self.fields['observacoes_internas'].label = "Observações Internas (visível apenas para a equipe)"


# ==========================================================
# === FORMSET PARA ADICIONAR PARTES NO PROCESSO ==========
# ==========================================================
ParteProcessoFormSet = inlineformset_factory(
    Processo,
    ParteProcesso,
    fields=('cliente', 'tipo_participacao', 'representado_por'),
    extra=1,  # <<< ALTERE DE 2 PARA 1
    can_delete=True,
    widgets={
        'cliente': forms.Select(attrs={'class': 'form-select'}),
        'tipo_participacao': forms.Select(attrs={'class': 'form-select'}),
        'representado_por': forms.Select(attrs={'class': 'form-select'}),
    }
)


class CalculoForm(forms.Form):
    """
    Formulário completo e aprimorado para a interface de cálculo monetário,
    com a correção definitiva para o formato de data.
    """
    INDICE_CHOICES = [
        ('IPCA', 'IPCA (IBGE)'),
        ('INPC', 'INPC (IBGE)'),
        ('IGP-M', 'IGP-M (FGV/BCB)'),
        ('IGP-DI', 'IGP-DI (FGV/BCB)'),
        ('SELIC', 'Taxa Selic (BCB)'),
        ('TR', 'Taxa Referencial (BCB)'),
    ]
    JUROS_TIPO_CHOICES = [('SIMPLES', 'Simples'), ('COMPOSTO', 'Compostos')]
    JUROS_PERIODO_CHOICES = [('MENSAL', 'Mensal'), ('ANUAL', 'Anual')]

    # --- Seção 1: Valor e Período ---
    valor_original = forms.DecimalField(
        label="Valor a ser atualizado (R$)",
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '1000,00'})
    )
    # CORREÇÃO: Adicionado o parâmetro 'format' ao widget de data
    data_inicio = forms.DateField(
        label="Data inicial (termo inicial)",
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'})
    )
    # CORREÇÃO: Adicionado o parâmetro 'format' ao widget de data
    data_fim = forms.DateField(
        label="Data final (termo final)",
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
        initial=date.today
    )
    correcao_pro_rata = forms.BooleanField(
        label="Correção Pro-Rata",
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    descricao = forms.CharField(
        label="Descrição do Cálculo",
        max_length=255,
        initial="Cálculo Padrão",
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text="Ex: Cálculo para proposta de acordo, Atualização para petição, etc."
    )

    # --- Seção 2: Correção Monetária ---
    indice = forms.ChoiceField(
        label="Índice de atualização",
        choices=INDICE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    # --- Seção 3: Juros ---
    juros_taxa = forms.DecimalField(
        label="Taxa de juros (%)",
        required=False,
        decimal_places=4,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 1.0 para 1%'})
    )
    juros_periodo = forms.ChoiceField(
        label="Período da taxa",
        choices=JUROS_PERIODO_CHOICES,
        initial='MENSAL',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    juros_tipo = forms.ChoiceField(
        label="Tipo de juros",
        choices=JUROS_TIPO_CHOICES,
        initial='SIMPLES',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    # CORREÇÃO: Adicionado o parâmetro 'format' ao widget de data
    juros_data_inicio = forms.DateField(
        label="Data inicial dos juros",
        required=False,
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
        help_text="Opcional. Se em branco, usa a data inicial da correção."
    )
    # CORREÇÃO: Adicionado o parâmetro 'format' ao widget de data
    juros_data_fim = forms.DateField(
        label="Data final dos juros",
        required=False,
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
        help_text="Opcional. Se em branco, usa a data final da correção."
    )

    # --- Seção 4: Multa e Honorários ---
    multa_percentual = forms.DecimalField(
        label="Percentual da multa (%)",
        required=False,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 10.00'})
    )
    multa_sobre_juros = forms.BooleanField(
        label="Calcular a multa também sobre os juros",
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    honorarios_percentual = forms.DecimalField(
        label="Percentual dos honorários (%)",
        required=False,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 12.00'})
    )

    # --- Seção 5: Opções de Exibição ---
    gerar_memorial = forms.BooleanField(
        label="Gerar Memorial de Cálculo Detalhado",
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

