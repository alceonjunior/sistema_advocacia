# gestao/models.py

# --- Imports Necessários ---
from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from simple_history.models import HistoricalRecords
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from django.urls import reverse  # <<< ADICIONE ESTA LINHA

from datetime import date

# --- Modelos de Base (Entidades Principais) ---

class Cliente(models.Model):
    """Representa um cliente do escritório, seja pessoa física ou jurídica."""
    TIPO_PESSOA_CHOICES = [('PF', 'Pessoa Física'), ('PJ', 'Pessoa Jurídica')]
    nome_completo = models.CharField(max_length=255, verbose_name="Nome Completo ou Razão Social")
    tipo_pessoa = models.CharField(max_length=2, choices=TIPO_PESSOA_CHOICES, default='PF', verbose_name="Tipo de Pessoa")
    cpf_cnpj = models.CharField(max_length=18, unique=True, blank=True, null=True, verbose_name="CPF/CNPJ")
    email = models.EmailField(max_length=255, blank=True, null=True, verbose_name="E-mail")
    telefone_principal = models.CharField(max_length=20, blank=True, null=True, verbose_name="Telefone Principal")
    history = HistoricalRecords()

    def __str__(self):
        return f"{self.nome_completo}"

    class Meta:
        ordering = ['nome_completo']


class UsuarioPerfil(models.Model):
    """Estende o modelo de usuário padrão do Django com informações específicas do escritório."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="perfil")
    cargo = models.CharField(max_length=20, choices=[('ADVOGADO', 'Advogado(a)'), ('ESTAGIARIO', 'Estagiário(a)')], null=True, blank=True)
    history = HistoricalRecords()

    def __str__(self):
        return self.user.username


# --- Modelos de Estrutura ---

class AreaProcesso(models.Model):
    """Categoriza as grandes áreas do direito (Cível, Criminal, etc.)."""
    nome = models.CharField(max_length=100, unique=True, verbose_name="Nome da Área")
    history = HistoricalRecords()
    def __str__(self): return self.nome


class TipoAcao(models.Model):
    """Define os tipos de ação específicos dentro de cada área."""
    area = models.ForeignKey(AreaProcesso, on_delete=models.PROTECT, related_name="tipos_de_acao")
    nome = models.CharField(max_length=255, verbose_name="Nome do Tipo de Ação")
    history = HistoricalRecords()
    def __str__(self): return f"{self.area.nome} - {self.nome}"


class TipoServico(models.Model):
    """Categoriza os serviços extrajudiciais (Consultoria, Inventário, etc.)."""
    nome = models.CharField(max_length=100, unique=True, verbose_name="Nome do Serviço")
    history = HistoricalRecords()
    def __str__(self): return self.nome


class TipoMovimentacao(models.Model):
    """Define os tipos de andamentos que podem ocorrer em um processo ou tarefa."""
    nome = models.CharField(max_length=200, unique=True, verbose_name="Nome do Tipo de Movimentação")
    sugestao_dias_prazo = models.PositiveIntegerField(null=True, blank=True, verbose_name="Sugestão de Dias para Prazo")
    history = HistoricalRecords()
    def __str__(self): return self.nome


# --- Modelos de Trabalho (Processo e Serviço) ---

class Processo(models.Model):
    """Representa um caso judicial."""
    #cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="processos")
    tipo_acao = models.ForeignKey(TipoAcao, on_delete=models.SET_NULL, null=True, blank=True, related_name="processos")
    numero_processo = models.CharField(max_length=50, blank=True, null=True)
    advogado_responsavel = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="processos_responsaveis")
    status_processo = models.CharField(max_length=30, choices=[('ATIVO', 'Ativo'), ('SUSPENSO', 'Suspenso'), ('ARQUIVADO', 'Arquivado')], default='ATIVO')
    vara_comarca_orgao = models.CharField(max_length=255, blank=True, null=True)
    valor_causa = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    descricao_caso = models.TextField(blank=True, null=True)
    observacoes_internas = models.TextField(blank=True, null=True)
    history = HistoricalRecords()

    def __str__(self):
        # Tenta encontrar o primeiro autor na lista de partes do processo
        autor_principal = self.partes.filter(tipo_participacao='AUTOR').first()

        # Se encontrar um autor, usa o nome dele na representação
        if autor_principal:
            return f"Processo {self.numero_processo or 'N/A'} - {autor_principal.cliente.nome_completo}"

        # Se não houver autor (ou nenhuma parte ainda), retorna um texto padrão
        return f"Processo {self.numero_processo or 'N/A'}"

    def get_absolute_url(self):
        return reverse('detalhe_processo', kwargs={'pk': self.pk})

    def get_polo_ativo_display(self):
        """Busca todos os clientes no polo ativo e retorna os nomes separados por vírgula."""
        autores = self.partes.filter(tipo_participacao='AUTOR')
        if not autores:
            return "Nenhum autor definido"
        return ", ".join([p.cliente.nome_completo for p in autores])

    def get_polo_passivo_display(self):
        """Busca todos os clientes no polo passivo e retorna os nomes separados por vírgula."""
        reus = self.partes.filter(tipo_participacao='REU')
        if not reus:
            return "Nenhum réu definido"
        return ", ".join([p.cliente.nome_completo for p in reus])


class ParteProcesso(models.Model):
    """Modelo intermediário para registrar as múltiplas partes de um processo."""
    TIPO_CHOICES = [
        ('AUTOR', 'Polo Ativo (Autor)'),
        ('REU', 'Polo Passivo (Réu)'),
        ('TERCEIRO', 'Terceiro Interessado'),
        ('VITIMA', 'Vítima'),
        ('TESTEMUNHA', 'Testemunha'),
    ]

    processo = models.ForeignKey(Processo, on_delete=models.CASCADE, related_name="partes")
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="participacoes")
    tipo_participacao = models.CharField(max_length=20, choices=TIPO_CHOICES, verbose_name="Tipo de Participação")

    # Campo chave para os casos de família (representação de menor)
    representado_por = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='representa',
        verbose_name="É representado/assistido por"
    )

    history = HistoricalRecords()

    class Meta:
        unique_together = (
        'processo', 'cliente')  # Garante que um cliente não seja adicionado duas vezes no mesmo processo
        ordering = ['tipo_participacao', 'cliente__nome_completo']

    def __str__(self):
        return f"{self.cliente.nome_completo} ({self.get_tipo_participacao_display()})"


class Servico(models.Model):
    """Representa um serviço extrajudicial prestado a um cliente."""
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="servicos")
    tipo_servico = models.ForeignKey(TipoServico, on_delete=models.PROTECT, related_name="servicos")

    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True, # Deixamos como opcional para não quebrar serviços existentes
        related_name="servicos_responsaveis",
        verbose_name="Responsável pelo Serviço"
    )

    descricao = models.CharField(max_length=255, verbose_name="Descrição Detalhada do Serviço")
    data_inicio = models.DateField(default=date.today)
    prazo = models.DateField(null=True, blank=True, verbose_name="Prazo de Conclusão")
    concluido = models.BooleanField(default=False, verbose_name="Concluído")
    data_encerramento = models.DateField(null=True, blank=True, verbose_name="Data de Encerramento (para recorrentes)")
    recorrente = models.BooleanField(default=False, verbose_name="É um serviço recorrente (mensal)?")
    ativo = models.BooleanField(default=True)



    history = HistoricalRecords()

    def __str__(self):
        return f"{self.tipo_servico} - {self.cliente}"

    def get_absolute_url(self):
        return reverse('detalhe_servico', kwargs={'pk': self.pk})


    class Meta:
        ordering = ['-data_inicio']


# --- Modelos de Movimentações ---

class Movimentacao(models.Model):
    """Registra cada andamento, prazo ou tarefa de um processo."""
    processo = models.ForeignKey(Processo, on_delete=models.CASCADE, related_name="movimentacoes")
    tipo_movimentacao = models.ForeignKey(TipoMovimentacao, on_delete=models.SET_NULL, null=True, blank=True)
    titulo = models.CharField(max_length=255)
    detalhes = models.TextField(blank=True, null=True)
    data_publicacao = models.DateField(null=True, blank=True)
    dias_prazo = models.PositiveIntegerField(null=True, blank=True)
    data_prazo_final = models.DateField(null=True, blank=True)
    responsavel = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="movimentacoes_responsaveis")
    status = models.CharField(max_length=20, choices=[('PENDENTE', 'Pendente'), ('EM_ANDAMENTO', 'Em Andamento'), ('CONCLUIDA', 'Concluída')], default='PENDENTE')
    data_criacao = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()

    def __str__(self): return self.titulo

    def save(self, *args, **kwargs):
        if self.data_publicacao and self.dias_prazo and not self.data_prazo_final:
            self.data_prazo_final = self.data_publicacao + timedelta(days=self.dias_prazo)
        super().save(*args, **kwargs)


class MovimentacaoServico(models.Model):
    """Registra cada andamento ou tarefa de um serviço extrajudicial."""
    servico = models.ForeignKey(Servico, on_delete=models.CASCADE, related_name="movimentacoes")
    titulo = models.CharField(max_length=255, verbose_name="Título / Resumo da Atividade")
    detalhes = models.TextField(blank=True, null=True)
    data_atividade = models.DateField(default=date.today)
    responsavel = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="movimentacoes_servicos_responsaveis")
    status = models.CharField(max_length=20, choices=[('PENDENTE', 'Pendente'), ('EM_ANDAMENTO', 'Em Andamento'), ('CONCLUIDA', 'Concluída'), ('CANCELADA', 'Cancelada')], default='PENDENTE')
    prazo_final = models.DateField(null=True, blank=True, verbose_name="Prazo Final")
    data_criacao = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()

    def __str__(self): return self.titulo


# --- Modelos Financeiros ---

class ContratoHonorarios(models.Model):
    """Armazena os termos de um acordo financeiro, agora para Processos OU Serviços."""
    # Este é o "apontador genérico"
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')


    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="contratos_honorarios_cliente")
    descricao = models.CharField(max_length=255, default="Honorários Contratuais")
    valor_pagamento_fixo = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Valor de Cada Pagamento (R$)")
    qtde_pagamentos_fixos = models.PositiveIntegerField(default=1, verbose_name="Qtde. de Pagamentos Fixos")
    data_primeiro_vencimento = models.DateField(verbose_name="Data do Primeiro Vencimento")
    percentual_exito = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Percentual de Êxito (%)")
    history = HistoricalRecords()

    def __str__(self):
        return f"Contrato: {self.descricao} - {self.content_object}"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new and self.qtde_pagamentos_fixos > 0 and self.valor_pagamento_fixo > 0:
            for i in range(self.qtde_pagamentos_fixos):
                lancamento_data = {
                    'cliente': self.cliente, 'contrato': self,
                    'descricao': f"{self.descricao} - Parcela {i + 1}/{self.qtde_pagamentos_fixos}",
                    'valor': self.valor_pagamento_fixo,
                    'data_vencimento': self.data_primeiro_vencimento + relativedelta(months=i)
                }
                if isinstance(self.content_object, Processo):
                    lancamento_data['processo'] = self.content_object
                elif isinstance(self.content_object, Servico):
                    lancamento_data['servico'] = self.content_object
                LancamentoFinanceiro.objects.create(**lancamento_data)


class LancamentoFinanceiro(models.Model):
    """Representa uma única fatura ou conta a pagar/receber."""
    TIPO_CHOICES = [('RECEITA', 'Receita'), ('DESPESA', 'Despesa')]

    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="lancamentos")
    processo = models.ForeignKey(Processo, on_delete=models.CASCADE, null=True, blank=True, related_name="lancamentos")
    servico = models.ForeignKey(Servico, on_delete=models.CASCADE, null=True, blank=True, related_name="lancamentos")
    contrato = models.ForeignKey(ContratoHonorarios, on_delete=models.SET_NULL, null=True, blank=True, related_name="lancamentos")
    descricao = models.CharField(max_length=255)
    valor = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Valor Devido")
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, default='RECEITA')
    data_vencimento = models.DateField()
    history = HistoricalRecords()

    @property
    def valor_pago(self):
        return self.pagamentos.aggregate(total=models.Sum('valor_pago'))['total'] or Decimal('0.00')

    @property
    def saldo_devedor(self):
        return self.valor - self.valor_pago

    @property
    def status(self):
        if self.saldo_devedor <= 0: return 'PAGO'
        if self.valor_pago > 0: return 'PARCIALMENTE_PAGO'
        if self.data_vencimento < date.today(): return 'ATRASADO'
        return 'A_PAGAR'

    def __str__(self):
        return f"{self.descricao} (R$ {self.valor})"


class Pagamento(models.Model):
    """Registra cada pagamento individual efetuado para um Lançamento Financeiro."""
    lancamento = models.ForeignKey(LancamentoFinanceiro, on_delete=models.CASCADE, related_name="pagamentos")
    data_pagamento = models.DateField(default=date.today)
    valor_pago = models.DecimalField(max_digits=12, decimal_places=2)
    forma_pagamento = models.CharField(max_length=100, blank=True, null=True)
    observacoes = models.TextField(blank=True, null=True)
    history = HistoricalRecords()

    def __str__(self):
        return f"Pagamento de R$ {self.valor_pago} para {self.lancamento.descricao}"


class CalculoJudicial(models.Model):
    """Armazena o histórico de um cálculo realizado, incluindo todos os parâmetros."""
    processo = models.ForeignKey(Processo, on_delete=models.CASCADE, related_name="calculos")
    descricao = models.CharField(max_length=255, default="Cálculo Padrão")
    responsavel = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    data_calculo = models.DateTimeField(auto_now_add=True)

    # --- Parâmetros do Cálculo ---
    valor_original = models.DecimalField(max_digits=12, decimal_places=2)
    data_inicio_correcao = models.DateField()
    data_fim_correcao = models.DateField()
    indice_correcao = models.CharField(max_length=10)
    correcao_pro_rata = models.BooleanField(default=False)
    juros_percentual = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True)
    juros_tipo = models.CharField(max_length=10, null=True, blank=True)
    juros_periodo = models.CharField(max_length=10, null=True, blank=True)

    # === CAMPOS ADICIONADOS AQUI ===
    juros_data_inicio = models.DateField(null=True, blank=True, verbose_name="Data de Início dos Juros")
    juros_data_fim = models.DateField(null=True, blank=True, verbose_name="Data Final dos Juros")
    # === FIM DA ADIÇÃO ===

    multa_percentual = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    multa_sobre_juros = models.BooleanField(default=False)
    honorarios_percentual = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    # --- Resultados do Cálculo ---
    valor_corrigido = models.DecimalField(max_digits=15, decimal_places=2)
    valor_final = models.DecimalField(max_digits=15, decimal_places=2)
    memoria_calculo = models.JSONField()

    history = HistoricalRecords()

    def __str__(self):
        return f"{self.descricao} (R$ {self.valor_original})"

    class Meta:
        ordering = ['-data_calculo']
