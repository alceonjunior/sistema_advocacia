# gestao/apps.py

from django.apps import AppConfig
from django.db.backends.signals import connection_created
from unidecode import unidecode

def setup_sqlite_unaccent(connection, **kwargs):
    """
    Registra a função 'unaccent' no SQLite sempre que uma conexão é estabelecida.
    """
    if connection.vendor == 'sqlite':
        connection.connection.create_function('unaccent', 1, unidecode)


class GestaoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'gestao'

    def ready(self):
        """
        Executa rotinas de inicialização quando a aplicação está pronta.
        """
        # 1. Conecta a função de setup para o SQLite. (Mantenha isso)
        connection_created.connect(setup_sqlite_unaccent)

        # 2. Importa e registra os signals da aplicação. (Adicione esta linha)
        import gestao.signals