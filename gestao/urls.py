# gestao/urls.py

# A importação 'include' não é mais necessária aqui, pois as rotas de outros
# apps foram movidas para o local correto.
from django.urls import path
from . import views
from .views import lista_clientes, lista_pessoas

# O app_name é essencial para que o Django possa diferenciar as URLs
# deste aplicativo de outros. Ex: {% url 'gestao:detalhe_cliente' cliente.pk %}
app_name = 'gestao'

urlpatterns = [
    # ==============================================================================
    # ROTAS GERAIS E DASHBOARD
    # Esta seção contém as URLs para a página inicial e o painel principal do sistema.
    # ==============================================================================
    path('', views.dashboard, name='home'),  # Rota para a página inicial (raiz do app)
    path('dashboard/', views.dashboard, name='dashboard'), # Rota explícita para o dashboard

    # ==============================================================================
    # GESTÃO DE CLIENTES
    # URLs para gerenciar clientes, incluindo listagem, adição, detalhes, exclusão
    # e operações AJAX para formulários modais.
    # ==============================================================================
    path('clientes/', lista_clientes, name='lista_clientes'),
    path('pessoas/', lista_pessoas, name='lista_pessoas'),
    path('clientes/excluir-massa/', views.excluir_clientes_em_massa, name='excluir_clientes_em_massa'),

    path('clientes/adicionar/', views.adicionar_cliente_page, name='adicionar_cliente_page'), # Página para adicionar um novo cliente
    path('clientes/<int:pk>/', views.detalhe_cliente, name='detalhe_cliente'), # Detalhes de um cliente específico
    path('clientes/<int:pk>/excluir/', views.excluir_cliente, name='excluir_cliente'), # Excluir um cliente

    # Rotas AJAX para operações de Cliente
    path('clientes/salvar/', views.salvar_cliente, name='adicionar_cliente'), # Salvar novo cliente via AJAX
    path('clientes/<int:pk>/salvar/', views.salvar_cliente, name='editar_cliente'), # Editar cliente existente via AJAX
    path('clientes/<int:pk>/json/', views.get_cliente_json, name='get_cliente_json'), # Retornar dados do cliente em JSON
    path('cliente/adicionar/modal/', views.adicionar_cliente_modal, name='adicionar_cliente_modal'), # Adicionar cliente via modal AJAX

    # ==============================================================================
    # GESTÃO DE PROCESSOS
    # URLs para o gerenciamento de processos judiciais, incluindo CRUD e
    # ações relacionadas a movimentações e partes.
    # ==============================================================================
    path('processos/', views.lista_processos, name='lista_processos'), # Lista de todos os processos
    path('processo/adicionar/', views.adicionar_processo, name='adicionar_processo'), # Adicionar novo processo
    path('processo/<int:pk>/', views.detalhe_processo, name='detalhe_processo'), # Detalhes de um processo
    path('processo/<int:pk>/editar/', views.editar_processo, name='editar_processo'), # Editar processo
    path('processo/<int:pk>/arquivar/', views.arquivar_processo, name='arquivar_processo'), # Arquivar processo
    path('processo/<int:pk>/desarquivar/', views.desarquivar_processo, name='desarquivar_processo'), # Desarquivar processo
    path('processo/<int:processo_pk>/gerenciar-partes/', views.gerenciar_partes, name='gerenciar_partes'), # Gerenciar partes do processo
    path('processo/<int:processo_pk>/partial/partes/', views.detalhe_processo_partes_partial, name='detalhe_processo_partes_partial'), # Partial para partes do processo
    path('movimentacao/<int:pk>/editar/', views.editar_movimentacao, name='editar_movimentacao'), # Editar movimentação
    path('movimentacao/<int:pk>/excluir/', views.excluir_movimentacao, name='excluir_movimentacao'), # Excluir movimentação
    path('movimentacao/<int:pk>/concluir/', views.concluir_movimentacao, name='concluir_movimentacao'), # Concluir movimentação

    # ==============================================================================
    # GESTÃO DE SERVIÇOS EXTRAJUDICIAIS
    # URLs para gerenciar serviços, incluindo listagem, adição, detalhes, edição
    # e movimentações/tarefas específicas de serviços.
    # ==============================================================================
    path('servicos/', views.lista_servicos, name='lista_servicos'), # Lista de todos os serviços
    path('servico/adicionar/', views.adicionar_servico_view, name='adicionar_servico'), # Adicionar novo serviço
    path('servico/<int:pk>/', views.detalhe_servico, name='detalhe_servico'), # Detalhes de um serviço
    path('servico/<int:pk>/editar/', views.editar_servico, name='editar_servico'), # Editar serviço
    path('servico/<int:pk>/concluir/', views.concluir_servico, name='concluir_servico'), # Concluir serviço
    path('movimentacao-servico/<int:pk>/editar/', views.editar_movimentacao_servico, name='editar_movimentacao_servico'), # Editar movimentação de serviço
    path('movimentacao-servico/<int:pk>/excluir/', views.excluir_movimentacao_servico, name='excluir_movimentacao_servico'), # Excluir movimentação de serviço
    path('movimentacao-servico/<int:pk>/concluir/', views.concluir_movimentacao_servico, name='concluir_movimentacao_servico'), # Concluir movimentação de serviço
    path('servico/<int:pk>/excluir/', views.excluir_servico, name='excluir_servico'), # Excluir serviço

    # ==============================================================================
    # GESTÃO FINANCEIRA (Contratos, Pagamentos, Painéis e Despesas)
    # URLs para o painel financeiro, gerenciamento de contratos, pagamentos
    # e o novo fluxo de adição de despesas.
    # ==============================================================================
    path('financeiro/', views.painel_financeiro, name='painel_financeiro'), # Painel financeiro principal

    # Rota para o novo wizard de adição de despesas
    path('financeiro/despesa/adicionar/', views.adicionar_despesa_wizard, name='adicionar_despesa_wizard'),

    # Rotas para contratos e pagamentos
    path('processo/<int:processo_pk>/adicionar-contrato/', views.adicionar_contrato, name='adicionar_contrato_processo'), # Adicionar contrato a um processo
    path('servico/<int:servico_pk>/adicionar-contrato/', views.adicionar_contrato, name='adicionar_contrato_servico'), # Adicionar contrato a um serviço
    path('pagamento/<int:pk>/editar/', views.editar_pagamento, name='editar_pagamento'), # Editar pagamento
    path('pagamento/<int:pk>/excluir/', views.excluir_pagamento, name='excluir_pagamento'), # Excluir pagamento
    path('lancamento/<int:pk>/adicionar_pagamento/', views.adicionar_pagamento, name='adicionar_pagamento'), # Adicionar pagamento a um lançamento
    path('recibo/<int:pagamento_pk>/imprimir/', views.imprimir_recibo, name='imprimir_recibo'), # Imprimir recibo de pagamento

    # Rota para salvar lançamentos financeiros via AJAX (usado no modal de Receitas/Despesas avulsas)
    path('financeiro/lancamento/adicionar/ajax/', views.adicionar_lancamento_financeiro_ajax, name='adicionar_lancamento_financeiro_ajax'),

    # ==============================================================================
    # FERRAMENTAS (Modelos, Documentos, Cálculos Judiciais)
    # URLs para gerenciar modelos de documentos, gerar/editar documentos e
    # usar a ferramenta de cálculo judicial.
    # ==============================================================================
    path('modelos/', views.lista_modelos, name='lista_modelos'), # Lista de modelos de documentos
    path('modelos/adicionar/', views.adicionar_modelo, name='adicionar_modelo'), # Adicionar novo modelo
    path('modelos/<int:pk>/editar/', views.editar_modelo, name='editar_modelo'), # Editar modelo
    path('modelos/<int:pk>/excluir/', views.excluir_modelo, name='excluir_modelo'), # Excluir modelo
    path('processo/<int:processo_pk>/gerar-documento/<int:modelo_pk>/', views.gerar_documento, name='gerar_documento'), # Gerar documento a partir de modelo
    path('documento/<int:pk>/editar/', views.editar_documento, name='editar_documento'), # Editar documento
    path('documento/<int:pk>/imprimir/', views.imprimir_documento, name='imprimir_documento'), # Imprimir documento
    path('processo/<int:processo_pk>/calculos/', views.realizar_calculo, name='pagina_de_calculos'), # Página de cálculos judiciais
    path('processo/<int:processo_pk>/calculo/novo/', views.realizar_calculo, name='novo_calculo'), # Novo cálculo
    path('processo/<int:processo_pk>/calculos/<int:calculo_pk>/', views.realizar_calculo, name='carregar_calculo'), # Carregar cálculo existente
    path('calculo/<int:calculo_pk>/atualizar-hoje/', views.atualizar_calculo_hoje, name='atualizar_calculo_hoje'), # Atualizar cálculo para data de hoje
    path('calculo/<int:calculo_pk>/excluir/', views.excluir_calculo, name='excluir_calculo'), # Excluir cálculo
    path('processo/<int:processo_pk>/calculos/excluir-todos/', views.excluir_todos_calculos, name='excluir_todos_calculos'), # Excluir todos os cálculos de um processo

    # ==============================================================================
    # CONFIGURAÇÕES E GERENCIAMENTO DE USUÁRIOS
    # URLs para as configurações gerais do escritório e gestão de usuários/permissões.
    # ==============================================================================
    path('configuracoes/', views.configuracoes, name='configuracoes'), # Página de configurações
    path('configuracoes/usuarios/adicionar/', views.adicionar_usuario, name='adicionar_usuario'), # Adicionar novo usuário
    path('configuracoes/usuarios/<int:user_id>/editar/', views.editar_usuario, name='editar_usuario'), # Editar usuário
    path('configuracoes/usuarios/<int:user_id>/ativar-desativar/', views.ativar_desativar_usuario, name='ativar_desativar_usuario'), # Ativar/desativar usuário
    path('configuracoes/permissoes/grupo/<int:group_id>/', views.get_permissoes_grupo_ajax, name='get_permissoes_grupo_ajax'), # Obter permissões de grupo via AJAX
    path('configuracoes/permissoes/salvar/<int:group_id>/', views.salvar_permissoes_grupo, name='salvar_permissoes_grupo'), # Salvar permissões de grupo
    path('configuracoes/cadastros/salvar/<str:modelo>/', views.salvar_cadastro_auxiliar_ajax, name='salvar_cadastro_auxiliar_ajax'), # Salvar cadastro auxiliar (tipos, áreas) via AJAX
    path('configuracoes/cadastros/salvar/<str:modelo>/<int:pk>/', views.salvar_cadastro_auxiliar_ajax, name='editar_cadastro_auxiliar_ajax'), # Editar cadastro auxiliar via AJAX
    path('configuracoes/cadastros/excluir/<str:modelo>/<int:pk>/', views.excluir_cadastro_auxiliar_ajax, name='excluir_cadastro_auxiliar_ajax'), # Excluir cadastro auxiliar via AJAX

    # ==============================================================================
    # ROTAS DE SERVIÇO (AJAX e Partials Específicos)
    # Estas rotas são usadas principalmente para interações assíncronas (AJAX) e
    # carregamento de partes de templates (partials).
    # ==============================================================================
    path('servico/salvar/ajax/', views.salvar_servico_ajax, name='salvar_servico_ajax'), # Salvar serviço via AJAX
    path('tiposervico/adicionar/modal/', views.adicionar_tipo_servico_modal, name='adicionar_tipo_servico_modal'), # Adicionar tipo de serviço via modal
    path('servico/<int:servico_pk>/andamento/ajax/adicionar/', views.adicionar_movimentacao_servico_ajax, name='adicionar_movimentacao_servico_ajax'), # Adicionar movimentação de serviço via AJAX
    path('servico/<int:servico_pk>/andamento/partial/', views.atualizar_historico_servico_partial, name='atualizar_historico_servico_partial'), # Atualizar histórico de serviço via partial
    path('servico/<int:pk>/componentes-financeiros/', views.atualizar_componentes_financeiros_servico, name='atualizar_componentes_financeiros_servico'), # Atualizar componentes financeiros do serviço
    path('ajax/tabela_financeira/<int:parent_pk>/<str:parent_type>/', views.atualizar_tabela_financeira_partial, name='atualizar_tabela_financeira_partial'), # Atualizar tabela financeira via partial

    # Rotas AJAX para buscar e editar movimentações/serviços
    path('movimentacao/<int:pk>/json/', views.get_movimentacao_json, name='get_movimentacao_json'), # Obter movimentação em JSON
    path('movimentacao/<int:pk>/editar/ajax/', views.editar_movimentacao_ajax, name='editar_movimentacao_ajax'), # Editar movimentação via AJAX

    path('servico/<int:pk>/json/', views.get_servico_json, name='get_servico_json'), # Obter serviço em JSON
    path('servico/<int:pk>/editar/ajax/', views.editar_servico_ajax, name='editar_servico_ajax'), # Editar serviço via AJAX

    path('movimentacao-servico/<int:pk>/json/', views.get_movimentacao_servico_json, name='get_movimentacao_servico_json'), # Obter movimentação de serviço em JSON
    path('movimentacao-servico/<int:pk>/editar/ajax/', views.editar_movimentacao_servico_ajax, name='editar_movimentacao_servico_ajax'), # Editar movimentação de serviço via AJAX

    path('servico/<int:servico_pk>/emitir-nfse/', views.emitir_nfse_view, name='emitir_nfse'), # Emitir NFS-e para serviço

    path('clientes/json/all/', views.get_all_clients_json, name='get_all_clients_json'), # Obter todos os clientes em JSON

    path('importar/projudi/', views.importacao_projudi_view, name='importacao_projudi'),
    path('importacao/projudi/analisar/', views.analisar_dados_projudi_ajax, name='analisar_dados_projudi_ajax'),

    path('importacao/projudi/processar/', views.processar_importacao_projudi, name='processar_importacao_projudi'),

    path('ajax/global-search/', views.global_search, name='global_search'),
    path('dashboard/update-agenda/', views.update_agenda_partial, name='update_agenda_partial'),
    path('agenda/concluir/<str:tipo>/<int:pk>/', views.concluir_item_agenda_ajax, name='concluir_item_agenda_ajax'),

]