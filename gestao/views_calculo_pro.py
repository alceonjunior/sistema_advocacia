# gestao/views_calculo_pro.py
import json
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from .services.indices.catalog import public_catalog_for_api

@login_required
def calculo_pro_view(request):
    """Renderiza a nova tela de cálculo Pro."""
    indices_catalog_json = json.dumps(public_catalog_for_api(), ensure_ascii=False)
    context = {
        'titulo_pagina': 'Cálculo Pro',
        'indices_catalog_json': indices_catalog_json
    }
    return render(request, 'gestao/calculo_pro.html', context)