# gestao/migrations/0015_popular_tipos_movimentacao.py

from django.db import migrations

# Lista de tipos de movimentação a serem criados.
# Estrutura: (Nome do Tipo, Sugestão de Dias de Prazo [ou None se não aplicável])

TIPOS_DE_MOVIMENTACAO = [
    # --- Prazos Processuais Comuns ---
    ("Contestação", 15),
    ("Réplica à Contestação", 15),
    ("Apelação", 15),
    ("Contrarrazões de Apelação", 15),
    ("Agravo de Instrumento", 15),
    ("Contraminuta de Agravo", 15),
    ("Embargos de Declaração", 5),
    ("Recurso Especial", 15),
    ("Contrarrazões de Recurso Especial", 15),
    ("Recurso Extraordinário", 15),
    ("Contrarrazões de Recurso Extraordinário", 15),
    ("Juntada de Documentos (Prazo)", 5),
    ("Pagamento de Custas / Guias", 5),
    ("Manifestação sobre Laudo Pericial", 15),
    ("Alegações Finais", 15),
    ("Impugnação à Penhora", 15),

    # --- Atos Processuais e Eventos ---
    ("Audiência de Conciliação / Mediação", None),
    ("Audiência de Instrução e Julgamento", None),
    ("Despacho", None),
    ("Decisão Interlocutória", None),
    ("Sentença", None),
    ("Acórdão", None),
    ("Publicação / Intimação", None),
    ("Citação", None),
    ("Perícia Agendada", None),
    ("Trânsito em Julgado", None),
    ("Expedição de Alvará", None),
    ("Expedição de RPV/Precatório", None),

    # --- Tarefas Internas do Escritório ---
    ("Análise Inicial do Processo", None),
    ("Elaborar Petição Inicial", None),
    ("Elaborar Minuta de Contrato", None),
    ("Revisar Peça Processual", None),
    ("Contato com Cliente", None),
    ("Reunião com Cliente", None),
    ("Protocolo de Petição / Documentos", None),
    ("Alimentar Sistema do Cliente", None),
    ("Diligência Externa", None),
    ("Outra Tarefa Interna", None),
]

def popular_tipos_movimentacao(apps, schema_editor):
    """
    Esta função é executada pela migração para buscar o modelo
    e inserir os dados da lista acima no banco de dados.
    """
    TipoMovimentacao = apps.get_model('gestao', 'TipoMovimentacao')

    for nome, dias_prazo in TIPOS_DE_MOVIMENTACAO:
        TipoMovimentacao.objects.update_or_create(
            nome=nome,
            defaults={'sugestao_dias_prazo': dias_prazo}
        )

class Migration(migrations.Migration):

    dependencies = [
        ('gestao', '0014_cliente_bairro_cliente_cep_cliente_cidade_and_more'),
    ]

    operations = [
        migrations.RunPython(popular_tipos_movimentacao),
    ]
