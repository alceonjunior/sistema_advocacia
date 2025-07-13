# gestao/apps.py

from django.apps import AppConfig
from django.db.backends.signals import connection_created
from unidecode import unidecode

def setup_sqlite_unaccent(connection, **kwargs):
    """
    Registra a função 'unaccent' no SQLite sempre que uma conexão é estabelecida.
    """
    if connection.vendor == 'sqlite':
        # --- CORREÇÃO APLICADA AQUI ---
        # A função create_function é chamada no objeto de conexão real, e não no wrapper do Django.
        connection.connection.create_function('unaccent', 1, unidecode)


class GestaoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'gestao'

    def ready(self):
        """
        Conecta a nossa função de setup ao sinal de criação de conexão do Django.
        """
        connection_created.connect(setup_sqlite_unaccent)