# gestao/admin.py - VERSÃO DEFINITIVA E CONSOLIDADA

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import (
    Cliente, AreaProcesso, TipoAcao, Processo, UsuarioPerfil,
    TipoMovimentacao, Movimentacao,
    ContratoHonorarios, LancamentoFinanceiro,
    Servico, TipoServico, ParteProcesso,
    CalculoJudicial
)


# --- ADMINISTRAÇÃO DO PERFIL DE USUÁRIO ---
class UsuarioPerfilInline(admin.StackedInline):
    model = UsuarioPerfil
    can_delete = False
    verbose_name_plural = 'Perfis'

class UserAdmin(BaseUserAdmin):
    inlines = (UsuarioPerfilInline,)

admin.site.unregister(User)
admin.site.register(User, UserAdmin)


# --- REGISTROS DE GESTÃO (CLIENTE, ÁREAS, TIPOS) ---
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

@admin.register(Servico)
class ServicoAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'cliente', 'tipo_servico', 'recorrente', 'concluido', 'ativo')
    list_filter = ('tipo_servico', 'recorrente', 'concluido', 'ativo')
    search_fields = ('descricao', 'cliente__nome_completo')
    autocomplete_fields = ['cliente', 'tipo_servico']


# --- REGISTROS FINANCEIROS ---
class LancamentoFinanceiroInline(admin.TabularInline):
    model = LancamentoFinanceiro
    extra = 0
    readonly_fields = ('descricao', 'valor', 'data_vencimento', 'status', 'valor_pago')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

@admin.register(ContratoHonorarios)
class ContratoHonorariosAdmin(admin.ModelAdmin):
    list_display = ('content_object', 'cliente', 'descricao', 'valor_pagamento_fixo', 'qtde_pagamentos_fixos')
    list_filter = ('cliente', 'content_type')
    search_fields = ('descricao', 'cliente__nome_completo')
    autocomplete_fields = ['cliente']
    inlines = [LancamentoFinanceiroInline]

@admin.register(LancamentoFinanceiro)
class LancamentoFinanceiroAdmin(admin.ModelAdmin):
    list_display = ('descricao', 'processo', 'servico', 'valor', 'data_vencimento', 'status', 'tipo')
    list_filter = ('tipo', 'data_vencimento', 'processo', 'servico')
    readonly_fields = ('valor_pago', 'saldo_devedor', 'status')
    search_fields = ('descricao', 'processo__numero_processo', 'servico__descricao', 'cliente__nome_completo')
    autocomplete_fields = ['processo', 'contrato', 'cliente', 'servico']


# --- ADMINISTRAÇÃO DE PROCESSOS E PARTES ---
class ParteProcessoInline(admin.TabularInline):
    model = ParteProcesso
    extra = 1
    autocomplete_fields = ['cliente', 'representado_por']
    fk_name = 'processo'

class MovimentacaoInline(admin.TabularInline):
    model = Movimentacao
    extra = 1
    autocomplete_fields = ['responsavel', 'tipo_movimentacao']

@admin.register(Processo)
class ProcessoAdmin(admin.ModelAdmin):
    list_display = ('numero_processo', 'get_polo_ativo_display', 'tipo_acao', 'status_processo', 'advogado_responsavel')
    list_filter = ('status_processo', 'tipo_acao__area', 'advogado_responsavel')
    search_fields = ('numero_processo', 'partes__cliente__nome_completo', 'tipo_acao__nome')
    autocomplete_fields = ['tipo_acao', 'advogado_responsavel']
    inlines = [ParteProcessoInline, MovimentacaoInline]

    def get_polo_ativo_display(self, obj):
        autores = obj.partes.filter(tipo_participacao='AUTOR')
        return ", ".join([p.cliente.nome_completo for p in autores])
    get_polo_ativo_display.short_description = 'Polo Ativo'

@admin.register(ParteProcesso)
class ParteProcessoAdmin(admin.ModelAdmin):
    list_display = ('processo', 'cliente', 'tipo_participacao', 'representado_por')
    search_fields = ('cliente__nome_completo', 'processo__numero_processo')
    list_filter = ('tipo_participacao',)
    autocomplete_fields = ['processo', 'cliente', 'representado_por']


# --- ADMINISTRAÇÃO DE CÁLCULOS JUDICIAIS ---
@admin.register(CalculoJudicial)
class CalculoJudicialAdmin(admin.ModelAdmin):
    list_display = ('descricao', 'processo', 'valor_final', 'responsavel', 'data_calculo')
    list_filter = ('responsavel', 'data_inicio_correcao', 'indice_correcao')
    search_fields = ('descricao', 'processo__numero_processo', 'processo__partes__cliente__nome_completo')
    date_hierarchy = 'data_calculo'
    readonly_fields = ('data_calculo', 'responsavel', 'valor_corrigido', 'valor_final', 'memoria_calculo')

    fieldsets = (
        ('Informações Gerais', {'fields': ('processo', 'descricao', 'responsavel', 'data_calculo')}),
        ('Parâmetros do Cálculo (Originais)', {'fields': ('valor_original', 'data_inicio_correcao', 'data_fim_correcao', 'indice_correcao', 'correcao_pro_rata')}),
        ('Parâmetros de Juros, Multa e Honorários', {'fields': ('juros_percentual', 'juros_tipo', 'juros_periodo', 'juros_data_inicio', 'juros_data_fim', 'multa_percentual', 'multa_sobre_juros', 'honorarios_percentual')}),
        ('Resultados (Calculados)', {'classes': ('collapse',), 'fields': ('valor_corrigido', 'valor_final', 'memoria_calculo')}),
    )