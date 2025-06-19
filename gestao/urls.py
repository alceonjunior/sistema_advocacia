# gestao/urls.py

from django.urls import path
from . import views

urlpatterns = [
    # --- GERAL ---
    path('', views.dashboard, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),

    # --- PROCESSOS JUDICIAIS ---
    path('processos/', views.lista_processos, name='lista_processos'),
    path('processo/adicionar/', views.adicionar_processo, name='adicionar_processo'),
    path('processo/<int:pk>/', views.detalhe_processo, name='detalhe_processo'),
    path('processo/<int:pk>/editar/', views.editar_processo, name='editar_processo'),
    path('processo/<int:processo_pk>/gerenciar-partes/', views.gerenciar_partes, name='gerenciar_partes'),
    path('processo/<int:processo_pk>/partial/partes/', views.detalhe_processo_partes_partial, name='detalhe_processo_partes_partial'),
    path('movimentacao/<int:pk>/editar/', views.editar_movimentacao, name='editar_movimentacao'),
    path('movimentacao/<int:pk>/excluir/', views.excluir_movimentacao, name='excluir_movimentacao'),
    path('movimentacao/<int:pk>/concluir/', views.concluir_movimentacao, name='concluir_movimentacao'),

    # --- SERVIÇOS EXTRAJUDICIAIS ---
    path('servicos/', views.lista_servicos, name='lista_servicos'),
    path('servico/adicionar/', views.adicionar_servico, name='adicionar_servico'),
    path('servico/<int:pk>/', views.detalhe_servico, name='detalhe_servico'),
    path('servico/<int:pk>/editar/', views.editar_servico, name='editar_servico'),
    path('movimentacao-servico/<int:pk>/editar/', views.editar_movimentacao_servico, name='editar_movimentacao_servico'),
    path('movimentacao-servico/<int:pk>/excluir/', views.excluir_movimentacao_servico, name='excluir_movimentacao_servico'),
    path('movimentacao-servico/<int:pk>/concluir/', views.concluir_movimentacao_servico, name='concluir_movimentacao_servico'),
    path('servico/<int:pk>/concluir/', views.concluir_servico, name='concluir_servico'),

    # --- GESTÃO DE CLIENTES ---
    path('clientes/', views.lista_clientes, name='lista_clientes'),
    path('clientes/salvar/', views.salvar_cliente, name='adicionar_cliente'),
    path('clientes/<int:pk>/salvar/', views.salvar_cliente, name='editar_cliente'),
    path('clientes/<int:pk>/json/', views.get_cliente_json, name='get_cliente_json'),
    path('clientes/<int:pk>/excluir/', views.excluir_cliente, name='excluir_cliente'),

    # --- FINANCEIRO ---
    path('lancamento/<int:pk>/adicionar_pagamento/', views.adicionar_pagamento, name='adicionar_pagamento'),
    path('pagamento/<int:pk>/editar/', views.editar_pagamento, name='editar_pagamento'),
    path('pagamento/<int:pk>/excluir/', views.excluir_pagamento, name='excluir_pagamento'),
    path('processo/<int:processo_pk>/adicionar-contrato/', views.adicionar_contrato, name='adicionar_contrato_processo'),
    path('servico/<int:servico_pk>/adicionar-contrato/', views.adicionar_contrato, name='adicionar_contrato_servico'),

    # --- CÁLCULO JUDICIAL (BLOCO REATORADO E UNIFICADO) ---
    # A URL principal agora vai direto para a view de cálculo, que lida com 'novo' ou 'carregar'.
    path('processo/<int:processo_pk>/calculos/', views.realizar_calculo, name='pagina_de_calculos'),

    # URL para carregar/submeter um cálculo existente. A view sabe lidar com o GET (carregar) e POST (recalcular/salvar novo).
    path('processo/<int:processo_pk>/calculos/<int:calculo_pk>/', views.realizar_calculo, name='carregar_calculo'),

    # URL para a ação de POST 'Atualizar para Hoje'.
    path('calculo/<int:calculo_pk>/atualizar-hoje/', views.atualizar_calculo_hoje, name='atualizar_calculo_hoje'),

    # A URL 'novo_calculo' continua existindo para compatibilidade com o formulário,
    # mas aponta para a mesma view unificada.
    path('processo/<int:processo_pk>/calculo/novo/', views.realizar_calculo, name='novo_calculo'),

    # === ROTAS DE EXCLUSÃO ADICIONADAS AQUI ===
    path('calculo/<int:calculo_pk>/excluir/', views.excluir_calculo, name='excluir_calculo'),
    path('processo/<int:processo_pk>/calculos/excluir-todos/', views.excluir_todos_calculos, name='excluir_todos_calculos'),

    # --- ROTAS INTERNAS PARA MODAIS (AJAX) ---
    path('cliente/adicionar/modal/', views.adicionar_cliente_modal, name='adicionar_cliente_modal'),
    path('tiposervico/adicionar/modal/', views.adicionar_tipo_servico_modal, name='adicionar_tipo_servico_modal'),
]
