"""
Views do canal WhatsApp.

Ficam num módulo próprio porque `core/views.py` já passa de oito mil linhas e
este assunto é autocontido: webhook da Meta e, adiante, a caixa de entrada.
"""

from __future__ import annotations

import json
import os

from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.generic import TemplateView

from core import whatsapp as wa
from core import whatsapp_service as service
from core import whatsapp_signup as signup
from core.models import (
    Student,
    WhatsAppContact,
    WhatsAppConversation,
    WhatsAppMessage,
    WhatsAppTemplate,
)


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


# ===========================================================================
# Caixa de entrada
# ===========================================================================

def _visible_conversations(user):
    """
    Conversas que este utilizador pode ver.

    O dono do número vê tudo, porque é a conta dele e a responsabilidade legal
    também. O professor parceiro vê só os alunos atribuídos a ele.
    """
    return (
        WhatsAppConversation.objects
        .filter(Q(account__user=user) | Q(assigned_teacher=user))
        .select_related("contact", "contact__student", "account", "assigned_teacher")
        .distinct()
    )


def _get_conversation_or_none(user, conversation_id):
    return _visible_conversations(user).filter(id=conversation_id).first()


def _require_login(request):
    """Devolve uma resposta de erro quando não há sessão, ou None."""
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Não autenticado."}, status=401)
    return None


def _serialize_conversation(conversation) -> dict:
    contact = conversation.contact
    expires = conversation.window_expires_at

    return {
        "id": conversation.id,
        "name": contact.display_name,
        "phone": contact.formatted_phone,
        "profile_name": contact.profile_name,
        "student_id": contact.student_id,
        "student_name": contact.student.name if contact.student_id else "",
        "relationship": contact.get_relationship_display(),
        "assigned_teacher": (
            conversation.assigned_teacher.get_full_name()
            or conversation.assigned_teacher.username
        ) if conversation.assigned_teacher_id else "",
        "assigned_teacher_id": conversation.assigned_teacher_id,
        "unread": conversation.unread_count,
        "preview": conversation.last_message_preview,
        "last_message_at": (
            conversation.last_message_at.isoformat()
            if conversation.last_message_at else None
        ),
        "window_open": conversation.window_is_open,
        "window_expires_at": expires.isoformat() if expires else None,
        "opt_in": contact.opt_in_status,
        "blocked": contact.is_blocked,
    }


def _serialize_message(message) -> dict:
    return {
        "id": message.id,
        "direction": message.direction,
        "origin": message.origin,
        "status": message.status,
        "type": message.message_type,
        "body": message.body,
        "media_mime": message.media_mime,
        "media_filename": message.media_filename,
        "template": message.template.name if message.template_id else "",
        "sent_by": (
            message.sent_by.get_full_name() or message.sent_by.username
        ) if message.sent_by_id else "",
        "error": message.error_message,
        "timestamp": message.timestamp.isoformat(),
    }


class WhatsAppInboxView(TemplateView):
    """Página da caixa de entrada."""

    template_name = "whatsapp_inbox.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("/login/")

        from core.views import _user_has_active_subscription

        if not _user_has_active_subscription(request.user):
            return redirect("planos")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        from core.models import UserProfile

        try:
            profile = self.request.user.profile
            context["is_partner_teacher"] = (
                profile.user_profile == UserProfile.PROFILE_PARTNER_TEACHER
            )
        except UserProfile.DoesNotExist:
            context["is_partner_teacher"] = False

        account = getattr(self.request.user, "whatsapp_account", None)
        # O parceiro não tem conta própria: usa o número do dono.
        if not account:
            conversation = _visible_conversations(self.request.user).first()
            account = conversation.account if conversation else None

        context["wa_account"] = account
        context["wa_enabled"] = wa.is_enabled()
        return context


@require_http_methods(["GET"])
def whatsapp_conversations(request):
    """Lista de conversas, já filtrada pelo que este professor pode ver."""
    if error := _require_login(request):
        return error

    conversations = _visible_conversations(request.user)

    busca = (request.GET.get("q") or "").strip()
    if busca:
        filtro = (
            Q(contact__profile_name__icontains=busca)
            | Q(contact__student__name__icontains=busca)
        )

        # O mesmo cuidado do nono dígito vale aqui: a professora digita o
        # número como o cadastrou, e o wa_id guardado pode estar na outra
        # forma. Buscar pela string crua acharia só metade dos contatos.
        variantes = wa.phone_variants(busca)
        for variante in variantes:
            filtro |= Q(contact__wa_id__icontains=variante)
            filtro |= Q(contact__phone_e164__icontains=variante)
        if not variantes:
            filtro |= Q(contact__wa_id__icontains=busca)

        conversations = conversations.filter(filtro)

    if request.GET.get("filter") == "unread":
        conversations = conversations.filter(unread_count__gt=0)
    elif request.GET.get("filter") == "unlinked":
        conversations = conversations.filter(contact__student__isnull=True)

    conversations = conversations.filter(is_archived=False)[:200]

    return JsonResponse({
        "conversations": [_serialize_conversation(c) for c in conversations],
        "server_time": timezone.now().isoformat(),
    })


@require_http_methods(["GET"])
def whatsapp_messages(request, conversation_id):
    """Mensagens de uma conversa, mais antigas primeiro."""
    if error := _require_login(request):
        return error

    conversation = _get_conversation_or_none(request.user, conversation_id)
    if not conversation:
        return JsonResponse({"detail": "Conversa não encontrada."}, status=404)

    messages = (
        conversation.messages
        .select_related("template", "sent_by")
        .order_by("-timestamp")[:200]
    )

    return JsonResponse({
        "conversation": _serialize_conversation(conversation),
        "messages": [_serialize_message(m) for m in reversed(list(messages))],
        "server_time": timezone.now().isoformat(),
    })


@require_http_methods(["POST"])
def whatsapp_send(request, conversation_id):
    """
    Envia uma resposta.

    Aceita texto livre dentro da janela e template fora dela. O erro que volta
    é o texto que a professora lê, então vale mais explicar do que codificar.
    """
    if error := _require_login(request):
        return error

    conversation = _get_conversation_or_none(request.user, conversation_id)
    if not conversation:
        return JsonResponse({"detail": "Conversa não encontrada."}, status=404)

    try:
        data = json.loads(request.body or b"{}")
    except ValueError:
        return JsonResponse({"detail": "Requisição inválida."}, status=400)

    template_id = data.get("template_id")

    try:
        if template_id:
            template = WhatsAppTemplate.objects.filter(
                id=template_id, account=conversation.account
            ).first()
            if not template:
                return JsonResponse({"detail": "Modelo não encontrado."}, status=404)

            message = service.send_template(
                conversation, template,
                body_params=data.get("params") or [],
                sent_by=request.user,
            )
        else:
            body = (data.get("body") or "").strip()
            if not body:
                return JsonResponse({"detail": "Escreva uma mensagem."}, status=400)

            message = service.send_text(conversation, body, sent_by=request.user)

    except service.WhatsAppSendError as exc:
        return JsonResponse({"detail": str(exc)}, status=422)

    return JsonResponse({
        "message": _serialize_message(message),
        "conversation": _serialize_conversation(conversation),
    })


@require_http_methods(["POST"])
def whatsapp_mark_read(request, conversation_id):
    if error := _require_login(request):
        return error

    conversation = _get_conversation_or_none(request.user, conversation_id)
    if not conversation:
        return JsonResponse({"detail": "Conversa não encontrada."}, status=404)

    service.mark_conversation_read(conversation)
    return JsonResponse({"ok": True})


@require_http_methods(["POST"])
def whatsapp_link_student(request, conversation_id):
    """
    Liga um contato solto a um aluno.

    Reatribui a conversa ao professor do aluno, senão o parceiro continua sem
    enxergar a conversa que passou a ser dele.
    """
    if error := _require_login(request):
        return error

    conversation = _get_conversation_or_none(request.user, conversation_id)
    if not conversation:
        return JsonResponse({"detail": "Conversa não encontrada."}, status=404)

    try:
        data = json.loads(request.body or b"{}")
    except ValueError:
        return JsonResponse({"detail": "Requisição inválida."}, status=400)

    student = Student.objects.filter(
        id=data.get("student_id"), user=conversation.account.user
    ).first()
    if not student:
        return JsonResponse({"detail": "Aluno não encontrado."}, status=404)

    service.link_contact_to_student(
        conversation.contact, student,
        relationship=data.get("relationship") or WhatsAppContact.RELATIONSHIP_GUARDIAN,
    )
    conversation.refresh_from_db()

    return JsonResponse({"conversation": _serialize_conversation(conversation)})


@require_http_methods(["POST"])
def whatsapp_set_opt_in(request, conversation_id):
    """Registra ou revoga a autorização de receber mensagens da escola."""
    if error := _require_login(request):
        return error

    conversation = _get_conversation_or_none(request.user, conversation_id)
    if not conversation:
        return JsonResponse({"detail": "Conversa não encontrada."}, status=404)

    try:
        data = json.loads(request.body or b"{}")
    except ValueError:
        return JsonResponse({"detail": "Requisição inválida."}, status=400)

    if data.get("granted"):
        conversation.contact.grant_opt_in(
            source=(data.get("source") or "registrado pela professora")
        )
    else:
        conversation.contact.revoke_opt_in(source="revogado pela professora")

    return JsonResponse({"conversation": _serialize_conversation(conversation)})


@require_http_methods(["GET"])
def whatsapp_templates(request):
    """Modelos aprovados, para quando a janela de 24 horas estiver fechada."""
    if error := _require_login(request):
        return error

    conversation = _visible_conversations(request.user).first()
    account = getattr(request.user, "whatsapp_account", None) or (
        conversation.account if conversation else None
    )

    if not account:
        return JsonResponse({"templates": []})

    templates = WhatsAppTemplate.objects.filter(
        account=account, status=WhatsAppTemplate.STATUS_APPROVED
    )

    return JsonResponse({
        "templates": [{
            "id": t.id,
            "name": t.name,
            "purpose": t.get_purpose_display(),
            "body": t.body_text,
            "variables": t.variable_hints,
        } for t in templates],
    })


# ===========================================================================
# Conexão do número (Embedded Signup)
# ===========================================================================

@require_http_methods(["GET"])
def whatsapp_signup_config(request):
    """
    Dados públicos que o popup da Meta precisa.

    Só o App ID e o Config ID, que não são segredo. O App Secret nunca sai do
    servidor.
    """
    if error := _require_login(request):
        return error

    return JsonResponse({
        "configured": signup.is_configured(),
        "app_id": signup.app_id(),
        "config_id": signup.config_id(),
        "feature_type": signup.feature_type(),
        "graph_version": wa.GRAPH_VERSION,
    })


@require_http_methods(["POST"])
def whatsapp_signup_complete(request):
    """
    Fecha a conexão com o código devolvido pelo popup.

    O código é de uso único e expira em minutos, então o trabalho todo
    acontece aqui, na mesma requisição.
    """
    if error := _require_login(request):
        return error

    # Professor parceiro usa o número do dono, não conecta o próprio.
    from core.models import UserProfile

    try:
        if request.user.profile.user_profile == UserProfile.PROFILE_PARTNER_TEACHER:
            return JsonResponse({
                "detail": "Quem conecta o número é o dono da conta.",
            }, status=403)
    except UserProfile.DoesNotExist:
        pass

    try:
        data = json.loads(request.body or b"{}")
    except ValueError:
        return JsonResponse({"detail": "Requisição inválida."}, status=400)

    try:
        account = signup.complete_signup(
            user=request.user,
            code=(data.get("code") or "").strip(),
            waba_id=(data.get("waba_id") or "").strip(),
            phone_number_id=(data.get("phone_number_id") or "").strip(),
        )
    except signup.SignupError as exc:
        return JsonResponse({"detail": str(exc)}, status=422)

    return JsonResponse({
        "connected": True,
        "phone": account.display_phone_number,
        "name": account.verified_name,
        "warning": account.last_error,
    })


@require_http_methods(["POST"])
def whatsapp_disconnect(request):
    """Desliga o canal sem apagar conversa nenhuma."""
    if error := _require_login(request):
        return error

    account = getattr(request.user, "whatsapp_account", None)
    if not account:
        return JsonResponse({"detail": "Nenhum número conectado."}, status=404)

    signup.disconnect(account)
    return JsonResponse({"connected": False})


@require_http_methods(["GET"])
def whatsapp_students_lookup(request):
    """Alunos da conta, para ligar a um contato solto."""
    if error := _require_login(request):
        return error

    conversation = _visible_conversations(request.user).first()
    account = getattr(request.user, "whatsapp_account", None) or (
        conversation.account if conversation else None
    )
    if not account:
        return JsonResponse({"students": []})

    busca = (request.GET.get("q") or "").strip()
    students = Student.objects.filter(user=account.user)
    if busca:
        students = students.filter(name__icontains=busca)

    return JsonResponse({
        "students": [
            {"id": s.id, "name": s.name, "phone": s.phone}
            for s in students.order_by("name")[:50]
        ],
    })
