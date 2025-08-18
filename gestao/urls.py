# gestao/urls.py
"""
Arquivo de roteamento (URLconf) para o aplicativo 'gestao'.

Este arquivo mapeia URLs para as views (funções ou classes) correspondentes
que lidam com a lógica de cada requisição. A organização segue as melhores
práticas do Django, agrupando as rotas por funcionalidade para facilitar a
manutenção e a legibilidade.

O `app_name = 'gestao'` define um namespace para as URLs, permitindo que
sejam referenciadas de forma única em todo o projeto (ex: {% url 'gestao:detalhe_processo' %}).
Isso evita conflitos de nomes entre diferentes aplicativos.
"""

from django.urls import path, include
from . import views, views_calculo_pro, api_calculos_pro

# Define o namespace da aplicação. Essencial para o bom funcionamento do 'reverse()' e da tag {% url %}
app_name = 'gestao'

urlpatterns = [
    # ==============================================================================
    # ROTAS PRINCIPAIS, DASHBOARD E AUTENTICAÇÃO
    # ==============================================================================
    path('', views.dashboard, name='home'),  # Raiz do app redireciona para o dashboard
    path('dashboard/', views.dashboard, name='dashboard'),
    path('accounts/', include('django.contrib.auth.urls')),  # Inclui URLs padrão de autenticação do Django

    # ==============================================================================
    # ROTAS PARA CLIENTES E PESSOAS
    # ==============================================================================
    path('clientes/', views.lista_clientes, name='lista_clientes'),
    path('pessoas/', views.lista_pessoas, name='lista_pessoas'), # Lista todas as pessoas, clientes ou não
    path('clientes/adicionar/', views.adicionar_cliente_page, name='adicionar_cliente_page'),
    path('clientes/<int:pk>/', views.detalhe_cliente, name='detalhe_cliente'),
    path('clientes/<int:pk>/excluir/', views.excluir_cliente, name='excluir_cliente'),

    # ==============================================================================
    # ROTAS PARA PROCESSOS
    # ==============================================================================
    path('processos/', views.lista_processos, name='lista_processos'),
    path('processo/adicionar/', views.adicionar_processo, name='adicionar_processo'),
    path('processo/<int:pk>/', views.detalhe_processo, name='detalhe_processo'),
    path('processo/<int:pk>/editar/', views.editar_processo, name='editar_processo'),
    path('processo/<int:pk>/arquivar/', views.arquivar_processo, name='arquivar_processo'),
    path('processo/<int:pk>/desarquivar/', views.desarquivar_processo, name='desarquivar_processo'),
    path('processo/<int:processo_pk>/gerenciar-partes/', views.gerenciar_partes, name='gerenciar_partes'),

    # ==============================================================================
    # ROTAS PARA SERVIÇOS EXTRAJUDICIAIS
    # ==============================================================================
    path('servicos/', views.lista_servicos, name='lista_servicos'),
    path('servico/adicionar/', views.adicionar_servico_view, name='adicionar_servico'),
    path('servico/<int:pk>/', views.detalhe_servico, name='detalhe_servico'),
    path('servico/<int:pk>/editar/', views.editar_servico, name='editar_servico'),
    path('servico/<int:pk>/concluir/', views.concluir_servico, name='concluir_servico'),
    path('servico/<int:pk>/excluir/', views.excluir_servico, name='excluir_servico'),

    # ==============================================================================
    # ROTAS PARA O MÓDULO FINANCEIRO
    # ==============================================================================
    path('financeiro/', views.painel_financeiro, name='painel_financeiro'),
    path('financeiro/despesas/', views.painel_despesas, name='painel_despesas'),
    path('financeiro/despesa/adicionar/', views.adicionar_despesa_wizard, name='adicionar_despesa_wizard'),
    path('processo/<int:processo_pk>/adicionar-contrato/', views.adicionar_contrato, name='adicionar_contrato_processo'),
    path('servico/<int:servico_pk>/adicionar-contrato/', views.adicionar_contrato, name='adicionar_contrato_servico'),
    path('pagamento/<int:pk>/editar/', views.editar_pagamento, name='editar_pagamento'),
    path('pagamento/<int:pk>/excluir/', views.excluir_pagamento, name='excluir_pagamento'),
    path('lancamento/<int:pk>/adicionar_pagamento/', views.adicionar_pagamento, name='adicionar_pagamento'),
    path('recibo/<int:pagamento_pk>/imprimir/', views.imprimir_recibo, name='imprimir_recibo'),

    # ==============================================================================
    # ROTAS PARA FERRAMENTAS (DOCUMENTOS, CÁLCULOS, IMPORTAÇÃO)
    # ==============================================================================
    # --- Modelos de Documentos ---
    path('modelos/', views.lista_modelos, name='lista_modelos'),
    path('modelos/adicionar/', views.adicionar_modelo, name='adicionar_modelo'),
    path('modelos/<int:pk>/editar/', views.editar_modelo, name='editar_modelo'),
    path('modelos/<int:pk>/excluir/', views.excluir_modelo, name='excluir_modelo'),
    path('processo/<int:processo_pk>/gerar-documento/<int:modelo_pk>/', views.gerar_documento, name='gerar_documento'),
    path('documento/<int:pk>/editar/', views.editar_documento, name='editar_documento'),
    path('documento/<int:pk>/imprimir/', views.imprimir_documento, name='imprimir_documento'),

    # --- Wizard de Cálculos e API ---
    path('calculos/novo/', views.calculo_wizard_view, name='calculo_novo'),
    path('calculos/novo/processo/<int:processo_pk>/', views.calculo_wizard_view, name='calculo_novo_com_processo'),
    path('api/calculos/simular/', views.simular_calculo_api, name='api_simular_calculo'),
    path('api/indices/catalogo/', views.api_indices_catalogo, name='api_indices_catalogo'),
    path('api/indices/valores/', views.api_indices_valores, name='api_indices_valores'),

    # --- Importação Projudi ---
    path('importacao/projudi/', views.importacao_projudi_view, name='importacao_projudi'),
    path('importacao/projudi/analisar/', views.analisar_dados_projudi_ajax, name='analisar_dados_projudi_ajax'),
    path('importacao/projudi/confirmar/', views.confirmar_importacao_projudi, name='confirmar_importacao_projudi'),
    path('importacao/projudi/executar/', views.executar_importacao_projudi, name='executar_importacao_projudi'),

    # ==============================================================================
    # ROTAS DE SERVIÇO (AJAX, JSON, PARTIALS) - Usadas para interatividade
    # ==============================================================================
    # --- Busca e Agenda ---
    path('ajax/global-search/', views.global_search, name='global_search'),
    path('dashboard/update-agenda/', views.update_agenda_partial, name='update_agenda_partial'),
    path('agenda/concluir/<str:tipo>/<int:pk>/', views.concluir_item_agenda_ajax, name='concluir_item_agenda_ajax'),

    # --- Endpoints para Clientes ---
    path('clientes/salvar/', views.salvar_cliente, name='adicionar_cliente'),
    path('clientes/<int:pk>/salvar/', views.salvar_cliente, name='editar_cliente'),
    path('clientes/<int:pk>/json/', views.get_cliente_json, name='get_cliente_json'),
    path('clientes/json/all/', views.get_all_clients_json, name='get_all_clients_json'),
    path('cliente/adicionar/modal/', views.adicionar_cliente_modal, name='adicionar_cliente_modal'),

    # --- Endpoints para Processos e Movimentações ---
    path('processo/<int:processo_pk>/partial/partes/', views.detalhe_processo_partes_partial, name='detalhe_processo_partes_partial'),
    path('movimentacao/<int:pk>/editar/', views.editar_movimentacao, name='editar_movimentacao'),
    path('movimentacao/<int:pk>/excluir/', views.excluir_movimentacao, name='excluir_movimentacao'),
    path('movimentacao/<int:pk>/concluir/', views.concluir_movimentacao, name='concluir_movimentacao'),
    path('movimentacao/<int:pk>/json/', views.get_movimentacao_json, name='get_movimentacao_json'),
    path('movimentacao/<int:pk>/editar/ajax/', views.editar_movimentacao_ajax, name='editar_movimentacao_ajax'),

    # --- Endpoints para Serviços e suas Movimentações ---
    path('servico/salvar/ajax/', views.salvar_servico_ajax, name='salvar_servico_ajax'),
    path('servico/<int:pk>/json/', views.get_servico_json, name='get_servico_json'),
    path('servico/<int:pk>/editar/ajax/', views.editar_servico_ajax, name='editar_servico_ajax'),
    path('movimentacao-servico/<int:pk>/editar/ajax/', views.editar_movimentacao_servico_ajax, name='editar_movimentacao_servico_ajax'),
    path('movimentacao-servico/<int:pk>/json/', views.get_movimentacao_servico_json, name='get_movimentacao_servico_json'),

    # --- Endpoints para Financeiro (Tabelas, NFS-e) ---
    path('ajax/tabela_financeira/<int:parent_pk>/<str:parent_type>/', views.atualizar_tabela_financeira_partial, name='atualizar_tabela_financeira_partial'),
    path('servico/<int:servico_pk>/emitir-nfse/', views.emitir_nfse_view, name='emitir_nfse'),

    # --- Endpoints Genéricos para Cadastros Auxiliares (usado nas Configurações) ---
    path('cadastros-auxiliares/<str:modelo>/salvar/', views.salvar_cadastro_auxiliar_ajax, name='salvar_cadastro_auxiliar_ajax'),
    path('cadastros-auxiliares/<str:modelo>/<int:pk>/salvar/', views.salvar_cadastro_auxiliar_ajax, name='editar_cadastro_auxiliar_ajax'),
    path('cadastros-auxiliares/<str:modelo>/<int:pk>/excluir/', views.excluir_cadastro_auxiliar_ajax, name='excluir_cadastro_auxiliar_ajax'),

    # ==============================================================================
    # ROTAS DE CONFIGURAÇÃO E ADMINISTRAÇÃO DO SISTEMA
    # ==============================================================================
    path('configuracoes/', views.configuracoes, name='configuracoes'),
    path('usuarios/adicionar/', views.adicionar_usuario, name='adicionar_usuario'),
    path('usuarios/<int:user_id>/editar/', views.editar_usuario, name='editar_usuario'),
    path('usuarios/<int:user_id>/ativar-desativar/', views.ativar_desativar_usuario, name='ativar_desativar_usuario'),
    path('grupos/<int:group_id>/permissoes/json/', views.get_permissoes_grupo_ajax, name='get_permissoes_grupo_ajax'),
    path('grupos/<int:group_id>/permissoes/salvar/', views.salvar_permissoes_grupo, name='salvar_permissoes_grupo'),

    # === NOVAS ROTAS PARA O CÁLCULO PRO v2 ===
    path('calculos/novo-pro/', views_calculo_pro.calculo_pro_view, name='calculo_pro'),

    # === NOVAS APIS PARA O CÁLCULO PRO v2 ===
    path('api/calculos/preview/', api_calculos_pro.preview_calculo_pro, name='api_calculo_pro_preview'),
    path('api/calculos/replicar/', api_calculos_pro.replicar_parcelas, name='api_calculo_pro_replicar'),
    path('api/calculos/batch-update/', api_calculos_pro.batch_update_parcelas, name='api_calculo_pro_batch_update'),

]