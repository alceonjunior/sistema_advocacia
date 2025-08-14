# gestao/urls.py
"""
URLs do app 'gestao'.

Observações:
- Evitamos rotas duplicadas (mesmo path e/ou mesmo 'name'), pois o Django usa a última definição e isso gera
  comportamentos confusos.
- Como 'gestao.urls' é incluído na RAIZ em config/urls.py (path('', include('gestao.urls'))), todos os paths abaixo
  ficam acessíveis diretamente a partir de '/', por exemplo: '/ajax/calculo/wizard/calcular/'.
"""

from django.urls import path, include
from . import views

app_name = 'gestao'

urlpatterns = [
    # ==============================================================================
    # CORE & AUTENTICAÇÃO
    # ==============================================================================
    path('', views.dashboard, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('accounts/', include('django.contrib.auth.urls')),

    # ==============================================================================
    # CLIENTES & PESSOAS
    # ==============================================================================
    path('clientes/', views.lista_clientes, name='lista_clientes'),
    path('pessoas/', views.lista_pessoas, name='lista_pessoas'),
    path('clientes/adicionar/', views.adicionar_cliente_page, name='adicionar_cliente_page'),
    path('clientes/<int:pk>/', views.detalhe_cliente, name='detalhe_cliente'),
    path('clientes/<int:pk>/excluir/', views.excluir_cliente, name='excluir_cliente'),

    # ==============================================================================
    # PROCESSOS
    # ==============================================================================
    path('processos/', views.lista_processos, name='lista_processos'),
    path('processo/adicionar/', views.adicionar_processo, name='adicionar_processo'),
    path('processo/<int:pk>/', views.detalhe_processo, name='detalhe_processo'),
    path('processo/<int:pk>/editar/', views.editar_processo, name='editar_processo'),
    path('processo/<int:pk>/arquivar/', views.arquivar_processo, name='arquivar_processo'),
    path('processo/<int:pk>/desarquivar/', views.desarquivar_processo, name='desarquivar_processo'),
    path('processo/<int:processo_pk>/gerenciar-partes/', views.gerenciar_partes, name='gerenciar_partes'),

    # ==============================================================================
    # SERVIÇOS EXTRAJUDICIAIS
    # ==============================================================================
    path('servicos/', views.lista_servicos, name='lista_servicos'),
    path('servico/adicionar/', views.adicionar_servico_view, name='adicionar_servico'),
    path('servico/<int:pk>/', views.detalhe_servico, name='detalhe_servico'),
    path('servico/<int:pk>/editar/', views.editar_servico, name='editar_servico'),
    path('servico/<int:pk>/concluir/', views.concluir_servico, name='concluir_servico'),
    path('servico/<int:pk>/excluir/', views.excluir_servico, name='excluir_servico'),

    # ==============================================================================
    # FINANCEIRO
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
    # FERRAMENTAS / UTILITÁRIOS / CÁLCULOS
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
    path('processo/<int:processo_pk>/calculos/excluir-todos/', views.excluir_todos_calculos, name='excluir_todos_calculos'),

    # Wizard de cálculos (página)
    path('calculos/novo/', views.calculo_wizard_view, name='calculo_novo'),
    path('calculos/novo/processo/<int:processo_pk>/', views.calculo_wizard_view, name='calculo_novo_com_processo'),

    # API de simulação/salvamento/exportação (AJAX/JSON)
    path('api/calculos/simular/', views.simular_calculo_api, name='api_simular_calculo'),
    # path('api/calculos/exportar/pdf/', views.exportar_calculo_pdf, name='exportar_calculo_pdf'),

    # ==============================================================================
    # IMPORTAÇÃO PROJUDI
    # ==============================================================================
    # Use somente uma convenção. Aqui mantemos 'importacao' (moderna) e deixamos
    # um ALIAS legado 'importar/projudi/' sem 'name' para não criar conflito.
    path('importacao/projudi/', views.importacao_projudi_view, name='importacao_projudi'),
    path('importar/projudi/', views.importacao_projudi_view),  # alias legado, sem name
    path('importacao/projudi/analisar/', views.analisar_dados_projudi_ajax, name='analisar_dados_projudi_ajax'),
    path('importacao/projudi/confirmar/', views.confirmar_importacao_projudi, name='confirmar_importacao_projudi'),
    path('importacao/projudi/executar/', views.executar_importacao_projudi, name='executar_importacao_projudi'),

    # ==============================================================================
    # ENDPOINTS DE SERVIÇO (AJAX, JSON, PARTIALS)
    # ==============================================================================
    path('ajax/global-search/', views.global_search, name='global_search'),
    path('dashboard/update-agenda/', views.update_agenda_partial, name='update_agenda_partial'),
    path('agenda/concluir/<str:tipo>/<int:pk>/', views.concluir_item_agenda_ajax, name='concluir_item_agenda_ajax'),

    path('clientes/excluir-massa/', views.excluir_clientes_em_massa, name='excluir_clientes_em_massa'),
    path('clientes/salvar/', views.salvar_cliente, name='adicionar_cliente'),
    path('clientes/<int:pk>/salvar/', views.salvar_cliente, name='editar_cliente'),
    path('clientes/<int:pk>/json/', views.get_cliente_json, name='get_cliente_json'),
    path('clientes/json/all/', views.get_all_clients_json, name='get_all_clients_json'),
    path('cliente/adicionar/modal/', views.adicionar_cliente_modal, name='adicionar_cliente_modal'),

    path('processo/<int:processo_pk>/partial/partes/', views.detalhe_processo_partes_partial, name='detalhe_processo_partes_partial'),
    path('movimentacao/<int:pk>/editar/', views.editar_movimentacao, name='editar_movimentacao'),
    path('movimentacao/<int:pk>/excluir/', views.excluir_movimentacao, name='excluir_movimentacao'),
    path('movimentacao/<int:pk>/concluir/', views.concluir_movimentacao, name='concluir_movimentacao'),
    path('movimentacao/<int:pk>/json/', views.get_movimentacao_json, name='get_movimentacao_json'),
    path('movimentacao/<int:pk>/editar/ajax/', views.editar_movimentacao_ajax, name='editar_movimentacao_ajax'),

    path('servico/salvar/ajax/', views.salvar_servico_ajax, name='salvar_servico_ajax'),
    path('tiposervico/adicionar/modal/', views.adicionar_tipo_servico_modal, name='adicionar_tipo_servico_modal'),
    path('servico/<int:servico_pk>/andamento/ajax/adicionar/', views.adicionar_movimentacao_servico_ajax, name='adicionar_movimentacao_servico_ajax'),
    path('servico/<int:servico_pk>/andamento/partial/', views.atualizar_historico_servico_partial, name='atualizar_historico_servico_partial'),
    path('servico/<int:pk>/componentes-financeiros/', views.atualizar_componentes_financeiros_servico, name='atualizar_componentes_financeiros_servico'),
    path('servico/<int:pk>/json/', views.get_servico_json, name='get_servico_json'),
    path('servico/<int:pk>/editar/ajax/', views.editar_servico_ajax, name='editar_servico_ajax'),
    path('movimentacao-servico/<int:pk>/editar/', views.editar_movimentacao_servico, name='editar_movimentacao_servico'),
    path('movimentacao-servico/<int:pk>/excluir/', views.excluir_movimentacao_servico, name='excluir_movimentacao_servico'),
    path('movimentacao-servico/<int:pk>/concluir/', views.concluir_movimentacao_servico, name='concluir_movimentacao_servico'),
    path('movimentacao-servico/<int:pk>/json/', views.get_movimentacao_servico_json, name='get_movimentacao_servico_json'),
    path('movimentacao-servico/<int:pk>/editar/ajax/', views.editar_movimentacao_servico_ajax, name='editar_movimentacao_servico_ajax'),

    path('financeiro/lancamento/adicionar/ajax/', views.adicionar_lancamento_financeiro_ajax, name='adicionar_lancamento_financeiro_ajax'),
    path('ajax/tabela_financeira/<int:parent_pk>/<str:parent_type>/', views.atualizar_tabela_financeira_partial, name='atualizar_tabela_financeira_partial'),
    path('servico/<int:servico_pk>/emitir-nfse/', views.emitir_nfse_view, name='emitir_nfse'),

    # ---- CÁLCULO (AJAX)
    path('ajax/calculo/wizard/calcular/', views.calculo_wizard_calcular, name='calculo_wizard_calcular'),
    path('api/indices/valores/', views.api_indices_valores, name='api_indices_valores'),
    path('api/indices/catalogo/', views.api_indices_catalogo, name='api_indices_catalogo'),
]
