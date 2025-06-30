# gestao/urls.py

# A importação 'include' não é mais necessária aqui, pois as rotas de outros
# apps foram movidas para o local correto.
from django.urls import path
from . import views

# O app_name é essencial para que o Django possa diferenciar as URLs
# deste aplicativo de outros. Ex: {% url 'gestao:detalhe_cliente' cliente.pk %}
app_name = 'gestao'

urlpatterns = [
    # ==============================================================================
    # ROTAS GERAIS E DASHBOARD
    # ==============================================================================
    path('', views.dashboard, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),

    # ==============================================================================
    # GESTÃO DE CLIENTES
    # ==============================================================================
    path('clientes/', views.lista_clientes, name='lista_clientes'),
    path('clientes/adicionar/', views.adicionar_cliente_page, name='adicionar_cliente_page'),
    path('clientes/<int:pk>/', views.detalhe_cliente, name='detalhe_cliente'),
    path('clientes/<int:pk>/excluir/', views.excluir_cliente, name='excluir_cliente'),
    # Rotas AJAX para Cliente
    path('clientes/salvar/', views.salvar_cliente, name='adicionar_cliente'),
    path('clientes/<int:pk>/salvar/', views.salvar_cliente, name='editar_cliente'),
    path('clientes/<int:pk>/json/', views.get_cliente_json, name='get_cliente_json'),
    path('cliente/adicionar/modal/', views.adicionar_cliente_modal, name='adicionar_cliente_modal'),

    # ==============================================================================
    # GESTÃO DE PROCESSOS
    # ==============================================================================
    path('processos/', views.lista_processos, name='lista_processos'),
    path('processo/adicionar/', views.adicionar_processo, name='adicionar_processo'),
    path('processo/<int:pk>/', views.detalhe_processo, name='detalhe_processo'),
    path('processo/<int:pk>/editar/', views.editar_processo, name='editar_processo'),
    path('processo/<int:pk>/arquivar/', views.arquivar_processo, name='arquivar_processo'),
    path('processo/<int:pk>/desarquivar/', views.desarquivar_processo, name='desarquivar_processo'),
    path('processo/<int:processo_pk>/gerenciar-partes/', views.gerenciar_partes, name='gerenciar_partes'),
    path('processo/<int:processo_pk>/partial/partes/', views.detalhe_processo_partes_partial, name='detalhe_processo_partes_partial'),
    path('movimentacao/<int:pk>/editar/', views.editar_movimentacao, name='editar_movimentacao'),
    path('movimentacao/<int:pk>/excluir/', views.excluir_movimentacao, name='excluir_movimentacao'),
    path('movimentacao/<int:pk>/concluir/', views.concluir_movimentacao, name='concluir_movimentacao'),

    # ==============================================================================
    # GESTÃO DE SERVIÇOS EXTRAJUDICIAIS
    # ==============================================================================
    path('servicos/', views.lista_servicos, name='lista_servicos'),
    path('servico/adicionar/', views.adicionar_servico_view, name='adicionar_servico'),
    path('servico/<int:pk>/', views.detalhe_servico, name='detalhe_servico'),
    path('servico/<int:pk>/editar/', views.editar_servico, name='editar_servico'),
    path('servico/<int:pk>/concluir/', views.concluir_servico, name='concluir_servico'),
    path('movimentacao-servico/<int:pk>/editar/', views.editar_movimentacao_servico, name='editar_movimentacao_servico'),
    path('movimentacao-servico/<int:pk>/excluir/', views.excluir_movimentacao_servico, name='excluir_movimentacao_servico'),
    path('movimentacao-servico/<int:pk>/concluir/', views.concluir_movimentacao_servico, name='concluir_movimentacao_servico'),

    # ==============================================================================
    # GESTÃO FINANCEIRA (Contratos e Pagamentos)
    # ==============================================================================
    path('processo/<int:processo_pk>/adicionar-contrato/', views.adicionar_contrato, name='adicionar_contrato_processo'),
    path('servico/<int:servico_pk>/adicionar-contrato/', views.adicionar_contrato, name='adicionar_contrato_servico'),
    path('pagamento/<int:pk>/editar/', views.editar_pagamento, name='editar_pagamento'),
    path('pagamento/<int:pk>/excluir/', views.excluir_pagamento, name='excluir_pagamento'),
    path('lancamento/<int:pk>/adicionar_pagamento/', views.adicionar_pagamento, name='adicionar_pagamento'),
    path('recibo/<int:pagamento_pk>/imprimir/', views.imprimir_recibo, name='imprimir_recibo'),

    # ==============================================================================
    # FERRAMENTAS (Modelos, Documentos, Cálculos)
    # ==============================================================================
    path('modelos/', views.lista_modelos, name='lista_modelos'),
    path('modelos/adicionar/', views.adicionar_modelo, name='adicionar_modelo'),
    path('modelos/<int:pk>/editar/', views.editar_modelo, name='editar_modelo'),
    path('modelos/<int:pk>/excluir/', views.excluir_modelo, name='excluir_modelo'),
    path('processo/<int:processo_pk>/gerar-documento/<int:modelo_pk>/', views.gerar_documento, name='gerar_documento'),
    path('documento/<int:pk>/editar/', views.editar_documento, name='editar_documento'),
    path('processo/<int:processo_pk>/calculos/', views.realizar_calculo, name='pagina_de_calculos'),
    path('processo/<int:processo_pk>/calculo/novo/', views.realizar_calculo, name='novo_calculo'),
    path('processo/<int:processo_pk>/calculos/<int:calculo_pk>/', views.realizar_calculo, name='carregar_calculo'),
    path('calculo/<int:calculo_pk>/atualizar-hoje/', views.atualizar_calculo_hoje, name='atualizar_calculo_hoje'),
    path('calculo/<int:calculo_pk>/excluir/', views.excluir_calculo, name='excluir_calculo'),
    path('processo/<int:processo_pk>/calculos/excluir-todos/', views.excluir_todos_calculos, name='excluir_todos_calculos'),

    # ==============================================================================
    # CONFIGURAÇÕES E GERENCIAMENTO DE USUÁRIOS
    # ==============================================================================
    path('configuracoes/', views.configuracoes, name='configuracoes'),
    path('configuracoes/usuarios/adicionar/', views.adicionar_usuario, name='adicionar_usuario'),
    path('configuracoes/usuarios/<int:user_id>/editar/', views.editar_usuario, name='editar_usuario'),
    path('configuracoes/usuarios/<int:user_id>/ativar-desativar/', views.ativar_desativar_usuario, name='ativar_desativar_usuario'),
    path('configuracoes/permissoes/grupo/<int:group_id>/', views.get_permissoes_grupo_ajax, name='get_permissoes_grupo_ajax'),
    path('configuracoes/permissoes/salvar/<int:group_id>/', views.salvar_permissoes_grupo, name='salvar_permissoes_grupo'),
    path('configuracoes/cadastros/salvar/<str:modelo>/', views.salvar_cadastro_auxiliar_ajax, name='salvar_cadastro_auxiliar_ajax'),
    path('configuracoes/cadastros/salvar/<str:modelo>/<int:pk>/', views.salvar_cadastro_auxiliar_ajax, name='editar_cadastro_auxiliar_ajax'),
    path('configuracoes/cadastros/excluir/<str:modelo>/<int:pk>/', views.excluir_cadastro_auxiliar_ajax, name='excluir_cadastro_auxiliar_ajax'),

    # ==============================================================================
    # ROTAS DE SERVIÇO (AJAX e Partials)
    # ==============================================================================
    path('servico/salvar/ajax/', views.salvar_servico_ajax, name='salvar_servico_ajax'),
    path('tiposervico/adicionar/modal/', views.adicionar_tipo_servico_modal, name='adicionar_tipo_servico_modal'),
    path('servico/<int:servico_pk>/andamento/ajax/adicionar/', views.adicionar_movimentacao_servico_ajax, name='adicionar_movimentacao_servico_ajax'),
    path('servico/<int:servico_pk>/andamento/partial/', views.atualizar_historico_servico_partial, name='atualizar_historico_servico_partial'),
    path('servico/<int:pk>/componentes-financeiros/', views.atualizar_componentes_financeiros_servico, name='atualizar_componentes_financeiros_servico'),
    path('ajax/tabela_financeira/<int:parent_pk>/<str:parent_type>/', views.atualizar_tabela_financeira_partial, name='atualizar_tabela_financeira_partial'),
]