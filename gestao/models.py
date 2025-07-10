# gestao/models.py

# --- Imports Necessários ---
# Importações padrão do Django para criar modelos e gerenciar URLs.
from django.db import models
from django.conf import settings
from django.urls import reverse
from django.db.models.signals import post_save
from django.dispatch import receiver
from simple_history.models import HistoricalRecords

# Import para relacionamentos genéricos, mantido por compatibilidade.
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

# Import para registrar o histórico de alterações em cada registro. Essencial para auditoria.
from simple_history.models import HistoricalRecords

# Imports para manipulação de datas e valores decimais.
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from decimal import Decimal

# Import do CKEditor para campos de texto rico.
from ckeditor_uploader.fields import RichTextUploadingField


# --- Modelos de Base (Entidades Principais) ---
# Esta seção define as entidades fundamentais que são usadas em todo o sistema,
# como Cliente e Perfil de Usuário. Eles permanecem como a base do sistema.

class Cliente(models.Model):
    """Representa um cliente do escritório, seja pessoa física ou jurídica, com todos os campos necessários para qualificação processual."""

    # --- Choices (Opções Pré-definidas) ---
    TIPO_PESSOA_CHOICES = [('PF', 'Pessoa Física'), ('PJ', 'Pessoa Jurídica')]
    ESTADO_CIVIL_CHOICES = [
        ('SOLTEIRO', 'Solteiro(a)'),
        ('CASADO', 'Casado(a)'),
        ('DIVORCIADO', 'Divorciado(a)'),
        ('VIUVO', 'Viúvo(a)'),
        ('UNIAO_ESTAVEL', 'União Estável'),
    ]
    ESTADOS_BRASILEIROS_CHOICES = [
        ('AC', 'Acre'), ('AL', 'Alagoas'), ('AP', 'Amapá'), ('AM', 'Amazonas'),
        ('BA', 'Bahia'), ('CE', 'Ceará'), ('DF', 'Distrito Federal'), ('ES', 'Espírito Santo'),
        ('GO', 'Goiás'), ('MA', 'Maranhão'), ('MT', 'Mato Grosso'), ('MS', 'Mato Grosso do Sul'),
        ('MG', 'Minas Gerais'), ('PA', 'Pará'), ('PB', 'Paraíba'), ('PR', 'Paraná'),
        ('PE', 'Pernambuco'), ('PI', 'Piauí'), ('RJ', 'Rio de Janeiro'), ('RN', 'Rio Grande do Norte'),
        ('RS', 'Rio Grande do Sul'), ('RO', 'Rondônia'), ('RR', 'Roraima'), ('SC', 'Santa Catarina'),
        ('SP', 'São Paulo'), ('SE', 'Sergipe'), ('TO', 'Tocantins')
    ]

    # --- Bloco 1: Dados Fundamentais ---
    nome_completo = models.CharField(max_length=255, verbose_name="Nome Completo / Razão Social")
    tipo_pessoa = models.CharField(max_length=2, choices=TIPO_PESSOA_CHOICES, default='PF',
                                   verbose_name="Tipo de Pessoa")
    cpf_cnpj = models.CharField(max_length=18, unique=True, blank=True, null=True, verbose_name="CPF/CNPJ")
    email = models.EmailField(max_length=255, blank=True, null=True, verbose_name="E-mail")
    telefone_principal = models.CharField(max_length=20, blank=True, null=True, verbose_name="Telefone Principal")

    # --- Bloco 2: Qualificação Pessoa Física (PF) ---
    data_nascimento = models.DateField(blank=True, null=True, verbose_name="Data de Nascimento")
    nacionalidade = models.CharField(max_length=100, blank=True, null=True, default="Brasileiro(a)",
                                     verbose_name="Nacionalidade")
    estado_civil = models.CharField(max_length=20, choices=ESTADO_CIVIL_CHOICES, blank=True, null=True,
                                    verbose_name="Estado Civil")
    profissao = models.CharField(max_length=255, blank=True, null=True, verbose_name="Profissão")

    # --- Bloco 3: Endereço ---
    cep = models.CharField(max_length=9, blank=True, null=True, verbose_name="CEP")
    logradouro = models.CharField(max_length=255, blank=True, null=True, verbose_name="Logradouro (Rua, Av.)")
    numero = models.CharField(max_length=20, blank=True, null=True, verbose_name="Número")
    complemento = models.CharField(max_length=100, blank=True, null=True, verbose_name="Complemento")
    bairro = models.CharField(max_length=100, blank=True, null=True, verbose_name="Bairro")
    cidade = models.CharField(max_length=100, blank=True, null=True, verbose_name="Cidade")
    estado = models.CharField(max_length=2, choices=ESTADOS_BRASILEIROS_CHOICES, blank=True, null=True,
                              verbose_name="Estado (UF)")

    # --- Bloco 4: Representação Pessoa Jurídica (PJ) ---
    representante_legal = models.CharField(max_length=255, blank=True, null=True,
                                           verbose_name="Nome do Representante Legal")
    cpf_representante_legal = models.CharField(max_length=14, blank=True, null=True,
                                               verbose_name="CPF do Representante")

    # --- Bloco 5: Dados de Controle ---
    is_cliente = models.BooleanField(default=True, verbose_name="É um cliente?") # NOVO CAMPO ADICIONADO

    data_cadastro = models.DateField(auto_now_add=True, verbose_name="Data de Cadastro", editable=False, null=True,
                                     db_index=True)
    history = HistoricalRecords()

    def __str__(self):
        return self.nome_completo

    @property
    def qualificacao(self):
        """
        Gera o texto de qualificação completo para uso em documentos,
        adaptando-se para PF ou PJ e tratando campos vazios.
        """
        if self.tipo_pessoa == 'PF':
            partes = [self.nome_completo]
            if self.nacionalidade: partes.append(self.nacionalidade)
            if self.estado_civil: partes.append(self.get_estado_civil_display())
            if self.profissao: partes.append(self.profissao)
            if self.cpf_cnpj: partes.append(f"portador(a) do CPF nº {self.cpf_cnpj}")
            if self.logradouro:
                endereco = f"residente e domiciliado(a) na {self.logradouro}, nº {self.numero or 's/n'}"
                if self.complemento: endereco += f", {self.complemento}"
                if self.bairro: endereco += f", Bairro {self.bairro}"
                if self.cidade: endereco += f", {self.cidade}/{self.estado}"
                if self.cep: endereco += f", CEP: {self.cep}"
                partes.append(endereco)
            return ", ".join(filter(None, partes))
        else:  # Pessoa Jurídica
            partes = [self.nome_completo]
            if self.cpf_cnpj: partes.append(f"inscrita no CNPJ sob o nº {self.cpf_cnpj}")
            if self.logradouro:
                endereco = f"com sede na {self.logradouro}, nº {self.numero or 's/n'}"
                if self.cidade: endereco += f", {self.cidade}/{self.estado}"
                partes.append(endereco)
            if self.representante_legal:
                rep_str = f"neste ato representada por seu(sua) representante legal, {self.representante_legal}"
                if self.cpf_representante_legal: rep_str += f", portador(a) do CPF nº {self.cpf_representante_legal}"
                partes.append(rep_str)
            return ", ".join(filter(None, partes))

    class Meta:
        ordering = ['nome_completo']


class UsuarioPerfil(models.Model):
    """ Estende o modelo de usuário padrão do Django com informações específicas do escritório. """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="perfil")

    # CAMPOS NOVOS E APRIMORADOS
    cpf = models.CharField(max_length=14, null=True, blank=True, verbose_name="CPF")
    oab = models.CharField(max_length=20, null=True, blank=True, verbose_name="Nº da OAB (ex: 12345/PR)")
    telefone = models.CharField(max_length=20, null=True, blank=True, verbose_name="Telefone")
    data_admissao = models.DateField(null=True, blank=True, verbose_name="Data de Admissão")
    foto = models.ImageField(upload_to='fotos_perfil/', null=True, blank=True, verbose_name="Foto de Perfil")

    # Campo 'cargo' mantido por compatibilidade, mas o ideal é usar os Grupos do Django
    cargo = models.CharField(max_length=20, choices=[('ADVOGADO', 'Advogado(a)'), ('ESTAGIARIO', 'Estagiário(a)')],
                             null=True, blank=True)

    history = HistoricalRecords()

    def __str__(self):
        return self.user.username


# ==========================================================
# ↓↓↓ SINAL PARA CRIAÇÃO AUTOMÁTICA DE PERFIL ↓↓↓
# Adicione este código no final do seu models.py
# ==========================================================
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def criar_ou_atualizar_perfil_usuario(sender, instance, created, **kwargs):
    """
    Cria um perfil de usuário automaticamente toda vez que um novo usuário é criado.
    """
    if created:
        UsuarioPerfil.objects.create(user=instance)
    instance.perfil.save()


# --- Modelos de Estrutura e Suporte ---
# Estes modelos servem para categorizar e organizar informações que se repetem.
# A modelagem normalizada aqui evita a repetição de strings e facilita a manutenção.

class AreaProcesso(models.Model):
    """Categoriza as grandes áreas do direito (Cível, Criminal, etc.)."""
    nome = models.CharField(max_length=100, unique=True, verbose_name="Nome da Área")
    history = HistoricalRecords()

    def __str__(self): return self.nome


class TipoAcao(models.Model):
    """Define os tipos de ação (classe processual) dentro de cada área."""
    area = models.ForeignKey(AreaProcesso, on_delete=models.PROTECT, related_name="tipos_de_acao")
    nome = models.CharField(max_length=255, verbose_name="Nome do Tipo de Ação/Classe Processual")
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

    class Meta:
        ordering = ['nome'] # <-- LINHA ADICIONADA AQUI

    def __str__(self): return self.nome



# CORREÇÃO DE ORDEM: ModeloDocumento foi movido para ANTES de Documento
# para resolver o NameError.
class ModeloDocumento(models.Model):
    """Representa um modelo de documento (template) que pode ser reutilizado."""

    class Meta:
        verbose_name = "Modelo de Documento"
        verbose_name_plural = "Modelos de Documentos"
        ordering = ['titulo']

    titulo = models.CharField(max_length=255, verbose_name="Título do Modelo")
    descricao = models.TextField(blank=True, null=True, verbose_name="Descrição / Instruções de Uso")
    cabecalho = RichTextUploadingField(verbose_name="Cabeçalho", blank=True, null=True, config_name='advanced')
    conteudo = RichTextUploadingField(verbose_name="Corpo do Documento", config_name='advanced')
    rodape = RichTextUploadingField(verbose_name="Rodapé", blank=True, null=True, config_name='advanced')
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_modificacao = models.DateTimeField(auto_now=True)

    def __str__(self): return self.titulo


# --- Modelo Principal: Processo (Totalmente Refatorado) ---

class Processo(models.Model):
    """Modelo central que consolida todas as informações de um caso judicial."""
    # Seção de CHOICES: Centraliza as opções para os campos de escolha.
    STATUS_CHOICES = [('ATIVO', 'Ativo'), ('SUSPENSO', 'Suspenso'), ('ARQUIVADO', 'Arquivado'), ('EXTINTO', 'Extinto'),
                      ('EM_RECURSO', 'Em Recurso'), ('ENCERRADO', 'Encerrado com Resolução')]
    FASE_CHOICES = [('POSTULATORIA', 'Postulatória'), ('INSTRUTORIA', 'Instrutória'), ('DECISORIA', 'Decisória'),
                    ('RECURSAL', 'Recursal'), ('EXECUCAO', 'Execução'), ('ARQUIVAMENTO', 'Arquivamento')]
    TRIBUNAL_CHOICES = [('TJSP', 'TJSP'), ('TJPR', 'TJPR'), ('TJRS', 'TJRS'), ('TRF1', 'TRF-1'), ('TRF2', 'TRF-2'),
                        ('TRF3', 'TRF-3'), ('TRF4', 'TRF-4'), ('TRF5', 'TRF-5'), ('TRF6', 'TRF-6'), ('TST', 'TST'),
                        ('STJ', 'STJ'), ('STF', 'STF'), ('OUTRO', 'Outro')]
    GRAU_CHOICES = [('PRIMEIRO', '1º Grau'), ('SEGUNDO', '2º Grau'), ('SUPERIOR', 'Tribunal Superior')]
    PERMISSAO_CHOICES = [('PUBLICO', 'Público para a Equipe'), ('RESTRITO', 'Restrito ao Responsável e Envolvidos')]
    RESULTADO_CHOICES = [('PROCEDENTE', 'Procedente'), ('IMPROCEDENTE', 'Improcedente'),
                         ('PARCIALMENTE', 'Parcialmente Procedente'), ('ACORDO', 'Acordo'),
                         ('EXTINTO', 'Extinto sem mérito')]

    # Bloco 1: Informações Básicas
    numero_processo = models.CharField("Número do Processo (CNJ)", max_length=25, blank=True, null=True,
                                       help_text="Formato: 0000000-00.0000.0.00.0000")
    tipo_acao = models.ForeignKey(TipoAcao, on_delete=models.SET_NULL, null=True, blank=True, related_name="processos",
                                  verbose_name="Classe Processual")
    descricao_caso = models.TextField("Assunto Principal / Descrição do Caso", blank=True, null=True)
    data_distribuicao = models.DateField("Data de Distribuição/Início", default=date.today)
    fase = models.CharField("Fase Processual Atual", max_length=30, choices=FASE_CHOICES, default='POSTULATORIA')
    status_processo = models.CharField("Situação do Processo", max_length=30, choices=STATUS_CHOICES, default='ATIVO')
    valor_causa = models.DecimalField("Valor da Causa", max_digits=12, decimal_places=2, null=True, blank=True)
    segredo_justica = models.BooleanField("Segredo de Justiça", default=False)
    justica_gratuita = models.BooleanField("Justiça Gratuita", default=False)
    prioridade_tramitacao = models.BooleanField("Prioridade na Tramitação", default=False)

    # Bloco 2: Dados do Juízo
    tribunal = models.CharField("Tribunal", max_length=10, choices=TRIBUNAL_CHOICES, blank=True, null=True)
    vara_comarca_orgao = models.CharField("Órgão Julgador (Vara/Comarca)", max_length=255, blank=True, null=True)
    juiz_responsavel = models.CharField("Juiz Responsável", max_length=200, blank=True, null=True)
    grau_jurisdicao = models.CharField("Grau de Jurisdição", max_length=20, choices=GRAU_CHOICES, default='PRIMEIRO')

    # Bloco 8: Informações Complementares
    observacoes_internas = models.TextField("Notas Internas (visível apenas para a equipe)", blank=True, null=True)
    numero_sei = models.CharField("Número SEI (se aplicável)", max_length=50, blank=True, null=True)
    numero_outro_sistema = models.CharField("Nº em Outro Sistema (PJe, etc.)", max_length=50, blank=True, null=True)
    link_acesso = models.URLField("Link do Processo Eletrônico", max_length=500, blank=True, null=True)

    # Bloco 9: Controle de Acesso
    advogado_responsavel = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                             related_name="processos_responsaveis", verbose_name="Usuário Responsável")
    advogados_envolvidos = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="processos_envolvidos",
                                                  blank=True, verbose_name="Outros Colaboradores")
    nivel_permissao = models.CharField("Nível de Permissão", max_length=20, choices=PERMISSAO_CHOICES,
                                       default='PUBLICO')

    # Bloco 11: Execução
    resultado = models.CharField("Resultado Final", max_length=20, choices=RESULTADO_CHOICES, blank=True, null=True)
    data_transito_em_julgado = models.DateField("Data do Trânsito em Julgado", blank=True, null=True)
    execucao_iniciada = models.BooleanField("Execução Iniciada?", default=False)
    valor_executado = models.DecimalField("Valor Total Executado", max_digits=12, decimal_places=2, null=True,
                                          blank=True)
    bloqueios_penhoras = models.JSONField("Bloqueios e Penhoras", blank=True, null=True,
                                          help_text="Estrutura para registrar bloqueios. Ex: [{'sistema': 'SISBAJUD', 'valor': 1500.00}]")

    history = HistoricalRecords()

    def __str__(self):
        autor_principal = self.partes.filter(tipo_participacao='AUTOR').first()
        if autor_principal: return f"Proc. {self.numero_processo or 'N/A'} - {autor_principal.cliente.nome_completo}"
        return f"Proc. {self.numero_processo or 'N/A'}"

    def get_absolute_url(self):
        return reverse('gestao:detalhe_processo', kwargs={'pk': self.pk})

    def get_polo_ativo_display(self): return ", ".join(
        [p.cliente.nome_completo for p in self.partes.filter(tipo_participacao='AUTOR')]) or "N/A"

    def get_polo_passivo_display(self): return ", ".join(
        [p.cliente.nome_completo for p in self.partes.filter(tipo_participacao='REU')]) or "N/A"


# --- Modelos Relacionados ao Processo (Tabelas Auxiliares) ---
class ParteProcesso(models.Model):
    """Tabela intermediária (N:N) que conecta Clientes a Processos, definindo seu papel."""
    TIPO_CHOICES = [('AUTOR', 'Polo Ativo'), ('REU', 'Polo Passivo'), ('TERCEIRO', 'Terceiro Interessado'),
                    ('VITIMA', 'Vítima'), ('TESTEMUNHA', 'Testemunha')]
    processo = models.ForeignKey(Processo, on_delete=models.CASCADE, related_name="partes")
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="participacoes")
    tipo_participacao = models.CharField("Tipo de Participação", max_length=20, choices=TIPO_CHOICES)

    is_cliente_do_processo = models.BooleanField(
        default=False,
        verbose_name="É o cliente que representamos neste processo?",
        help_text="Marque esta opção se esta parte for o cliente do escritório neste processo específico."
    )

    # --- ADICIONE ESTE CAMPO ---
    # ForeignKey('self') cria um relacionamento com o próprio modelo.
    # null=True, blank=True torna o campo opcional.
    # on_delete=models.SET_NULL para não apagar a parte se seu representante for removido.
    representado_por = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='representantes'
    )

    history = HistoricalRecords()

    class Meta: unique_together = ('processo', 'cliente'); ordering = ['tipo_participacao', 'cliente__nome_completo']

    def __str__(self): return f"{self.cliente.nome_completo} ({self.get_tipo_participacao_display()})"


class Documento(models.Model):
    """Armazena cada documento (peça processual, prova, etc.) vinculado a um processo."""
    TIPO_DOCUMENTO_CHOICES = [('PETICAO', 'Petição'), ('OFICIO', 'Ofício'), ('CONTRATO', 'Contrato'),
                              ('PROCURACAO', 'Procuração'), ('DECISAO', 'Decisão/Sentença'), ('PROVA', 'Prova'),
                              ('OUTRO', 'Outro')]
    processo = models.ForeignKey(Processo, on_delete=models.CASCADE, related_name="documentos")
    titulo = models.CharField("Título do Documento", max_length=255)
    tipo_documento = models.CharField("Tipo do Documento", max_length=20, choices=TIPO_DOCUMENTO_CHOICES,
                                      default='OUTRO')
    arquivo_upload = models.FileField("Arquivo", upload_to='processos/documentos/%Y/%m/', blank=True, null=True,
                                      help_text="Anexe o arquivo original (PDF, DOCX, etc).")
    data_protocolo = models.DateTimeField("Data e Hora do Protocolo", blank=True, null=True)
    conteudo = RichTextUploadingField("Conteúdo Editável",
                                      help_text="Use para gerar petições no sistema. Para documentos externos, use o campo de upload.",
                                      blank=True, null=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_modificacao = models.DateTimeField(auto_now=True)
    modelo_origem = models.ForeignKey(ModeloDocumento, on_delete=models.SET_NULL, null=True, blank=True,
                                      verbose_name="Gerado a partir do Modelo")
    history = HistoricalRecords()

    def __str__(self): return self.titulo

    def get_absolute_url(self): return reverse('editar_documento', kwargs={'pk': self.pk})

    class Meta: ordering = ['-data_criacao']


class Movimentacao(models.Model):
    """Registra cada andamento, prazo, tarefa ou audiência de um processo."""
    processo = models.ForeignKey(Processo, on_delete=models.CASCADE, related_name="movimentacoes")
    tipo_movimentacao = models.ForeignKey(TipoMovimentacao, on_delete=models.SET_NULL, null=True, blank=True)
    titulo = models.CharField(max_length=255)
    detalhes = models.TextField(blank=True, null=True)
    data_publicacao = models.DateField("Data do Ato/Publicação", null=True, blank=True)
    dias_prazo = models.PositiveIntegerField(null=True, blank=True, verbose_name="Dias de Prazo")
    data_prazo_final = models.DateField("Data do Prazo/Audiência", null=True, blank=True)
    responsavel = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="movimentacoes_responsaveis")
    status = models.CharField(max_length=20, choices=[('PENDENTE', 'Pendente'), ('EM_ANDAMENTO', 'Em Andamento'),
                                                      ('CONCLUIDA', 'Concluída')], default='PENDENTE')
    hora_prazo = models.TimeField("Horário", null=True, blank=True, help_text="Preencha apenas para audiências ou eventos com hora marcada.")
    data_criacao = models.DateTimeField(auto_now_add=True)

    link_referencia = models.URLField("Link de Referência", max_length=500, blank=True, null=True, help_text="Cole aqui o link para o andamento no sistema do tribunal, se houver.")

    history = HistoricalRecords()

    def __str__(self): return self.titulo

    def save(self, *args, **kwargs):
        if self.data_publicacao and self.dias_prazo and not self.data_prazo_final:
            self.data_prazo_final = self.data_publicacao + timedelta(days=self.dias_prazo)
        super().save(*args, **kwargs)


class Recurso(models.Model):
    """Tabela para registrar os recursos interpostos em um processo."""
    processo = models.ForeignKey(Processo, on_delete=models.CASCADE, related_name="recursos")
    TIPO_RECURSO_CHOICES = [('APELACAO', 'Apelação'), ('AGRAVO', 'Agravo de Instrumento'),
                            ('ESPECIAL', 'Recurso Especial'), ('EXTRAORDINARIO', 'Recurso Extraordinário'),
                            ('OUTRO', 'Outro')]
    tipo = models.CharField("Tipo de Recurso", max_length=20, choices=TIPO_RECURSO_CHOICES)
    data_interposicao = models.DateField("Data de Interposição")
    resultado = models.CharField("Resultado", max_length=100, blank=True, null=True)
    detalhes = models.TextField("Detalhes", blank=True, null=True)
    history = HistoricalRecords()

    class Meta: ordering = ['-data_interposicao']


class Incidente(models.Model):
    """Tabela para registrar incidentes processuais."""
    processo = models.ForeignKey(Processo, on_delete=models.CASCADE, related_name="incidentes")
    tipo = models.CharField("Tipo de Incidente", max_length=100)
    descricao = models.TextField("Descrição")
    STATUS_CHOICES = [('ABERTO', 'Aberto'), ('RESOLVIDO', 'Resolvido'), ('PENDENTE', 'Pendente')]
    status = models.CharField("Status", max_length=20, choices=STATUS_CHOICES, default='ABERTO')
    data_ocorrido = models.DateField("Data", default=date.today)
    history = HistoricalRecords()

    class Meta: ordering = ['-data_ocorrido']


# --- Outros Modelos do Sistema (mantidos para integridade) ---
class Servico(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="servicos")
    tipo_servico = models.ForeignKey(TipoServico, on_delete=models.PROTECT, related_name="servicos")
    responsavel = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="servicos_responsaveis", verbose_name="Responsável pelo Serviço")
    descricao = models.CharField(max_length=255, verbose_name="Descrição Detalhada do Serviço")
    codigo_servico_municipal = models.CharField(max_length=10, blank=True, null=True, verbose_name="Cód. do Serviço Municipal (LC 116/03)", help_text="Ex: 01.07, 14.01, etc.")
    data_inicio = models.DateField(default=date.today)
    prazo = models.DateField(null=True, blank=True, verbose_name="Prazo de Conclusão")
    concluido = models.BooleanField(default=False, verbose_name="Concluído")
    data_encerramento = models.DateField(null=True, blank=True, verbose_name="Data de Encerramento (para recorrentes)")
    recorrente = models.BooleanField(default=False, verbose_name="É um serviço recorrente (mensal)?")
    ativo = models.BooleanField(default=True)
    history = HistoricalRecords()

    def __str__(self): return f"{self.tipo_servico} - {self.cliente}"

    def get_absolute_url(self):
        return reverse('gestao:detalhe_servico', kwargs={'pk': self.pk})

    class Meta: ordering = ['-data_inicio']


class MovimentacaoServico(models.Model):
    servico = models.ForeignKey(Servico, on_delete=models.CASCADE, related_name="movimentacoes")
    titulo = models.CharField(max_length=255, verbose_name="Título / Resumo da Atividade")
    detalhes = models.TextField(blank=True, null=True)
    data_atividade = models.DateField(default=date.today)
    responsavel = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="movimentacoes_servicos_responsaveis")
    status = models.CharField(max_length=20, choices=[('PENDENTE', 'Pendente'), ('EM_ANDAMENTO', 'Em Andamento'),
                                                      ('CONCLUIDA', 'Concluída'), ('CANCELADA', 'Cancelada')],
                              default='PENDENTE')
    prazo_final = models.DateField(null=True, blank=True, verbose_name="Prazo Final")
    data_criacao = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()

    def __str__(self): return self.titulo


class ContratoHonorarios(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="contratos_honorarios_cliente")
    descricao = models.CharField(max_length=255, default="Honorários Contratuais")
    valor_pagamento_fixo = models.DecimalField(max_digits=12, decimal_places=2,
                                               verbose_name="Valor de Cada Pagamento (R$)")
    qtde_pagamentos_fixos = models.PositiveIntegerField(default=1, verbose_name="Qtde. de Pagamentos Fixos")
    data_primeiro_vencimento = models.DateField(verbose_name="Data do Primeiro Vencimento")
    percentual_exito = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
                                           verbose_name="Percentual de Êxito (%)")
    history = HistoricalRecords()

    def __str__(self):
        return f"Contrato: {self.descricao} - {self.content_object}"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new and self.qtde_pagamentos_fixos > 0 and self.valor_pagamento_fixo > 0:
            for i in range(self.qtde_pagamentos_fixos):
                lancamento_data = {'cliente': self.cliente, 'contrato': self,
                                   'descricao': f"{self.descricao} - Parcela {i + 1}/{self.qtde_pagamentos_fixos}",
                                   'valor': self.valor_pagamento_fixo,
                                   'data_vencimento': self.data_primeiro_vencimento + relativedelta(months=i)}
                if isinstance(self.content_object, Processo):
                    lancamento_data['processo'] = self.content_object
                elif isinstance(self.content_object, Servico):
                    lancamento_data['servico'] = self.content_object
                LancamentoFinanceiro.objects.create(**lancamento_data)


class LancamentoFinanceiro(models.Model):
    TIPO_CHOICES = [('RECEITA', 'Receita'), ('DESPESA', 'Despesa')]
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="lancamentos")
    processo = models.ForeignKey(Processo, on_delete=models.CASCADE, null=True, blank=True, related_name="lancamentos")
    servico = models.ForeignKey(Servico, on_delete=models.CASCADE, null=True, blank=True, related_name="lancamentos")
    contrato = models.ForeignKey(ContratoHonorarios, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="lancamentos")
    descricao = models.CharField(max_length=255)
    valor = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Valor Devido")
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, default='RECEITA')
    data_vencimento = models.DateField()

    CATEGORIA_CHOICES = [
        ('HONORARIOS', 'Honorários'),
        ('TAXAS', 'Taxas Judiciais/Administrativas'),
        ('CUSTAS', 'Custas Processuais'),
        ('ALUGUEL', 'Aluguel'),
        ('SALARIO', 'Salário'),
        ('OUTROS', 'Outros'),
        # Adicione mais categorias conforme necessário
    ]
    categoria = models.CharField(
        max_length=50,
        choices=CATEGORIA_CHOICES,
        default='OUTROS',
        blank=True,  # Permite que o campo seja vazio no banco de dados
        null=True  # Permite que o campo seja NULL no banco de dados
    )

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
    lancamento = models.ForeignKey(LancamentoFinanceiro, on_delete=models.CASCADE, related_name="pagamentos")
    data_pagamento = models.DateField(default=date.today)
    valor_pago = models.DecimalField(max_digits=12, decimal_places=2)
    forma_pagamento = models.CharField(max_length=100, blank=True, null=True)
    observacoes = models.TextField(blank=True, null=True)
    history = HistoricalRecords()

    def __str__(self): return f"Pagamento de R$ {self.valor_pago} para {self.lancamento.descricao}"


class CalculoJudicial(models.Model):
    processo = models.ForeignKey(Processo, on_delete=models.CASCADE, related_name="calculos")
    descricao = models.CharField(max_length=255, default="Cálculo Padrão")
    responsavel = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    data_calculo = models.DateTimeField(auto_now_add=True)
    valor_original = models.DecimalField(max_digits=12, decimal_places=2)
    data_inicio_correcao = models.DateField()
    data_fim_correcao = models.DateField()
    indice_correcao = models.CharField(max_length=10)
    correcao_pro_rata = models.BooleanField(default=False)
    juros_percentual = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True)
    juros_tipo = models.CharField(max_length=10, null=True, blank=True)
    juros_periodo = models.CharField(max_length=10, null=True, blank=True)
    juros_data_inicio = models.DateField(null=True, blank=True, verbose_name="Data de Início dos Juros")
    juros_data_fim = models.DateField(null=True, blank=True, verbose_name="Data Final dos Juros")
    multa_percentual = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    multa_sobre_juros = models.BooleanField(default=False)
    honorarios_percentual = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    valor_corrigido = models.DecimalField(max_digits=15, decimal_places=2)
    valor_final = models.DecimalField(max_digits=15, decimal_places=2)
    memoria_calculo = models.JSONField()
    history = HistoricalRecords()

    def __str__(self): return f"{self.descricao} (R$ {self.valor_original})"

    class Meta: ordering = ['-data_calculo']


class EscritorioConfiguracao(models.Model):
    """
    Armazena as configurações globais do escritório.
    Este modelo é projetado para ter apenas uma única instância (Singleton).
    """
    nome_escritorio = models.CharField(max_length=255, verbose_name="Nome do Escritório")
    cnpj = models.CharField(max_length=18, blank=True, null=True, verbose_name="CNPJ")
    inscricao_municipal = models.CharField(max_length=20, blank=True, null=True, verbose_name="Inscrição Municipal")

    oab_principal = models.CharField(max_length=20, blank=True, null=True, verbose_name="Inscrição OAB Principal")

    # Endereço
    cep = models.CharField(max_length=9, blank=True, null=True, verbose_name="CEP")
    logradouro = models.CharField(max_length=255, blank=True, null=True, verbose_name="Logradouro")
    numero = models.CharField(max_length=20, blank=True, null=True, verbose_name="Número")
    complemento = models.CharField(max_length=100, blank=True, null=True, verbose_name="Complemento")
    bairro = models.CharField(max_length=100, blank=True, null=True, verbose_name="Bairro")
    cidade = models.CharField(max_length=100, blank=True, null=True, verbose_name="Cidade")
    estado = models.CharField(max_length=2, choices=Cliente.ESTADOS_BRASILEIROS_CHOICES, blank=True, null=True,
                              verbose_name="UF")

    # Contato
    telefone_contato = models.CharField(max_length=20, blank=True, null=True, verbose_name="Telefone de Contato")
    email_contato = models.EmailField(max_length=255, blank=True, null=True, verbose_name="E-mail de Contato")

    def __str__(self):
        return self.nome_escritorio

    def save(self, *args, **kwargs):
        # Garante que só exista uma instância deste modelo no banco de dados.
        self.pk = 1
        super(EscritorioConfiguracao, self).save(*args, **kwargs)

    class Meta:
        verbose_name = "Configuração do Escritório"
        verbose_name_plural = "Configurações do Escritório"


class NotaFiscalServico(models.Model):
    """Armazena o resultado da emissão de uma NFS-e para um serviço."""
    STATUS_CHOICES = [
        ('PROCESSANDO', 'Em Processamento'),
        ('ACEITO', 'Aceito'),
        ('ERRO', 'Erro'),
        ('CANCELADO', 'Cancelado'),
    ]
    servico = models.ForeignKey(Servico, on_delete=models.CASCADE, related_name="notas_fiscais")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PROCESSANDO')

    # Dados retornados pela prefeitura
    numero_nfse = models.CharField(max_length=15, blank=True, null=True, verbose_name="Número da NFS-e")
    codigo_verificacao = models.CharField(max_length=50, blank=True, null=True, verbose_name="Código de Verificação")
    data_emissao_nfse = models.DateTimeField(blank=True, null=True, verbose_name="Data de Emissão")

    # Para auditoria
    xml_enviado = models.TextField(blank=True, null=True)
    xml_recebido = models.TextField(blank=True, null=True)
    mensagem_retorno = models.TextField(blank=True, null=True)

    data_criacao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"NFS-e {self.numero_nfse or '(Aguardando)'} para {self.servico}"

    class Meta:
        verbose_name = "Nota Fiscal de Serviço"
        verbose_name_plural = "Notas Fiscais de Serviço"
