"""
Views do canal WhatsApp.

Ficam num módulo próprio porque `core/views.py` já passa de oito mil linhas e
este assunto é autocontido: webhook da Meta e, adiante, a caixa de entrada.
"""

from __future__ import annotations

import json
import os

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from core import whatsapp as wa
from core import whatsapp_service as service


@csrf_exempt
@require_http_methods(["GET", "POST"])
def whatsapp_webhook(request):
    """
    Ponto único de entrada dos eventos da Meta.

    GET  handshake de verificação, feito uma vez ao cadastrar a URL.
    POST eventos: mensagens recebidas, status de entrega, e os echoes do
         aplicativo do celular.

    Devolve 200 em quase tudo de propósito. Erro diferente de 200 faz a Meta
    reentregar o lote inteiro em escala crescente e, se persistir, desativar a
    assinatura do webhook. O que falhar fica guardado em WhatsAppWebhookEvent
    para reprocessar sem depender da reentrega.
    """
    if request.method == "GET":
        return _handle_verification(request)

    app_secret = os.environ.get("WHATSAPP_APP_SECRET", "").strip()
    signature = request.META.get("HTTP_X_HUB_SIGNATURE_256", "")

    if not app_secret:
        print("[WhatsApp] WHATSAPP_APP_SECRET não configurado, webhook recusado")
        return HttpResponse("app secret ausente", status=500)

    # A assinatura é sobre o corpo cru. Reserializar o JSON quebra a conferência.
    if not wa.verify_webhook_signature(request.body, signature, app_secret):
        print("[WhatsApp] Assinatura inválida no webhook")
        return HttpResponse("assinatura inválida", status=403)

    try:
        payload = json.loads(request.body or b"{}")
    except ValueError:
        print("[WhatsApp] Corpo do webhook não é JSON válido")
        return HttpResponse("ok", status=200)

    if not wa.is_enabled():
        # Canal desligado no ambiente: confirma o recebimento sem processar,
        # senão a Meta fica reentregando enquanto o piloto não sobe.
        return HttpResponse("ok", status=200)

    summary = service.process_webhook(payload)

    if summary["errors"] or summary["ignored"]:
        print(f"[WhatsApp] Webhook: {summary}")

    return HttpResponse("ok", status=200)


def _handle_verification(request):
    """
    Handshake do cadastro da URL do webhook.

    A Meta chama com hub.verify_token e espera o hub.challenge de volta em
    texto puro. Qualquer coisa diferente disso reprova o cadastro.
    """
    expected = os.environ.get("WHATSAPP_WEBHOOK_VERIFY_TOKEN", "").strip()
    mode = request.GET.get("hub.mode", "")
    token = request.GET.get("hub.verify_token", "")
    challenge = request.GET.get("hub.challenge", "")

    if not expected:
        print("[WhatsApp] WHATSAPP_WEBHOOK_VERIFY_TOKEN não configurado")
        return HttpResponse("verify token ausente", status=500)

    if mode == "subscribe" and token == expected:
        print("[WhatsApp] Webhook verificado pela Meta")
        return HttpResponse(challenge, content_type="text/plain", status=200)

    print(f"[WhatsApp] Verificação recusada (mode={mode!r})")
    return HttpResponse("token inválido", status=403)


@require_http_methods(["GET"])
def whatsapp_account_status(request):
    """
    Estado da conta conectada, para a interface e para diagnóstico.

    Não expõe token nem identificadores internos da Meta: a resposta serve
    para a professora saber se o canal está de pé, não para depurar a conta.
    """
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Não autenticado."}, status=401)

    account = getattr(request.user, "whatsapp_account", None)

    if not account:
        return JsonResponse({
            "connected": False,
            "enabled": wa.is_enabled(),
        })

    return JsonResponse({
        "connected": account.status == account.STATUS_CONNECTED,
        "enabled": wa.is_enabled(),
        "active": account.is_active,
        "can_send": account.can_send,
        "status": account.status,
        "phone": account.display_phone_number,
        "name": account.verified_name,
        "coexistence": account.is_coexistence,
        "quality_rating": account.quality_rating,
        "messaging_limit": account.messaging_limit,
        "last_error": account.last_error if account.status == account.STATUS_ERROR else "",
    })
