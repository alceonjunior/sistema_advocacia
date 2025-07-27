# config/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # 1. Rota para a área administrativa.
    path('admin/', admin.site.urls),

    # 2. Rota para as URLs de autenticação (login, logout, etc.).
    path('accounts/', include('django.contrib.auth.urls')),

    # 3. Rota para o CKEditor.
    path('ckeditor/', include('ckeditor_uploader.urls')),

    # 4. Rota principal que delega para o app 'gestao'.
    # A remoção do 'namespace' aqui resolve o conflito.
    path('', include('gestao.urls')),
]

# Bloco para servir arquivos de mídia em desenvolvimento.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)