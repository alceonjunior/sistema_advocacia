# gestao/urls.py

"""
Arquivo de configuração de URLs para o app 'gestao'.

Este arquivo mapeia as URLs (endereços web) para as views (funções Python)
que lidam com as requisições. A organização é feita em blocos lógicos
para facilitar a manutenção e a escalabilidade do sistema.
"""

# Importações do Django
from django.urls import path, include

# Importação das views locais
from . import views

# O app_name é crucial para criar um namespace para as URLs deste app.
# Isso evita conflitos com outros apps e permite referenciar as URLs de forma segura
# nos templates, como por exemplo: {% url 'gestao:home' %}.
app_name = 'gestao'

urlpatterns = [
    # ==============================================================================
    # CORE & AUTENTICAÇÃO
    # Rotas centrais do sistema, incluindo o painel principal e o fluxo de
    # autenticação (login, logout, redefinição de senha).
    # ==============================================================================
    # [CORREÇÃO] A rota raiz agora é nomeada 'home' para corresponder ao LOGIN_REDIRECT_URL
    # e aos links dos templates, resolvendo o erro NoReverseMatch.
    path('', views.dashboard, name='home'),

    # Rota explícita para o dashboard para manter a consistência e a compatibilidade.
    path('dashboard/', views.dashboard, name='dashboard'),

    # Inclui todas as URLs de autenticação padrão do Django (/login, /logout, etc.).
    # NOTA: O Django procura os templates de autenticação em uma pasta 'registration'.
    # Ex: 'registration/login.html'.
    path('accounts/', include('django.contrib.auth.urls')),

    # ==============================================================================
    # MÓDULO: CLIENTES E PESSOAS
    # Gerenciamento completo de clientes e pessoas (contrapartes, etc.).
    # ==============================================================================
    path('clientes/', views.lista_clientes, name='lista_clientes'),
    path('pessoas/', views.lista_pessoas, name='lista_pessoas'),
    path('clientes/adicionar/', views.adicionar_cliente_page, name='adicionar_cliente_page'),
    path('clientes/<int:pk>/', views.detalhe_cliente, name='detalhe_cliente'),
    path('clientes/<int:pk>/excluir/', views.excluir_cliente, name='excluir_cliente'),

    # ==============================================================================
    # MÓDULO: PROCESSOS
    # Gerenciamento de processos judiciais.
    # ==============================================================================
    path('processos/', views.lista_processos, name='lista_processos'),
    path('processo/adicionar/', views.adicionar_processo, name='adicionar_processo'),
    path('processo/<int:pk>/', views.detalhe_processo, name='detalhe_processo'),
    path('processo/<int:pk>/editar/', views.editar_processo, name='editar_processo'),
    path('processo/<int:pk>/arquivar/', views.arquivar_processo, name='arquivar_processo'),
    path('processo/<int:pk>/desarquivar/', views.desarquivar_processo, name='desarquivar_processo'),
    path('processo/<int:processo_pk>/gerenciar-partes/', views.gerenciar_partes, name='gerenciar_partes'),

    # ==============================================================================
    # MÓDULO: SERVIÇOS EXTRAJUDICIAIS
    # Gerenciamento de serviços que não são processos judiciais.
    # ==============================================================================
    path('servicos/', views.lista_servicos, name='lista_servicos'),
    path('servico/adicionar/', views.adicionar_servico_view, name='adicionar_servico'),
    path('servico/<int:pk>/', views.detalhe_servico, name='detalhe_servico'),
    path('servico/<int:pk>/editar/', views.editar_servico, name='editar_servico'),
    path('servico/<int:pk>/concluir/', views.concluir_servico, name='concluir_servico'),
    path('servico/<int:pk>/excluir/', views.excluir_servico, name='excluir_servico'),

    # ==============================================================================
    # MÓDULO: FINANCEIRO
    # Painel financeiro, contratos, pagamentos e despesas.
    # ==============================================================================
    path('financeiro/', views.painel_financeiro, name='painel_financeiro'),
    path('financeiro/despesas/', views.painel_despesas, name='painel_despesas'),
    path('financeiro/despesa/adicionar/', views.adicionar_despesa_wizard, name='adicionar_despesa_wizard'),

    path('processo/<int:processo_pk>/adicionar-contrato/', views.adicionar_contrato,
         name='adicionar_contrato_processo'),
    path('servico/<int:servico_pk>/adicionar-contrato/', views.adicionar_contrato, name='adicionar_contrato_servico'),
    path('pagamento/<int:pk>/editar/', views.editar_pagamento, name='editar_pagamento'),
    path('pagamento/<int:pk>/excluir/', views.excluir_pagamento, name='excluir_pagamento'),
    path('lancamento/<int:pk>/adicionar_pagamento/', views.adicionar_pagamento, name='adicionar_pagamento'),
    path('recibo/<int:pagamento_pk>/imprimir/', views.imprimir_recibo, name='imprimir_recibo'),

    # ==============================================================================
    # FERRAMENTAS E UTILITÁRIOS
    # Modelos de documentos, cálculos judiciais, importação, etc.
    # ==============================================================================
    path('modelos/', views.lista_modelos, name='lista_modelos'),
    path('modelos/adicionar/', views.adicionar_modelo, name='adicionar_modelo'),
    path('modelos/<int:pk>/editar/', views.editar_modelo, name='editar_modelo'),
    path('modelos/<int:pk>/excluir/', views.excluir_modelo, name='excluir_modelo'),
    path('processo/<int:processo_pk>/gerar-documento/<int:modelo_pk>/', views.gerar_documento, name='gerar_documento'),
    path('documento/<int:pk>/editar/', views.editar_documento, name='editar_documento'),
    path('documento/<int:pk>/imprimir/', views.imprimir_documento, name='imprimir_documento'),
    path('processo/<int:processo_pk>/calculos/', views.realizar_calculo, name='pagina_de_calculos'),
    path('processo/<int:processo_pk>/calculo/novo/', views.realizar_calculo, name='novo_calculo'),
    path('processo/<int:processo_pk>/calculos/<int:calculo_pk>/', views.realizar_calculo, name='carregar_calculo'),
    path('calculo/<int:calculo_pk>/atualizar-hoje/', views.atualizar_calculo_hoje, name='atualizar_calculo_hoje'),
    path('calculo/<int:calculo_pk>/excluir/', views.excluir_calculo, name='excluir_calculo'),
    path('processo/<int:processo_pk>/calculos/excluir-todos/', views.excluir_todos_calculos,
         name='excluir_todos_calculos'),
    path('importar/projudi/', views.importacao_projudi_view, name='importacao_projudi'),

    # ==============================================================================
    # CONFIGURAÇÕES
    # Gestão de usuários, permissões e cadastros auxiliares do sistema.
    # ==============================================================================
    path('configuracoes/', views.configuracoes, name='configuracoes'),
    path('configuracoes/usuarios/adicionar/', views.adicionar_usuario, name='adicionar_usuario'),
    path('configuracoes/usuarios/<int:user_id>/editar/', views.editar_usuario, name='editar_usuario'),
    path('configuracoes/usuarios/<int:user_id>/ativar-desativar/', views.ativar_desativar_usuario,
         name='ativar_desativar_usuario'),
    path('configuracoes/permissoes/salvar/<int:group_id>/', views.salvar_permissoes_grupo,
         name='salvar_permissoes_grupo'),

    # ==============================================================================
    # ENDPOINTS DE SERVIÇO (AJAX, JSON, PARTIALS)
    # Rotas que retornam dados (JSON) ou trechos de HTML (partials) para
    # interações dinâmicas na interface, sem recarregar a página inteira.
    # ==============================================================================
    # --- Geral ---
    path('ajax/global-search/', views.global_search, name='global_search'),
    path('dashboard/update-agenda/', views.update_agenda_partial, name='update_agenda_partial'),
    path('agenda/concluir/<str:tipo>/<int:pk>/', views.concluir_item_agenda_ajax, name='concluir_item_agenda_ajax'),

    # --- Clientes ---
    path('clientes/excluir-massa/', views.excluir_clientes_em_massa, name='excluir_clientes_em_massa'),
    path('clientes/salvar/', views.salvar_cliente, name='adicionar_cliente'),
    path('clientes/<int:pk>/salvar/', views.salvar_cliente, name='editar_cliente'),
    path('clientes/<int:pk>/json/', views.get_cliente_json, name='get_cliente_json'),
    path('clientes/json/all/', views.get_all_clients_json, name='get_all_clients_json'),
    path('cliente/adicionar/modal/', views.adicionar_cliente_modal, name='adicionar_cliente_modal'),

    # --- Processos e Movimentações ---
    path('processo/<int:processo_pk>/partial/partes/', views.detalhe_processo_partes_partial,
         name='detalhe_processo_partes_partial'),
    path('movimentacao/<int:pk>/editar/', views.editar_movimentacao, name='editar_movimentacao'),
    path('movimentacao/<int:pk>/excluir/', views.excluir_movimentacao, name='excluir_movimentacao'),
    path('movimentacao/<int:pk>/concluir/', views.concluir_movimentacao, name='concluir_movimentacao'),
    path('movimentacao/<int:pk>/json/', views.get_movimentacao_json, name='get_movimentacao_json'),
    path('movimentacao/<int:pk>/editar/ajax/', views.editar_movimentacao_ajax, name='editar_movimentacao_ajax'),

    # --- Serviços e Movimentações de Serviço ---
    path('servico/salvar/ajax/', views.salvar_servico_ajax, name='salvar_servico_ajax'),
    path('tiposervico/adicionar/modal/', views.adicionar_tipo_servico_modal, name='adicionar_tipo_servico_modal'),
    path('servico/<int:servico_pk>/andamento/ajax/adicionar/', views.adicionar_movimentacao_servico_ajax,
         name='adicionar_movimentacao_servico_ajax'),
    path('servico/<int:servico_pk>/andamento/partial/', views.atualizar_historico_servico_partial,
         name='atualizar_historico_servico_partial'),
    path('servico/<int:pk>/componentes-financeiros/', views.atualizar_componentes_financeiros_servico,
         name='atualizar_componentes_financeiros_servico'),
    path('servico/<int:pk>/json/', views.get_servico_json, name='get_servico_json'),
    path('servico/<int:pk>/editar/ajax/', views.editar_servico_ajax, name='editar_servico_ajax'),
    path('movimentacao-servico/<int:pk>/editar/', views.editar_movimentacao_servico,
         name='editar_movimentacao_servico'),
    path('movimentacao-servico/<int:pk>/excluir/', views.excluir_movimentacao_servico,
         name='excluir_movimentacao_servico'),
    path('movimentacao-servico/<int:pk>/concluir/', views.concluir_movimentacao_servico,
         name='concluir_movimentacao_servico'),
    path('movimentacao-servico/<int:pk>/json/', views.get_movimentacao_servico_json,
         name='get_movimentacao_servico_json'),
    path('movimentacao-servico/<int:pk>/editar/ajax/', views.editar_movimentacao_servico_ajax,
         name='editar_movimentacao_servico_ajax'),

    # --- Financeiro e NFS-e ---
    path('financeiro/lancamento/adicionar/ajax/', views.adicionar_lancamento_financeiro_ajax,
         name='adicionar_lancamento_financeiro_ajax'),
    path('ajax/tabela_financeira/<int:parent_pk>/<str:parent_type>/', views.atualizar_tabela_financeira_partial,
         name='atualizar_tabela_financeira_partial'),
    path('servico/<int:servico_pk>/emitir-nfse/', views.emitir_nfse_view, name='emitir_nfse'),

    # --- Importação Projudi ---
    path('importacao/projudi/analisar/', views.analisar_dados_projudi_ajax, name='analisar_dados_projudi_ajax'),

    # --- Configurações ---
    path('configuracoes/permissoes/grupo/<int:group_id>/', views.get_permissoes_grupo_ajax,
         name='get_permissoes_grupo_ajax'),
    path('configuracoes/cadastros/salvar/<str:modelo>/', views.salvar_cadastro_auxiliar_ajax,
         name='salvar_cadastro_auxiliar_ajax'),
    path('configuracoes/cadastros/salvar/<str:modelo>/<int:pk>/', views.salvar_cadastro_auxiliar_ajax,
         name='editar_cadastro_auxiliar_ajax'),
    path('configuracoes/cadastros/excluir/<str:modelo>/<int:pk>/', views.excluir_cadastro_auxiliar_ajax,
         name='excluir_cadastro_auxiliar_ajax'),

    # ==============================================================================
    # ROTA PARA A BUSCA GLOBAL (AJAX)
    # ==============================================================================
    path('ajax/global-search/', views.global_search, name='global_search'),

    path('importacao/projudi/', views.importacao_projudi_view, name='importacao_projudi'),

    path('importacao/projudi/analisar-ajax/', views.analisar_dados_projudi_ajax, name='analisar_dados_projudi_ajax'),
    path('importacao/projudi/confirmar/', views.confirmar_importacao_projudi, name='confirmar_importacao_projudi'),
    path('importacao/projudi/executar/', views.executar_importacao_projudi, name='executar_importacao_projudi'),

    path('calculos/novo/', views.calculo_wizard_view, name='calculo_novo'),
    path('calculos/novo/processo/<int:processo_pk>/', views.calculo_wizard_view, name='calculo_novo_com_processo'),

    # API para simulação e salvamento
    path('api/calculos/simular/', views.simular_calculo_api, name='api_simular_calculo'),

    # Exportação

    path('calculos/novo/', views.calculo_wizard_view, name='calculo_novo'),
    path('calculos/novo/processo/<int:processo_pk>/', views.calculo_wizard_view, name='calculo_novo_com_processo'),
    path('api/calculos/simular/', views.simular_calculo_api, name='api_simular_calculo'),
    #path('api/calculos/exportar/pdf/', views.exportar_calculo_pdf, name='exportar_calculo_pdf'),


]