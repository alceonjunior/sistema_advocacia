"""
URL configuration for sistema_advocacia project.

[...]
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include  # Garanta que 'include' está aqui


urlpatterns = [
    path('admin/', admin.site.urls),

    # =======================================================================
    # ↓↓↓ ADICIONE ESTA LINHA AQUI ↓↓↓
    # =======================================================================
    # Inclui as URLs de autenticação padrão do Django (login, logout, etc.)
    # Agora a tag {% url 'logout' %} funcionará.
    path('accounts/', include('django.contrib.auth.urls')),
    # =======================================================================

    # Rota principal que direciona para as URLs do seu app
    path('', include('gestao.urls')),
    path('ckeditor/', include('ckeditor_uploader.urls')),

]

# Bloco para servir arquivos de mídia (sem alterações)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)