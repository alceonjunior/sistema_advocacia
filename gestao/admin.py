# gestao/admin.py

# --- Imports Necessários ---
from django.contrib import admin
from django.db.models import Sum
from django.urls import reverse
from django.utils.html import format_html
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

# Importa os modelos do seu aplicativo
from .models import (
    Processo, Cliente, Movimentacao, TipoAcao, LancamentoFinanceiro, Pagamento,
    Servico, TipoServico, ParteProcesso, Recurso, Incidente, UsuarioPerfil,
    AreaProcesso, TipoMovimentacao, ContratoHonorarios, CalculoJudicial,
    ModeloDocumento, Documento
)
# Importa o formulário customizado para ser usado no admin
from .forms import ParteProcessoForm


# --- Configuração do Admin para Usuários ---
class UsuarioPerfilInline(admin.StackedInline):
    model = UsuarioPerfil
    can_delete = False
    verbose_name_plural = 'Perfis de Usuário'


class UserAdmin(BaseUserAdmin):
    inlines = (UsuarioPerfilInline,)


admin.site.unregister(User)
admin.site.register(User, UserAdmin)


# --- Registros de Modelos de Suporte e Estrutura ---
@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nome_completo', 'cpf_cnpj', 'tipo_pessoa', 'email')
    search_fields = ('nome_completo', 'cpf_cnpj', 'email')
    list_filter = ('tipo_pessoa',)


@admin.register(AreaProcesso)
class AreaProcessoAdmin(admin.ModelAdmin):
    list_display = ('nome',)
    search_fields = ('nome',)


@admin.register(TipoAcao)
class TipoAcaoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'area')
    search_fields = ('nome', 'area__nome')
    list_filter = ('area',)
    autocomplete_fields = ['area']


@admin.register(TipoMovimentacao)
class TipoMovimentacaoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'sugestao_dias_prazo')
    search_fields = ('nome',)


@admin.register(TipoServico)
class TipoServicoAdmin(admin.ModelAdmin):
    list_display = ('nome',)
    search_fields = ('nome',)


# --- Configuração dos Inlines ---
class ParteProcessoInline(admin.TabularInline):
    model = ParteProcesso
    form = ParteProcessoForm
    extra = 1
    autocomplete_fields = ['cliente', 'representado_por']
    fk_name = 'processo'
    verbose_name = "Parte do Processo"
    verbose_name_plural = "Partes do Processo"


class MovimentacaoInline(admin.TabularInline):
    model = Movimentacao
    extra = 0
    autocomplete_fields = ['responsavel', 'tipo_movimentacao']
    ordering = ('-data_prazo_final',)


class RecursoInline(admin.TabularInline):
    model = Recurso
    extra = 0


class IncidenteInline(admin.TabularInline):
    model = Incidente
    extra = 0


# NOVO INLINE PARA EXIBIR AS PARCELAS DO CONTRATO
class LancamentoFinanceiroInline(admin.TabularInline):
    model = LancamentoFinanceiro
    verbose_name = "Parcela (Lançamento)"
    verbose_name_plural = "Parcelas e Lançamentos Gerados pelo Contrato"

    # Define os campos que aparecerão na tabela do inline
    fields = ('descricao', 'data_vencimento', 'valor', 'get_valor_pago', 'get_status_com_cor')
    readonly_fields = fields  # Torna todos os campos somente leitura

    # Impede a adição ou exclusão de parcelas por aqui, pois são controladas pelo contrato
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description='Status')
    def get_status_com_cor(self, obj):
        """Usa a propriedade 'status' do modelo e adiciona cores para melhor visualização."""
        status = obj.status
        if status == 'PAGO':
            cor = 'green'
            texto = 'Pago'
        elif status == 'ATRASADO':
            cor = 'red'
            texto = 'Atrasado'
        elif status == 'PARCIALMENTE_PAGO':
            cor = 'orange'
            texto = 'Parcial'
        else:  # A_PAGAR
            cor = 'black'
            texto = 'A Pagar'
        return format_html(f'<b style="color: {cor};">{texto}</b>')

    @admin.display(description='Valor Pago')
    def get_valor_pago(self, obj):
        """Exibe o valor pago formatado como moeda, usando a propriedade do modelo."""
        valor = obj.valor_pago
        return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# --- Admin Principal do Processo ---
@admin.register(Processo)
class ProcessoAdmin(admin.ModelAdmin):
    list_display = ('numero_processo', 'get_polo_ativo_display', 'tipo_acao', 'status_processo', 'advogado_responsavel',
                    'get_valor_total_pago')
    list_filter = ('status_processo', 'fase', 'tribunal', 'advogado_responsavel')
    search_fields = ('numero_processo', 'partes__cliente__nome_completo', 'tipo_acao__nome', 'descricao_caso')
    autocomplete_fields = ['tipo_acao', 'advogado_responsavel', 'advogados_envolvidos']
    inlines = [ParteProcessoInline, MovimentacaoInline, RecursoInline, IncidenteInline]
    readonly_fields = ('display_pagamentos',)
    fieldsets = (
        ('Informações Básicas',
         {'fields': ('numero_processo', 'tipo_acao', 'descricao_caso', 'data_distribuicao', 'valor_causa')}),
        ('Status e Fase', {'fields': ('status_processo', 'fase')}),
        ('Visão Financeira', {'fields': ('display_pagamentos',), 'classes': ('collapse',)}),
        ('Dados do Juízo', {'fields': ('tribunal', 'grau_jurisdicao', 'vara_comarca_orgao', 'juiz_responsavel')}),
        ('Informações Adicionais', {'fields': (
        'segredo_justica', 'justica_gratuita', 'prioridade_tramitacao', 'link_acesso', 'numero_sei',
        'numero_outro_sistema', 'observacoes_internas')}),
        ('Responsáveis e Permissões', {'fields': ('advogado_responsavel', 'advogados_envolvidos', 'nivel_permissao')}),
        ('Resultado e Execução', {'classes': ('collapse',), 'fields': (
        'resultado', 'data_transito_em_julgado', 'execucao_iniciada', 'valor_executado', 'bloqueios_penhoras')}),
    )

    # ... (métodos do ProcessoAdmin - get_polo_ativo_display, get_valor_total_pago, display_pagamentos) ...
    @admin.display(description='Polo Ativo')
    def get_polo_ativo_display(self, obj):
        autores = obj.partes.filter(tipo_participacao='AUTOR')
        return ", ".join([p.cliente.nome_completo for p in autores])

    @admin.display(description='Valor Total Pago')
    def get_valor_total_pago(self, obj):
        total_pago = obj.lancamentos.aggregate(total=Sum('pagamentos__valor_pago'))['total']
        if total_pago is None:
            return "R$ 0,00"
        return f"R$ {total_pago:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    @admin.display(description='Histórico de Pagamentos')
    def display_pagamentos(self, obj):
        pagamentos = Pagamento.objects.filter(lancamento__processo=obj).order_by('-data_pagamento')
        if not pagamentos.exists():
            return "Nenhum pagamento registrado para este processo."
        html = """<table style="width:100%; border-collapse: collapse;">...</table>"""  # Conteúdo omitido para brevidade
        # (O código completo para esta tabela está mantido no seu arquivo)
        return format_html(html)


# --- Admin de Partes do Processo ---
@admin.register(ParteProcesso)
class ParteProcessoAdmin(admin.ModelAdmin):
    form = ParteProcessoForm
    list_display = ('processo', 'cliente', 'tipo_participacao', 'representado_por')
    search_fields = ('cliente__nome_completo', 'processo__numero_processo')
    list_filter = ('tipo_participacao',)
    autocomplete_fields = ['processo', 'cliente', 'representado_por']


# --- Registros dos Outros Modelos do Sistema ---
@admin.register(Servico)
class ServicoAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'cliente', 'tipo_servico', 'recorrente', 'concluido', 'ativo')
    list_filter = ('tipo_servico', 'recorrente', 'concluido', 'ativo')
    search_fields = ('descricao', 'cliente__nome_completo')
    autocomplete_fields = ['cliente', 'tipo_servico', 'responsavel']


# AJUSTE APLICADO AQUI
@admin.register(ContratoHonorarios)
class ContratoHonorariosAdmin(admin.ModelAdmin):
    list_display = ('content_object', 'cliente', 'descricao', 'valor_pagamento_fixo', 'qtde_pagamentos_fixos')
    search_fields = ('descricao', 'cliente__nome_completo')
    autocomplete_fields = ['cliente']
    # Adiciona o inline para exibir as parcelas na página de edição do contrato
    inlines = [LancamentoFinanceiroInline]


@admin.register(LancamentoFinanceiro)
class LancamentoFinanceiroAdmin(admin.ModelAdmin):
    list_display = ('descricao', 'processo', 'servico', 'valor', 'data_vencimento', 'status', 'tipo')
    list_filter = ('tipo', 'data_vencimento')
    readonly_fields = ('valor_pago', 'saldo_devedor', 'status')
    search_fields = ('descricao', 'processo__numero_processo', 'servico__descricao', 'cliente__nome_completo')
    autocomplete_fields = ['processo', 'contrato', 'cliente', 'servico']


@admin.register(Pagamento)
class PagamentoAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'lancamento', 'data_pagamento', 'valor_pago')
    autocomplete_fields = ['lancamento']
    search_fields = ('lancamento__descricao', 'lancamento__cliente__nome_completo')


@admin.register(CalculoJudicial)
class CalculoJudicialAdmin(admin.ModelAdmin):
    list_display = ('descricao', 'processo', 'valor_final', 'responsavel', 'data_calculo')
    readonly_fields = ('data_calculo', 'responsavel', 'valor_corrigido', 'valor_final', 'memoria_calculo')
    autocomplete_fields = ['processo', 'responsavel']


@admin.register(ModeloDocumento)
class ModeloDocumentoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'data_modificacao')
    search_fields = ('titulo', 'conteudo')


@admin.register(Documento)
class DocumentoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'processo', 'tipo_documento', 'data_modificacao')
    list_filter = ('tipo_documento',)
    search_fields = ('titulo', 'processo__numero_processo')
    autocomplete_fields = ['processo']