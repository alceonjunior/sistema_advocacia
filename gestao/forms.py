# gestao/forms.py

# -----------------------------------------------------------------------------
# IMPORTS NECESSÁRIOS
# -----------------------------------------------------------------------------
# Módulos padrão do Django e Python
from django import forms
from datetime import date
from django.contrib.auth.models import Group

# Modelos de dados do aplicativo 'gestao'
# A importação explícita de cada modelo torna o código mais legível e previne
# potenciais conflitos de nomes ou importações circulares.
from .models import (
    Processo, Cliente, TipoAcao, Movimentacao, TipoMovimentacao,
    Pagamento, Servico, TipoServico, MovimentacaoServico, ContratoHonorarios,
    ModeloDocumento, Documento, ParteProcesso, Recurso, Incidente, EscritorioConfiguracao, AreaProcesso, UsuarioPerfil,
    LancamentoFinanceiro
)
from .models import CalculoJudicial, FaseCalculo

# Ferramenta do Django para criar conjuntos de formulários (formsets) a partir de
# um modelo, essencial para editar múltiplos objetos relacionados em uma única tela.
from django.forms import inlineformset_factory
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth.models import User

# -----------------------------------------------------------------------------
# FORMULÁRIOS DE PROCESSO
# -----------------------------------------------------------------------------

class ProcessoForm(forms.ModelForm):
    """
    Formulário principal e abrangente para a CRIAÇÃO e EDIÇÃO de um Processo.
    Este formulário utiliza ModelForm para se conectar diretamente ao modelo 'Processo',
    reduzindo a duplicação de código. Os widgets são definidos explicitamente para
    garantir uma renderização consistente e estilizada com Bootstrap.
    """

    class Meta:
        """
        Configurações do ModelForm, ligando-o ao modelo 'Processo' e especificando
        os campos e widgets a serem utilizados.
        """
        # Modelo base para o formulário
        model = Processo
        # Inclui todos os campos do modelo 'Processo' no formulário
        fields = '__all__'

        # Dicionário de widgets para customizar a aparência e o comportamento
        # dos campos no HTML. As classes CSS ('form-control', 'form-select', etc.)
        # são padrão do Bootstrap 5 para estilização.
        widgets = {
            # Campos de Texto e URL
            'numero_processo': forms.TextInput(attrs={'class': 'form-control'}),
            'vara_comarca_orgao': forms.TextInput(attrs={'class': 'form-control'}),
            'juiz_responsavel': forms.TextInput(attrs={'class': 'form-control'}),
            'numero_sei': forms.TextInput(attrs={'class': 'form-control'}),
            'numero_outro_sistema': forms.TextInput(attrs={'class': 'form-control'}),
            'link_acesso': forms.URLInput(attrs={'class': 'form-control'}),

            # Campos de Seleção (Dropdown)
            'tipo_acao': forms.Select(attrs={'class': 'form-select'}),
            'fase': forms.Select(attrs={'class': 'form-select'}),
            'status_processo': forms.Select(attrs={'class': 'form-select'}),
            'tribunal': forms.Select(attrs={'class': 'form-select'}),
            'grau_jurisdicao': forms.Select(attrs={'class': 'form-select'}),
            'advogado_responsavel': forms.Select(attrs={'class': 'form-select'}),
            'resultado': forms.Select(attrs={'class': 'form-select'}),

            # Campos de Data
            'data_distribuicao': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'data_transito_em_julgado': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),

            # Campos Numéricos
            'valor_causa': forms.NumberInput(attrs={'class': 'form-control'}),
            'valor_executado': forms.NumberInput(attrs={'class': 'form-control'}),

            # Campos de Texto Longo (Textarea)
            'descricao_caso': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'observacoes_internas': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'bloqueios_penhoras': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Formato JSON: [{"sistema": "SISBAJUD", "valor": 1500.00}]'}),

            # Campos Booleanos (Checkbox)
            'segredo_justica': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'justica_gratuita': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'prioridade_tramitacao': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'execucao_iniciada': forms.CheckboxInput(attrs={'class': 'form-check-input'}),

            # Campos de Múltipla Escolha
            'advogados_envolvidos': forms.SelectMultiple(attrs={'class': 'd-none'}),
            'nivel_permissao': forms.RadioSelect(), # RadioSelect é ideal para poucas opções
        }

# Por simplicidade e consistência, o formulário de criação pode ser o mesmo da edição.
ProcessoCreateForm = ProcessoForm

# -----------------------------------------------------------------------------
# FORMSETS (Conjuntos de Formulários)
# -----------------------------------------------------------------------------

class ParteProcessoForm(forms.ModelForm):
    """
    Formulário customizado para uma única Parte do Processo.
    A customização no __init__ é crucial para filtrar dinamicamente
    o campo 'representado_por'.
    """

    class Meta:
        model = ParteProcesso
        fields = ['cliente', 'tipo_participacao', 'is_cliente_do_processo', 'representado_por']
        widgets = {
            'cliente': forms.Select(attrs={'class': 'form-select'}),
            'tipo_participacao': forms.Select(attrs={'class': 'form-select'}),
            'representado_por': forms.Select(attrs={'class': 'form-select'}),
            'is_cliente_do_processo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Esta parte do código filtra o campo 'representado_por' e está correta.
        if self.instance and self.instance.pk and self.instance.processo:
            processo_atual = self.instance.processo
            # Exclui a própria parte da lista de possíveis representantes
            partes_elegiveis = ParteProcesso.objects.filter(processo=processo_atual).exclude(pk=self.instance.pk)
            self.fields['representado_por'].queryset = partes_elegiveis
        else:
            # Se for um formulário novo (sem instância), não há ninguém para representar ainda.
            self.fields['representado_por'].queryset = ParteProcesso.objects.none()


ParteProcessoFormSet = inlineformset_factory(
    Processo,
    ParteProcesso,
    form=ParteProcessoForm,
    fk_name='processo',
    extra=1,
    can_delete=True
)


# -----------------------------------------------------------------------------
# FORMULÁRIOS DE ENTIDADES RELACIONADAS
# -----------------------------------------------------------------------------

class ClienteForm(forms.ModelForm):
    """Formulário para criar e editar um Cliente, com todos os novos campos."""

    class Meta:
        model = Cliente
        # Lista explícita de todos os campos para garantir a ordem
        fields = [
            'nome_completo', 'tipo_pessoa', 'cpf_cnpj', 'email', 'telefone_principal',
            'data_nascimento', 'nacionalidade', 'estado_civil', 'profissao',
            'cep', 'logradouro', 'numero', 'complemento', 'bairro', 'cidade', 'estado',
            'representante_legal', 'cpf_representante_legal', 'is_cliente'
        ]

        # Widgets para estilização com Bootstrap
        widgets = {
            # Bloco 1
            'nome_completo': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo_pessoa': forms.Select(attrs={'class': 'form-select'}),
            'cpf_cnpj': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'telefone_principal': forms.TextInput(attrs={'class': 'form-control'}),
            # Bloco 2
            'data_nascimento': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'nacionalidade': forms.TextInput(attrs={'class': 'form-control'}),
            'estado_civil': forms.Select(attrs={'class': 'form-select'}),
            'profissao': forms.TextInput(attrs={'class': 'form-control'}),
            # Bloco 3
            'cep': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Apenas números'}),
            'logradouro': forms.TextInput(attrs={'class': 'form-control'}),
            'numero': forms.TextInput(attrs={'class': 'form-control'}),
            'complemento': forms.TextInput(attrs={'class': 'form-control'}),
            'bairro': forms.TextInput(attrs={'class': 'form-control'}),
            'cidade': forms.TextInput(attrs={'class': 'form-control'}),
            'estado': forms.Select(attrs={'class': 'form-select'}),
            # Bloco 4
            'representante_legal': forms.TextInput(attrs={'class': 'form-control'}),
            'cpf_representante_legal': forms.TextInput(attrs={'class': 'form-control'}),
            'is_cliente': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class DocumentoForm(forms.ModelForm):
    """Formulário para gerar ou editar documentos vinculados a um processo."""
    class Meta:
        model = Documento
        fields = ['titulo', 'tipo_documento', 'data_protocolo', 'arquivo_upload', 'conteudo']
        widgets = {
            'titulo': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo_documento': forms.Select(attrs={'class': 'form-select'}),
            'data_protocolo': forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'arquivo_upload': forms.FileInput(attrs={'class': 'form-control'}),
        }

# ===== INÍCIO DA CORREÇÃO =====
# Adicione este novo formulário, mais simples e específico para a geração
class GerarDocumentoForm(forms.ModelForm):
    """Formulário simplificado, usado apenas para a criação inicial do documento a partir de um modelo."""
    class Meta:
        model = Documento
        # Incluímos apenas os campos que o usuário edita nesta tela específica
        fields = ['titulo', 'conteudo']
        widgets = {
            'titulo': forms.TextInput(attrs={'class': 'form-control'}),
            # O widget do 'conteudo' (CKEditor) já é definido automaticamente pelo RichTextUploadingField
        }

class RecursoForm(forms.ModelForm):
    """Formulário para registrar recursos interpostos em um processo."""
    class Meta:
        model = Recurso
        fields = ['tipo', 'data_interposicao', 'resultado', 'detalhes']
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'data_interposicao': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'resultado': forms.TextInput(attrs={'class': 'form-control'}),
            'detalhes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class IncidenteForm(forms.ModelForm):
    """Formulário para registrar incidentes processuais."""
    class Meta:
        model = Incidente
        fields = ['tipo', 'descricao', 'status', 'data_ocorrido']
        widgets = {
            'tipo': forms.TextInput(attrs={'class': 'form-control'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'data_ocorrido': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
        }

# -----------------------------------------------------------------------------
# FORMULÁRIOS DE SERVIÇOS EXTRAJUDICIAIS
# -----------------------------------------------------------------------------

class AreaProcessoForm(forms.ModelForm):
    class Meta:
        model = AreaProcesso
        fields = ['nome']
        widgets = {'nome': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome da nova área'})}

class TipoAcaoForm(forms.ModelForm):
    class Meta:
        model = TipoAcao
        fields = ['area', 'nome']
        widgets = {
            'area': forms.Select(attrs={'class': 'form-select'}),
            'nome': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome do novo tipo de ação'}),
        }


class TipoServicoForm(forms.ModelForm):
    """Formulário simples para adicionar tipos de serviço (usado em modais)."""
    class Meta:
        model = TipoServico
        fields = ['nome']
        widgets = {'nome': forms.TextInput(attrs={'class': 'form-control'})}


class ServicoForm(forms.ModelForm):
    """Formulário para o cadastro de um serviço extrajudicial."""

    class Meta:
        model = Servico
        fields = ['cliente', 'tipo_servico', 'responsavel', 'descricao', 'recorrente', 'prazo']
        widgets = {
            # AJUSTE: Adicionamos a classe 'select2' para que o JavaScript encontre estes campos.
            'cliente': forms.Select(attrs={'class': 'form-select select2'}),
            'tipo_servico': forms.Select(attrs={'class': 'form-select select2'}),
            'responsavel': forms.Select(attrs={'class': 'form-select select2'}),

            'descricao': forms.TextInput(attrs={'class': 'form-control'}),
            'recorrente': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'prazo': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),

        }


class ServicoEditForm(forms.ModelForm):
    """Formulário completo para a edição de um serviço existente."""

    class Meta:
        model = Servico
        # --- ADICIONE 'codigo_servico_municipal' À LISTA ---
        fields = [
            'responsavel', 'descricao', 'data_inicio', 'recorrente', 'prazo',
            'data_encerramento', 'concluido', 'ativo', 'codigo_servico_municipal'
        ]
        widgets = {
            'responsavel': forms.Select(attrs={'class': 'form-select'}),
            'descricao': forms.TextInput(attrs={'class': 'form-control'}),
            # --- ADICIONE O WIDGET PARA O NOVO CAMPO ---
            'codigo_servico_municipal': forms.TextInput(attrs={'class': 'form-control'}),
            'data_inicio': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'recorrente': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'prazo': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'data_encerramento': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'concluido': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class MovimentacaoServicoForm(forms.ModelForm):
    """Formulário para registrar andamentos e tarefas de um serviço."""
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


class MovimentacaoForm(forms.ModelForm):
    """
    Formulário aprimorado para criar e editar andamentos, tarefas e prazos de um processo.
    """
    class Meta:
        model = Movimentacao
        # Lista de campos completa e na ordem lógica
        fields = [
            'titulo', 'tipo_movimentacao',
            'data_publicacao', 'data_intimacao',
            'dias_prazo', 'data_prazo_final', 'hora_prazo',
            'detalhes', 'link_referencia',
            'responsavel', 'status',
        ]
        # Widgets para usar os melhores tipos de input do HTML5
        widgets = {
            'data_publicacao': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'data_intimacao': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'data_prazo_final': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'hora_prazo': forms.TimeInput(format='%H:%M', attrs={'type': 'time'}),
            'detalhes': forms.Textarea(attrs={'rows': 4}),
            'link_referencia': forms.URLInput(attrs={'placeholder': 'https://tribunal.jus.br/consulta/...'}),
        }
        # Rótulos personalizados para clareza
        labels = {
            'titulo': 'Título / Resumo da Movimentação',
            'tipo_movimentacao': 'Tipo de Movimentação',
            'dias_prazo': 'Prazo em Dias (alternativo)',
        }

    def __init__(self, *args, **kwargs):
        """
        Construtor para aplicar classes do Bootstrap e outras lógicas dinâmicas.
        """
        super().__init__(*args, **kwargs)

        # Querysets para otimizar e ordenar as opções dos selects
        self.fields['tipo_movimentacao'].queryset = TipoMovimentacao.objects.all().order_by('-favorito', 'nome')
        self.fields['responsavel'].queryset = User.objects.filter(is_active=True).order_by('first_name', 'last_name')

        # Aplica a classe 'form-control' ou 'form-select' a todos os campos
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = 'form-select'
            elif not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'form-control'

    def clean(self):
        """
        Validação personalizada para garantir a consistência dos dados de prazo.
        """
        cleaned_data = super().clean()
        dias_prazo = cleaned_data.get('dias_prazo')
        data_prazo_final = cleaned_data.get('data_prazo_final')

        # Se o usuário preencher os dois, priorizamos a data final e limpamos os dias.
        if dias_prazo and data_prazo_final:
            cleaned_data['dias_prazo'] = None
            self.add_error(
                'dias_prazo',
                forms.ValidationError(
                    "Ambos os campos de prazo foram preenchidos. O sistema priorizou a 'Data do Prazo Final'.",
                    code='prazo_conflitante'
                )
            )
        return cleaned_data


class ServicoConcluirForm(forms.ModelForm):
    """Formulário específico para o ato de concluir um serviço."""
    class Meta:
        model = Servico
        fields = ['data_encerramento']
        widgets = {'data_encerramento': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['data_encerramento'].label = "Data de Conclusão"

# -----------------------------------------------------------------------------
# FORMULÁRIOS FINANCEIROS
# -----------------------------------------------------------------------------

class ContratoHonorariosForm(forms.ModelForm):
    """Formulário para registrar um novo contrato de honorários, gerando os lançamentos."""
    class Meta:
        model = ContratoHonorarios
        fields = ['descricao', 'valor_pagamento_fixo', 'qtde_pagamentos_fixos', 'data_primeiro_vencimento', 'percentual_exito']
        widgets = {
            'descricao': forms.TextInput(attrs={'class': 'form-control'}),
            'valor_pagamento_fixo': forms.NumberInput(attrs={'class': 'form-control'}),
            'qtde_pagamentos_fixos': forms.NumberInput(attrs={'class': 'form-control', 'value': 1}),
            'data_primeiro_vencimento': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'percentual_exito': forms.NumberInput(attrs={'class': 'form-control'}),
        }

from django import forms
# from .models import Pagamento # Certifique-se de importar seu modelo Pagamento

class PagamentoForm(forms.ModelForm):
    """Formulário para registrar o recebimento de um pagamento de um lançamento."""

    # Defina as escolhas e o campo forma_pagamento DIRETAMENTE na classe PagamentoForm,
    # antes da classe Meta.
    FORMA_PAGAMENTO_CHOICES = [
        ('PIX', 'Pix'),
        ('DINHEIRO', 'Dinheiro'),
        ('CARTAO', 'Cartão'),
        ('DEPOSITO', 'Depósito'),
        ('OUTRO', 'Outro'),
    ]

    forma_pagamento = forms.ChoiceField(
        choices=FORMA_PAGAMENTO_CHOICES,
        required=False,
        label="Tipo de Pagamento",
        # Adicione o widget aqui para aplicar classes CSS
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Pagamento
        fields = ['data_pagamento', 'valor_pago', 'forma_pagamento', 'observacoes']
        widgets = {
            'data_pagamento': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'valor_pago': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}), # Adicione step='0.01' para valores monetários
            # Não defina 'forma_pagamento' aqui novamente, pois já foi definido acima como ChoiceField
            'observacoes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:  # Se for um novo pagamento (não edição)
            self.fields['forma_pagamento'].initial = 'PIX'  # Define 'Pix' como padrão

        # Adicionalmente, você pode garantir que todos os campos tenham a classe 'form-control'
        # Isso é uma boa prática para formulários Bootstrap
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.TextInput) or \
               isinstance(field.widget, forms.NumberInput) or \
               isinstance(field.widget, forms.Textarea) or \
               isinstance(field.widget, forms.Select) or \
               isinstance(field.widget, forms.DateInput):
                field.widget.attrs.update({'class': 'form-control'})

# -----------------------------------------------------------------------------
# FORMULÁRIOS DE FERRAMENTAS (CÁLCULOS, MODELOS)
# -----------------------------------------------------------------------------

class CalculoForm(forms.Form):
    """
    Formulário para a interface de cálculo judicial.
    Usa forms.Form (e não ModelForm) porque a lógica de cálculo é executada
    antes de salvar no banco, e os dados de entrada podem não corresponder
    diretamente a todos os campos do modelo 'CalculoJudicial'.
    """
    # Choices são definidos aqui para centralizar as opções disponíveis na ferramenta
    INDICE_CHOICES = [('IPCA', 'IPCA (IBGE)'), ('INPC', 'INPC (IBGE)'), ('IGP-M', 'IGP-M (FGV/BCB)'), ('IGP-DI', 'IGP-DI (FGV/BCB)'), ('SELIC', 'Taxa Selic (BCB)'), ('TR', 'Taxa Referencial (BCB)')]
    JUROS_TIPO_CHOICES = [('SIMPLES', 'Simples'), ('COMPOSTO', 'Compostos')]
    JUROS_PERIODO_CHOICES = [('MENSAL', 'Mensal'), ('ANUAL', 'Anual')]

    # Definição de cada campo do formulário
    descricao = forms.CharField(label="Descrição do Cálculo", max_length=255, initial="Cálculo Padrão", widget=forms.TextInput(attrs={'class': 'form-control'}))
    valor_original = forms.DecimalField(label="Valor a ser atualizado (R$)", decimal_places=2, widget=forms.NumberInput(attrs={'class': 'form-control'}))
    data_inicio = forms.DateField(label="Data inicial da correção", widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}))
    data_fim = forms.DateField(label="Data final da correção", initial=date.today, widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}))
    indice = forms.ChoiceField(label="Índice de atualização", choices=INDICE_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}))
    correcao_pro_rata = forms.BooleanField(label="Correção Pro-Rata", required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    juros_taxa = forms.DecimalField(label="Taxa de juros (%)", required=False, decimal_places=4, widget=forms.NumberInput(attrs={'class': 'form-control'}))
    juros_periodo = forms.ChoiceField(label="Período da taxa", choices=JUROS_PERIODO_CHOICES, initial='MENSAL', widget=forms.Select(attrs={'class': 'form-select'}))
    juros_tipo = forms.ChoiceField(label="Tipo de juros", choices=JUROS_TIPO_CHOICES, initial='SIMPLES', widget=forms.Select(attrs={'class': 'form-select'}))
    juros_data_inicio = forms.DateField(label="Data inicial dos juros", required=False, widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}))
    juros_data_fim = forms.DateField(label="Data final dos juros", required=False, widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}))
    multa_percentual = forms.DecimalField(label="Percentual da multa (%)", required=False, decimal_places=2, widget=forms.NumberInput(attrs={'class': 'form-control'}))
    multa_sobre_juros = forms.BooleanField(label="Calcular a multa sobre os juros", required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    honorarios_percentual = forms.DecimalField(label="Percentual dos honorários (%)", required=False, decimal_places=2, widget=forms.NumberInput(attrs={'class': 'form-control'}))
    gerar_memorial = forms.BooleanField(label="Gerar Memorial de Cálculo", required=False, initial=True, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))


class ModeloDocumentoForm(forms.ModelForm):
    """Formulário para criar e editar Modelos de Documentos (templates)."""
    class Meta:
        model = ModeloDocumento
        # Os campos 'cabecalho', 'conteudo' e 'rodape' são RichTextUploadingFields
        # e usarão o widget do CKEditor automaticamente.
        fields = ['titulo', 'descricao', 'cabecalho', 'conteudo', 'rodape']
        widgets = {
            'titulo': forms.TextInput(attrs={'class': 'form-control'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class ClienteModalForm(forms.ModelForm):
    """
    Formulário simplificado para cadastro rápido de cliente via modal.
    Contém apenas os campos essenciais para identificação e contato imediato.
    """
    class Meta:
        model = Cliente
        # Define apenas os campos essenciais para o cadastro rápido
        fields = [
            'nome_completo',
            'tipo_pessoa',
            'cpf_cnpj',
            'email',
            'telefone_principal',
            'is_cliente'  # <-- CAMPO ADICIONADO AQUI

        ]
        # Widgets para manter a estilização do Bootstrap
        widgets = {
            'nome_completo': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo_pessoa': forms.Select(attrs={'class': 'form-select'}),
            'cpf_cnpj': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'telefone_principal': forms.TextInput(attrs={'class': 'form-control'}),
            'is_cliente': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class EscritorioConfiguracaoForm(forms.ModelForm):
    class Meta:
        model = EscritorioConfiguracao
        fields = '__all__'
        widgets = {
            'nome_escritorio': forms.TextInput(attrs={'class': 'form-control'}),
            'cnpj': forms.TextInput(attrs={'class': 'form-control'}),
            'oab_principal': forms.TextInput(attrs={'class': 'form-control'}),
            'cep': forms.TextInput(attrs={'class': 'form-control'}),
            'logradouro': forms.TextInput(attrs={'class': 'form-control'}),
            'numero': forms.TextInput(attrs={'class': 'form-control'}),
            'complemento': forms.TextInput(attrs={'class': 'form-control'}),
            'bairro': forms.TextInput(attrs={'class': 'form-control'}),
            'cidade': forms.TextInput(attrs={'class': 'form-control'}),
            'estado': forms.Select(attrs={'class': 'form-select'}),
            'telefone_contato': forms.TextInput(attrs={'class': 'form-control'}),
            'email_contato': forms.EmailInput(attrs={'class': 'form-control'}),
        }


class CustomUserCreationForm(UserCreationForm):
    """ Formulário aprimorado para criação de usuários. """

    # Usamos ModelMultipleChoiceField com CheckboxSelectMultiple para uma melhor UX
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all().order_by('name'),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Grupos de Permissão",
        help_text="Define o cargo e o nível de acesso do usuário no sistema."
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'first_name', 'last_name', 'email')
        # Adiciona placeholders e classes para estilização com Bootstrap
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ex: jose.silva'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome do usuário'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Sobrenome do usuário'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'ex: email@dominio.com'}),
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            # Salva os grupos (relação Many-to-Many)
            user.groups.set(self.cleaned_data['groups'])
            self.save_m2m()
        return user


class CustomUserChangeForm(UserChangeForm):
    """ Formulário aprimorado para a EDIÇÃO de usuários existentes. """
    password = None  # Remove completamente o manuseio de senhas deste formulário

    class Meta(UserChangeForm.Meta):
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'is_active', 'is_staff', 'groups')
        widgets = {
            # APRIMORAMENTO: Desabilita a edição do nome de usuário
            'username': forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'groups': forms.CheckboxSelectMultiple, # Garante o uso de checkboxes
        }

from django.contrib.auth.models import User
from simple_history import register

# Esta linha instrui o simple-history a começar a monitorar
# e a criar um histórico para o modelo de Usuário do Django.
register(User)

class UsuarioPerfilForm(forms.ModelForm):
    class Meta:
        model = UsuarioPerfil
        # Incluímos apenas os campos que o usuário deve poder editar diretamente
        fields = ['cpf', 'oab', 'telefone', 'data_admissao', 'foto']
        widgets = {
            'cpf': forms.TextInput(attrs={'class': 'form-control'}),
            'oab': forms.TextInput(attrs={'class': 'form-control'}),
            'telefone': forms.TextInput(attrs={'class': 'form-control'}),
            'data_admissao': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'foto': forms.FileInput(attrs={'class': 'form-control'}),
        }

class LancamentoFinanceiroForm(forms.ModelForm):
    """
    Formulário para o cadastro manual de contas a pagar e a receber
    que não estão vinculadas a contratos.
    """
    # Adicionamos o campo de cliente, que é obrigatório
    cliente = forms.ModelChoiceField(
        queryset=Cliente.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select select2-modal'}),
        required=False,
        label="Cliente (Opcional)"
    )

    class Meta:
        model = LancamentoFinanceiro
        # Campos que o usuário poderá preencher manualmente
        fields = [
            'descricao', 'valor', 'data_vencimento', 'tipo', 'cliente',
            'processo', 'servico', 'categoria'
        ]
        widgets = {
            'descricao': forms.TextInput(attrs={'class': 'form-control'}),
            'valor': forms.NumberInput(attrs={'class': 'form-control'}),
            'data_vencimento': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            # Select2 para os campos de relacionamento, para facilitar a busca
            'processo': forms.Select(attrs={'class': 'form-select select2-modal'}),
            'servico': forms.Select(attrs={'class': 'form-select select2-modal'}),
            'categoria': forms.Select(attrs={'class': 'form-select'}),  # <--- ADICIONE ESTE WIDGET

        }
        labels = {
            'processo': 'Vincular a um Processo (Opcional)',
            'servico': 'Vincular a um Serviço (Opcional)',
        }


class DespesaTipoForm(forms.Form):
    """Formulário simples para a seleção inicial do tipo de despesa no wizard."""
    TIPO_DESPESA_CHOICES = [
        ('', 'Selecione...'),
        ('pontual', 'Pontual (Conta única)'),
        ('recorrente_fixa', 'Recorrente Fixa (Aluguel, Salário)'),
        ('recorrente_variavel', 'Recorrente Variável (Luz, Água)'),
    ]
    tipo_despesa = forms.ChoiceField(
        choices=TIPO_DESPESA_CHOICES,
        label="Qual o tipo de despesa?",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    categoria = forms.ChoiceField(
        choices=LancamentoFinanceiro.CATEGORIA_CHOICES, # Reutiliza as escolhas do modelo
        label="Categoria da Despesa",
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

class DespesaPontualForm(forms.Form):
    """Formulário para despesas pontuais."""
    # NOVO: Adicione o campo cliente
    cliente = forms.ModelChoiceField(
        queryset=Cliente.objects.all(),
        required=False, # Definido como opcional no formulário
        label="Cliente Relacionado (Opcional)",
        widget=forms.Select(attrs={'class': 'form-select select2-despesa-wizard'}) # Adicione uma classe para Select2
    )
    descricao = forms.CharField(label="Descrição da Despesa", widget=forms.TextInput(attrs={'class': 'form-control'}))
    valor = forms.DecimalField(label="Valor (R$)", max_digits=12, decimal_places=2,
                               widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}))
    data_vencimento = forms.DateField(label="Data de Vencimento",
                                      widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}))

class DespesaRecorrenteFixaForm(forms.Form):
    """Formulário para despesas recorrentes fixas."""
    # NOVO: Adicione o campo cliente
    cliente = forms.ModelChoiceField(
        queryset=Cliente.objects.all(),
        required=False,
        label="Cliente Relacionado (Opcional)",
        widget=forms.Select(attrs={'class': 'form-select select2-despesa-wizard'})
    )
    descricao = forms.CharField(label="Descrição da Despesa", widget=forms.TextInput(attrs={'class': 'form-control'}))
    valor_recorrente = forms.DecimalField(label="Valor Fixo Mensal (R$)", max_digits=12, decimal_places=2,
                                          widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}))
    dia_vencimento_recorrente = forms.IntegerField(label="Dia do Vencimento no Mês", min_value=1, max_value=31,
                                                   widget=forms.NumberInput(attrs={'class': 'form-control'}))
    data_inicio_recorrencia = forms.DateField(label="Início da Recorrência",
                                              widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}))
    data_fim_recorrencia = forms.DateField(label="Fim da Recorrência (Opcional)", required=False,
                                           widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}))

class DespesaRecorrenteVariavelForm(forms.Form):
    """Formulário para despesas recorrentes variáveis (lançamento do mês atual)."""
    # NOVO: Adicione o campo cliente
    cliente = forms.ModelChoiceField(
        queryset=Cliente.objects.all(),
        required=False,
        label="Cliente Relacionado (Opcional)",
        widget=forms.Select(attrs={'class': 'form-select select2-despesa-wizard'})
    )
    descricao = forms.CharField(label="Descrição da Despesa", widget=forms.TextInput(attrs={'class': 'form-control'}))
    valor = forms.DecimalField(label="Valor (R$)", max_digits=12, decimal_places=2,
                               widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}))
    data_vencimento = forms.DateField(label="Data de Vencimento",
                                      widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}))


class CalculoJudicialForm(forms.ModelForm):
    class Meta:
        model = CalculoJudicial
        # Inclua os campos que aparecem na seção "Dados Gerais"
        fields = ['descricao', 'valor_original']

        widgets = {
            'descricao': forms.TextInput(
                attrs={
                    'class': 'form-control',  # Adiciona a classe do Bootstrap
                }
            ),
            'valor_original': forms.TextInput(
                attrs={
                    'class': 'form-control',  # Adiciona a classe do Bootstrap
                    'style': 'text-align: right;',  # Alinha o texto à direita para valores monetários
                    'placeholder': '0,00'
                }
            ),
        }

        labels = {
            'descricao': 'Descrição do Cálculo',
            'valor_original': 'Valor a ser atualizado',  # Rótulo igual ao da imagem
        }


class FaseCalculoForm(forms.ModelForm):
    """Formulário para uma única fase de cálculo."""
    class Meta:
        model = FaseCalculo
        fields = ['ordem', 'data_inicio', 'data_fim', 'indice', 'juros_taxa', 'juros_tipo', 'observacao']
        widgets = {
            'ordem': forms.HiddenInput(),
            'data_inicio': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'data_fim': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'indice': forms.Select(attrs={'class': 'form-select indice-select'}),
            'juros_taxa': forms.NumberInput(attrs={'class': 'form-control juros-taxa', 'step': '0.0001'}),
            'juros_tipo': forms.Select(attrs={'class': 'form-select juros-tipo'}),
            'observacao': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Correção até a citação'}),
        }

# Cria um FormSet para as fases, ligado ao cálculo principal
FaseCalculoFormSet = inlineformset_factory(
    CalculoJudicial,
    FaseCalculo,
    form=FaseCalculoForm,
    # --- CORREÇÃO APLICADA ---
    # extra=0 garante que o formset nunca adicione um formulário em branco por padrão.
    # A view será responsável por essa lógica.
    extra=0,
    can_delete=True,
    min_num=1,
    validate_min=True,
)
