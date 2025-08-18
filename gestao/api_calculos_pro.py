# gestao/api_calculos_pro.py
import json
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from .services.calculo_v2 import CalculoProEngine


@require_POST
@login_required
def preview_calculo_pro(request):
    """Endpoint da API para pré-visualização do cálculo."""
    try:
        payload = json.loads(request.body)
        if not payload.get('parcelas'):
            return JsonResponse({'ok': False, 'erro': 'Nenhuma parcela fornecida.'}, status=400)

        engine = CalculoProEngine(payload)
        resultado = engine.run_preview()

        return JsonResponse(resultado)

    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'erro': 'JSON inválido.'}, status=400)
    except Exception as e:
        # Em produção, logar o erro `e`
        return JsonResponse({'ok': False, 'erro': 'Erro interno no servidor.'}, status=500)


# Stubs para futuras implementações
@require_POST
@login_required
def replicar_parcelas(request):
    return JsonResponse({"ok": False, "erro": "Funcionalidade de replicação ainda não implementada."}, status=501)


@require_POST
@login_required
def batch_update_parcelas(request):
    return JsonResponse({"ok": False, "erro": "Funcionalidade de edição em lote ainda não implementada."}, status=501)