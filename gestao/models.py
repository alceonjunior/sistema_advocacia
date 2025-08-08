# gestao/models.py
import re
from datetime import date, timedelta
from decimal import Decimal

from ckeditor_uploader.fields import RichTextUploadingField
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from simple_history.models import HistoricalRecords
from .encoders import DecimalEncoder


# ==============================================================================
# SEÇÃO 1: MODELOS DE BASE (ENTIDADES PRINCIPAIS)
# ==============================================================================

class Cliente(models.Model):
    """Representa um cliente do escritório, seja pessoa física ou jurídica."""
    TIPO_PESSOA_CHOICES = [('PF', 'Pessoa Física'), ('PJ', 'Pessoa Jurídica')]
    ESTADO_CIVIL_CHOICES = [('SOLTEIRO', 'Solteiro(a)'), ('CASADO', 'Casado(a)'), ('DIVORCIADO', 'Divorciado(a)'),
                            ('VIUVO', 'Viúvo(a)'), ('UNIAO_ESTAVEL', 'União Estável')]
    ESTADOS_BRASILEIROS_CHOICES = [
        ('AC', 'Acre'), ('AL', 'Alagoas'), ('AP', 'Amapá'), ('AM', 'Amazonas'), ('BA', 'Bahia'), ('CE', 'Ceará'),
        ('DF', 'Distrito Federal'), ('ES', 'Espírito Santo'),
        ('GO', 'Goiás'), ('MA', 'Maranhão'), ('MT', 'Mato Grosso'), ('MS', 'Mato Grosso do Sul'),
        ('MG', 'Minas Gerais'), ('PA', 'Pará'), ('PB', 'Paraíba'), ('PR', 'Paraná'),
        ('PE', 'Pernambuco'), ('PI', 'Piauí'), ('RJ', 'Rio de Janeiro'), ('RN', 'Rio Grande do Norte'),
        ('RS', 'Rio Grande do Sul'), ('RO', 'Rondônia'), ('RR', 'Roraima'), ('SC', 'Santa Catarina'),
        ('SP', 'São Paulo'), ('SE', 'Sergipe'), ('TO', 'Tocantins')
    ]

    nome_completo = models.CharField(max_length=255, verbose_name="Nome Completo / Razão Social")
    tipo_pessoa = models.CharField(max_length=2, choices=TIPO_PESSOA_CHOICES, default='PF',
                                   verbose_name="Tipo de Pessoa")
    cpf_cnpj = models.CharField(max_length=18, unique=True, blank=True, null=True, verbose_name="CPF/CNPJ")
    email = models.EmailField(max_length=255, blank=True, null=True, verbose_name="E-mail")
    telefone_principal = models.CharField(max_length=20, blank=True, null=True, verbose_name="Telefone Principal")
    data_nascimento = models.DateField(blank=True, null=True, verbose_name="Data de Nascimento")
    nacionalidade = models.CharField(max_length=100, blank=True, null=True, default="Brasileiro(a)",
                                     verbose_name="Nacionalidade")
    estado_civil = models.CharField(max_length=20, choices=ESTADO_CIVIL_CHOICES, blank=True, null=True,
                                    verbose_name="Estado Civil")
    profissao = models.CharField(max_length=255, blank=True, null=True, verbose_name="Profissão")
    cep = models.CharField(max_length=9, blank=True, null=True, verbose_name="CEP")
    logradouro = models.CharField(max_length=255, blank=True, null=True, verbose_name="Logradouro (Rua, Av.)")
    numero = models.CharField(max_length=20, blank=True, null=True, verbose_name="Número")
    complemento = models.CharField(max_length=100, blank=True, null=True, verbose_name="Complemento")
    bairro = models.CharField(max_length=100, blank=True, null=True, verbose_name="Bairro")
    cidade = models.CharField(max_length=100, blank=True, null=True, verbose_name="Cidade")
    estado = models.CharField(max_length=2, choices=ESTADOS_BRASILEIROS_CHOICES, blank=True, null=True,
                              verbose_name="Estado (UF)")
    representante_legal = models.CharField(max_length=255, blank=True, null=True,
                                           verbose_name="Nome do Representante Legal")
    cpf_representante_legal = models.CharField(max_length=14, blank=True, null=True,
                                               verbose_name="CPF do Representante")
    is_cliente = models.BooleanField(default=True, verbose_name="É um cliente?")
    data_cadastro = models.DateField(auto_now_add=True, verbose_name="Data de Cadastro", editable=False, null=True,
                                     db_index=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ['nome_completo']

    def get_absolute_url(self):
        # --- CORREÇÃO APLICADA ---
        # Padronizado para 'detalhe_cliente'. Verifique se este é o nome da sua rota em urls.py
        return reverse('gestao:detalhe_cliente', kwargs={'pk': self.pk})

    def __str__(self):
        return self.nome_completo

    @property
    def qualificacao(self):
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
        else:
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

    @property
    def telefone_principal_digits(self):
        if not self.telefone_principal:
            return ""
        return re.sub(r'\D', '', str(self.telefone_principal))


class UsuarioPerfil(models.Model):
    """Estende o modelo de usuário padrão do Django com informações específicas do escritório."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="perfil")
    cpf = models.CharField(max_length=14, null=True, blank=True, verbose_name="CPF")
    oab = models.CharField(max_length=20, null=True, blank=True, verbose_name="Nº da OAB (ex: 12345/PR)")
    telefone = models.CharField(max_length=20, null=True, blank=True, verbose_name="Telefone")
    data_admissao = models.DateField(null=True, blank=True, verbose_name="Data de Admissão")
    foto = models.ImageField(upload_to='fotos_perfil/', null=True, blank=True, verbose_name="Foto de Perfil")
    cargo = models.CharField(max_length=20, choices=[('ADVOGADO', 'Advogado(a)'), ('ESTAGIARIO', 'Estagiário(a)')],
                             null=True, blank=True)
    history = HistoricalRecords()

    def __str__(self):
        return self.user.username


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def criar_ou_atualizar_perfil_usuario(sender, instance, created, **kwargs):
    """Cria um perfil de usuário automaticamente toda vez que um novo usuário é criado."""
    if created:
        UsuarioPerfil.objects.create(user=instance)
    instance.perfil.save()


# ==============================================================================
# SEÇÃO 2: MODELOS DE SUPORTE E CATEGORIZAÇÃO
# ==============================================================================

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


# ==============================================================================
# SEÇÃO 3: MODELOS OPERACIONAIS PRINCIPAIS
# ==============================================================================

class Processo(models.Model):
    """Modelo central que consolida todas as informações de um caso judicial."""
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
    tribunal = models.CharField("Tribunal", max_length=10, choices=TRIBUNAL_CHOICES, blank=True, null=True)
    vara_comarca_orgao = models.CharField("Órgão Julgador (Vara/Comarca)", max_length=255, blank=True, null=True)
    juiz_responsavel = models.CharField("Juiz Responsável", max_length=200, blank=True, null=True)
    grau_jurisdicao = models.CharField("Grau de Jurisdição", max_length=20, choices=GRAU_CHOICES, default='PRIMEIRO')
    observacoes_internas = models.TextField("Notas Internas (visível apenas para a equipe)", blank=True, null=True)
    numero_sei = models.CharField("Número SEI (se aplicável)", max_length=50, blank=True, null=True)
    numero_outro_sistema = models.CharField("Nº em Outro Sistema (PJe, etc.)", max_length=50, blank=True, null=True)
    link_acesso = models.URLField("Link do Processo Eletrônico", max_length=500, blank=True, null=True)
    advogado_responsavel = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                             related_name="processos_responsaveis", verbose_name="Usuário Responsável")
    advogados_envolvidos = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="processos_envolvidos",
                                                  blank=True, verbose_name="Outros Colaboradores")
    nivel_permissao = models.CharField("Nível de Permissão", max_length=20, choices=PERMISSAO_CHOICES,
                                       default='PUBLICO')
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
        # Este método já parecia correto, mantido para consistência.
        return reverse('gestao:detalhe_processo', kwargs={'pk': self.pk})

    def get_polo_ativo_display(self):
        return ", ".join([p.cliente.nome_completo for p in self.partes.filter(tipo_participacao='AUTOR')]) or "N/A"

    def get_polo_passivo_display(self):
        return ", ".join([p.cliente.nome_completo for p in self.partes.filter(tipo_participacao='REU')]) or "N/A"

    def get_cliente_principal(self):
        """
        Retorna o objeto Cliente marcado como 'is_cliente_do_processo=True'
        associado a este processo. Retorna None se não houver um.
        Prioriza o campo is_cliente_do_processo. Se não houver, busca o primeiro autor.
        """
        # Tenta encontrar o cliente marcado explicitamente como principal
        cliente_principal = self.partes.filter(is_cliente_do_processo=True).first()
        if cliente_principal:
            return cliente_principal.cliente
        # Se não houver um marcado como principal, retorna o primeiro autor
        polo_ativo = self.partes.filter(tipo_participacao='AUTOR').first()
        if polo_ativo:
            return polo_ativo.cliente
        return None

    def get_cliente_principal_display(self):
        """
        Retorna o nome completo do cliente principal ou uma string padrão
        se o cliente principal não estiver definido.
        """
        cliente = self.get_cliente_principal()  # Agora usa o método que retorna o objeto
        return cliente.nome_completo if cliente else "Cliente não definido"


class Servico(models.Model):
    """Modelo para serviços extrajudiciais."""
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="servicos")
    tipo_servico = models.ForeignKey(TipoServico, on_delete=models.PROTECT, related_name="servicos")
    responsavel = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="servicos_responsaveis", verbose_name="Responsável pelo Serviço")
    descricao = models.CharField(max_length=255, verbose_name="Descrição Detalhada do Serviço")
    codigo_servico_municipal = models.CharField(max_length=10, blank=True, null=True,
                                                verbose_name="Cód. do Serviço Municipal (LC 116/03)",
                                                help_text="Ex: 01.07, 14.01, etc.")
    data_inicio = models.DateField(default=date.today)
    prazo = models.DateField(null=True, blank=True, verbose_name="Prazo de Conclusão")
    concluido = models.BooleanField(default=False, verbose_name="Concluído")
    data_encerramento = models.DateField(null=True, blank=True, verbose_name="Data de Encerramento (para recorrentes)")
    recorrente = models.BooleanField(default=False, verbose_name="É um serviço recorrente (mensal)?")
    ativo = models.BooleanField(default=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ['-data_inicio']

    def __str__(self):
        return f"{self.tipo_servico} - {self.cliente}"

    def get_absolute_url(self):
        # Este método já parecia correto, mantido para consistência.
        return reverse('gestao:detalhe_servico', kwargs={'pk': self.pk})


# ==============================================================================
# SEÇÃO 4: MODELOS DEPENDENTES (Filhos de Processo e Serviço)
# ==============================================================================

class TipoMovimentacao(models.Model):
    """Define os tipos de andamentos, agora com lógica aprimorada para prazos."""
    TIPO_CONTAGEM_CHOICES = [('UTEIS', 'Dias Úteis'), ('CORRIDOS', 'Dias Corridos')]

    nome = models.CharField(max_length=200, unique=True, verbose_name="Nome do Tipo de Movimentação")
    sugestao_dias_prazo = models.PositiveIntegerField(null=True, blank=True, verbose_name="Sugestão de Dias para Prazo")
    tipo_contagem_prazo = models.CharField(max_length=10, choices=TIPO_CONTAGEM_CHOICES, default='UTEIS',
                                           verbose_name="Tipo de Contagem do Prazo",
                                           help_text="Define se o prazo deve ser contado em dias úteis ou corridos.")
    fase_processual_sugerida = models.CharField(max_length=30, choices=Processo.FASE_CHOICES, null=True, blank=True,
                                                verbose_name="Fase Processual Padrão",
                                                help_text="Associe este tipo de movimentação a uma fase do processo para facilitar a seleção.")
    dias_antecedencia_lembrete = models.PositiveIntegerField(null=True, blank=True,
                                                             verbose_name="Antecedência para Lembrete (dias)",
                                                             help_text="Ex: 3. O sistema poderá usar este valor para criar um lembrete 3 dias antes do prazo final.")
    favorito = models.BooleanField(default=False, verbose_name="Favorito",
                                   help_text="Marque para que este tipo apareça no topo das listas de seleção.")
    history = HistoricalRecords()

    class Meta:
        ordering = ['-favorito', 'nome']

    def __str__(self):
        return self.nome


class ParteProcesso(models.Model):
    """Tabela intermediária que conecta Clientes a Processos, definindo seu papel."""
    TIPO_CHOICES = [('AUTOR', 'Polo Ativo'), ('REU', 'Polo Passivo'), ('TERCEIRO', 'Terceiro Interessado'),
                    ('VITIMA', 'Vítima'), ('TESTEMUNHA', 'Testemunha')]
    processo = models.ForeignKey(Processo, on_delete=models.CASCADE, related_name="partes")
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="participacoes")
    tipo_participacao = models.CharField("Tipo de Participação", max_length=20, choices=TIPO_CHOICES)
    is_cliente_do_processo = models.BooleanField(default=False,
                                                 verbose_name="É o cliente que representamos neste processo?",
                                                 help_text="Marque esta opção se esta parte for o cliente do escritório neste processo específico.")
    representado_por = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name='representantes')
    history = HistoricalRecords()

    class Meta:
        unique_together = ('processo', 'cliente')
        ordering = ['tipo_participacao', 'cliente__nome_completo']

    def __str__(self):
        return f"{self.cliente.nome_completo} ({self.get_tipo_participacao_display()})"


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

    class Meta:
        ordering = ['-data_criacao']

    def __str__(self):
        return self.titulo


class Movimentacao(models.Model):
    """Registra cada andamento, prazo, tarefa ou audiência de um processo."""
    processo = models.ForeignKey(Processo, on_delete=models.CASCADE, related_name="movimentacoes")
    tipo_movimentacao = models.ForeignKey(TipoMovimentacao, on_delete=models.SET_NULL, null=True, blank=True)
    titulo = models.CharField(max_length=255)
    detalhes = models.TextField(blank=True, null=True)
    data_publicacao = models.DateField("Data da Publicação", null=True, blank=True)
    data_intimacao = models.DateField("Data da Intimação", null=True, blank=True)
    data_inicio_prazo = models.DateField("Primeiro Dia do Prazo", null=True, blank=True)
    data_prazo_final = models.DateField("Data do Prazo Final", null=True, blank=True)
    dias_prazo = models.PositiveIntegerField(null=True, blank=True, verbose_name="Dias de Prazo (manual)")
    responsavel = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="movimentacoes_responsaveis")
    status = models.CharField(max_length=20, choices=[('PENDENTE', 'Pendente'), ('EM_ANDAMENTO', 'Em Andamento'),
                                                      ('CONCLUIDA', 'Concluída')], default='PENDENTE')
    hora_prazo = models.TimeField("Horário", null=True, blank=True,
                                  help_text="Preencha apenas para audiências ou eventos com hora marcada.")
    data_criacao = models.DateTimeField(auto_now_add=True)
    link_referencia = models.URLField("Link de Referência", max_length=500, blank=True, null=True,
                                      help_text="Cole aqui o link para o andamento no sistema do tribunal, se houver.")
    history = HistoricalRecords()

    def __str__(self):
        return self.titulo


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

    class Meta:
        ordering = ['-data_interposicao']


class Incidente(models.Model):
    """Tabela para registrar incidentes processuais."""
    processo = models.ForeignKey(Processo, on_delete=models.CASCADE, related_name="incidentes")
    tipo = models.CharField("Tipo de Incidente", max_length=100)
    descricao = models.TextField("Descrição")
    STATUS_CHOICES = [('ABERTO', 'Aberto'), ('RESOLVIDO', 'Resolvido'), ('PENDENTE', 'Pendente')]
    status = models.CharField("Status", max_length=20, choices=STATUS_CHOICES, default='ABERTO')
    data_ocorrido = models.DateField("Data", default=date.today)
    history = HistoricalRecords()

    class Meta:
        ordering = ['-data_ocorrido']


class MovimentacaoServico(models.Model):
    """Registra cada andamento ou tarefa de um serviço extrajudicial."""
    servico = models.ForeignKey(Servico, on_delete=models.CASCADE,
                                related_name="movimentacoes_servico")  # Nome do related_name ajustado para evitar conflito
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

    def __str__(self):
        return self.titulo


# ==============================================================================
# SEÇÃO 5: MODELOS FINANCEIROS
# ==============================================================================

class ContratoHonorarios(models.Model):
    """Define um contrato financeiro, que pode estar ligado a um Processo ou Serviço."""
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
    """Representa uma única conta a pagar ou a receber."""
    TIPO_CHOICES = [('RECEITA', 'Receita'), ('DESPESA', 'Despesa')]
    CATEGORIA_CHOICES = [('HONORARIOS', 'Honorários'), ('TAXAS', 'Taxas Judiciais/Administrativas'),
                         ('CUSTAS', 'Custas Processuais'), ('ALUGUEL', 'Aluguel'), ('SALARIO', 'Salário'),
                         ('OUTROS', 'Outros')]

    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="lancamentos", null=True,
                                blank=True)  # Cliente é opcional
    processo = models.ForeignKey(Processo, on_delete=models.CASCADE, null=True, blank=True, related_name="lancamentos")
    servico = models.ForeignKey(Servico, on_delete=models.CASCADE, null=True, blank=True, related_name="lancamentos")
    contrato = models.ForeignKey(ContratoHonorarios, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="lancamentos")
    descricao = models.CharField(max_length=255)
    valor = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Valor Devido")
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, default='RECEITA')
    data_vencimento = models.DateField()
    categoria = models.CharField(max_length=50, choices=CATEGORIA_CHOICES, default='OUTROS', blank=True, null=True)
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
    """Registra um pagamento efetuado para um LancamentoFinanceiro."""
    lancamento = models.ForeignKey(LancamentoFinanceiro, on_delete=models.CASCADE, related_name="pagamentos")
    data_pagamento = models.DateField(default=date.today)
    valor_pago = models.DecimalField(max_digits=12, decimal_places=2)
    forma_pagamento = models.CharField(max_length=100, blank=True, null=True)
    observacoes = models.TextField(blank=True, null=True)
    history = HistoricalRecords()

    def __str__(self):
        return f"Pagamento de R$ {self.valor_pago} para {self.lancamento.descricao}"


# ==============================================================================
# SEÇÃO 6: MODELOS DE FERRAMENTAS E CONFIGURAÇÕES
# ==============================================================================

class CalculoJudicial(models.Model):
    """
    Modelo container para um cálculo judicial completo, que pode consistir em múltiplas fases.
    """
    processo = models.ForeignKey('Processo', on_delete=models.CASCADE, related_name='calculos')
    descricao = models.CharField(max_length=255, verbose_name="Descrição do Cálculo")
    valor_original = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Valor Original da Causa")

    valor_final_calculado = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        default=None,
        verbose_name="Valor Final Calculado"
    )

    # --- CORREÇÃO APLICADA AQUI ---
    # Adicionamos o 'encoder=DecimalEncoder' para que o Django saiba como
    # salvar os números decimais do resultado do cálculo no banco de dados.
    memoria_calculo_json = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Memória de Cálculo (JSON)",
        encoder=DecimalEncoder
    )

    responsavel = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    data_calculo = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Cálculo Judicial"
        verbose_name_plural = "Cálculos Judiciais"
        ordering = ['-data_calculo']

    def __str__(self):
        return self.descricao or f"Cálculo {self.pk} do processo {self.processo.numero_processo}"


class FaseCalculo(models.Model):
    """
    Representa uma fase (período) específica dentro de um Cálculo Judicial.
    """
    INDICE_CHOICES = [('IPCA', 'IPCA (IBGE)'), ('INPC', 'INPC (IBGE)'), ('IGP-M', 'IGP-M (FGV/BCB)'),
                      ('IGP-DI', 'IGP-DI (FGV/BCB)'), ('SELIC', 'Taxa Selic (BCB)'), ('TR', 'Taxa Referencial (BCB)')]
    JUROS_TIPO_CHOICES = [('SIMPLES', 'Simples'), ('COMPOSTO', 'Compostos')]

    calculo_judicial = models.ForeignKey(CalculoJudicial, on_delete=models.CASCADE, related_name='fases')
    ordem = models.PositiveIntegerField(default=1)
    data_inicio = models.DateField(verbose_name="Data de Início da Fase")
    data_fim = models.DateField(verbose_name="Data de Fim da Fase")
    indice = models.CharField(max_length=50, choices=INDICE_CHOICES, verbose_name="Índice de Correção")
    # --- AJUSTE DE CONSISTÊNCIA ---
    juros_taxa = models.DecimalField(max_digits=7, decimal_places=2, default=0, verbose_name="Taxa de Juros Mensal (%)")
    juros_tipo = models.CharField(max_length=20, choices=JUROS_TIPO_CHOICES, default='SIMPLES',
                                  verbose_name="Tipo de Juros")
    observacao = models.CharField(max_length=255, blank=True, null=True, verbose_name="Observação da Fase")

    class Meta:
        ordering = ['calculo_judicial', 'ordem']

    def __str__(self):
        return f"Fase {self.ordem} do Cálculo {self.calculo_judicial.id}"


class EscritorioConfiguracao(models.Model):
    """Armazena as configurações globais do escritório (Singleton)."""
    nome_escritorio = models.CharField(max_length=255, verbose_name="Nome do Escritório")
    cnpj = models.CharField(max_length=18, blank=True, null=True, verbose_name="CNPJ")
    inscricao_municipal = models.CharField(max_length=20, blank=True, null=True, verbose_name="Inscrição Municipal")
    oab_principal = models.CharField(max_length=20, blank=True, null=True, verbose_name="Inscrição OAB Principal")
    cep = models.CharField(max_length=9, blank=True, null=True, verbose_name="CEP")
    logradouro = models.CharField(max_length=255, blank=True, null=True, verbose_name="Logradouro")
    numero = models.CharField(max_length=20, blank=True, null=True, verbose_name="Número")
    complemento = models.CharField(max_length=100, blank=True, null=True, verbose_name="Complemento")
    bairro = models.CharField(max_length=100, blank=True, null=True, verbose_name="Bairro")
    cidade = models.CharField(max_length=100, blank=True, null=True, verbose_name="Cidade")
    estado = models.CharField(max_length=2, choices=Cliente.ESTADOS_BRASILEIROS_CHOICES, blank=True, null=True,
                              verbose_name="UF")
    telefone_contato = models.CharField(max_length=20, blank=True, null=True, verbose_name="Telefone de Contato")
    email_contato = models.EmailField(max_length=255, blank=True, null=True, verbose_name="E-mail de Contato")
    logo = models.ImageField(upload_to='logos/', blank=True, null=True)

    class Meta:
        verbose_name = "Configuração do Escritório"
        verbose_name_plural = "Configurações do Escritório"

    def __str__(self):
        return self.nome_escritorio

    def save(self, *args, **kwargs):
        self.pk = 1
        super(EscritorioConfiguracao, self).save(*args, **kwargs)


class NotaFiscalServico(models.Model):
    """Armazena o resultado da emissão de uma NFS-e para um serviço."""
    STATUS_CHOICES = [('PROCESSANDO', 'Em Processamento'), ('ACEITO', 'Aceito'), ('ERRO', 'Erro'),
                      ('CANCELADO', 'Cancelado')]
    servico = models.ForeignKey(Servico, on_delete=models.CASCADE, related_name="notas_fiscais")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PROCESSANDO')
    numero_nfse = models.CharField(max_length=15, blank=True, null=True, verbose_name="Número da NFS-e")
    codigo_verificacao = models.CharField(max_length=50, blank=True, null=True, verbose_name="Código de Verificação")
    data_emissao_nfse = models.DateTimeField(blank=True, null=True, verbose_name="Data de Emissão")
    xml_enviado = models.TextField(blank=True, null=True)
    xml_recebido = models.TextField(blank=True, null=True)
    mensagem_retorno = models.TextField(blank=True, null=True)
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Nota Fiscal de Serviço"
        verbose_name_plural = "Notas Fiscais de Serviço"

    def __str__(self):
        return f"NFS-e {self.numero_nfse or '(Aguardando)'} para {self.servico}"