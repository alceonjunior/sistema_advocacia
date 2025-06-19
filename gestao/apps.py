from django.apps import AppConfig


class GestaoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'gestao'

    def ready(self): # Adicione este método
        import gestao.signals
