# gestao/signals.py - VERSÃO CORRIGIDA

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings # Importe 'settings'
from .models import UsuarioPerfil # Importe seu modelo de Perfil

# Em vez de importar o modelo User, usamos a string do settings.AUTH_USER_MODEL
# para nos conectarmos ao sinal. Esta é a melhor prática.
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Cria um Perfil de Usuário automaticamente sempre que um novo
    usuário do tipo definido em AUTH_USER_MODEL é criado.
    """
    if created:
        UsuarioPerfil.objects.create(user=instance)