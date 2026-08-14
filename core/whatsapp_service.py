"""
Regras do canal WhatsApp que tocam o banco.

Divisão: `core/whatsapp.py` fala com a Meta e não conhece modelos;
este módulo conhece modelos e não fala HTTP direto. As views chamam daqui.
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from core import whatsapp as wa
from core.models import (
    BillingLog,
    Student,
    WhatsAppAccount,
    WhatsAppContact,
    WhatsAppConversation,
    WhatsAppMessage,
    WhatsAppTemplate,
    WhatsAppWebhookEvent,
)


class WhatsAppSendError(Exception):
    """Erro de negócio no envio, já traduzido para o que a professora entende."""


# ---------------------------------------------------------------------------
# Resolução de conta, contato e conversa
# ---------------------------------------------------------------------------

def resolve_account(phone_number_id: str) -> WhatsAppAccount | None:
    """Acha a conta dona do evento pelo número que a Meta identificou."""
    if not phone_number_id:
        return None
    return WhatsAppAccount.objects.filter(phone_number_id=phone_number_id).first()


def match_student(account: WhatsAppAccount, phone: str) -> Student | None:
    """
    Procura o aluno pelo telefone, aceitando o número com e sem o nono dígito.

    Varre só os alunos do dono da conta. É uma varredura em Python porque
    Student.phone é texto livre, escrito à mão pela professora: "(41) 98836-9627",
    "41988369627", "41 8836 9627 (mãe)". Comparar no banco exigiria normalizar
    o cadastro inteiro, o que fica para quando o volume justificar.
    """
    variants = set(wa.phone_variants(phone))
    if not variants:
        return None

    candidates = (
        Student.objects
        .filter(user=account.user)
        .exclude(phone="")
        .only("id", "name", "phone", "assigned_teacher_id", "user_id")
    )

    for student in candidates:
        if variants & set(wa.phone_variants(student.phone)):
            return student

    return None


@transaction.atomic
def get_or_create_contact(account: WhatsAppAccount, wa_id: str,
                          profile_name: str = "") -> WhatsAppContact:
    """
    Devolve o contato do número, criando na primeira mensagem.

    O contato nasce mesmo sem aluno: é comum o responsável escrever antes de a
    professora cadastrar o filho, e perder essa conversa seria pior do que ter
    um contato solto na caixa de entrada.
    """
    contact = WhatsAppContact.objects.filter(account=account, wa_id=wa_id).first()

    if contact:
        # O nome do perfil muda quando a pessoa troca no WhatsApp.
        if profile_name and contact.profile_name != profile_name:
            contact.profile_name = profile_name[:255]
            contact.save(update_fields=["profile_name", "updated_at"])
        return contact

    e164 = wa.normalize_phone(wa_id)
    student = match_student(account, wa_id)

    contact = WhatsAppContact.objects.create(
        account=account,
        wa_id=wa_id,
        phone_e164=e164,
        profile_name=(profile_name or "")[:255],
        student=student,
        relationship=(
            WhatsAppContact.RELATIONSHIP_GUARDIAN if student
            else WhatsAppContact.RELATIONSHIP_UNKNOWN
        ),
    )
    return contact


@transaction.atomic
def get_or_create_conversation(contact: WhatsAppContact) -> WhatsAppConversation:
    """Devolve a thread do contato, já com o professor responsável definido."""
    conversation = WhatsAppConversation.objects.filter(contact=contact).first()
    if conversation:
        return conversation

    conversation = WhatsAppConversation.objects.create(
        account=contact.account,
        contact=contact,
    )
    conversation.assigned_teacher = conversation.resolve_assigned_teacher()
    conversation.save(update_fields=["assigned_teacher", "updated_at"])
    return conversation


def link_contact_to_student(contact: WhatsAppContact, student: Student,
                            relationship: str = WhatsAppContact.RELATIONSHIP_GUARDIAN
                            ) -> WhatsAppContact:
    """
    Liga um contato solto a um aluno, feito à mão na caixa de entrada.

    Reatribui a conversa ao professor do aluno, senão o parceiro continua sem
    enxergar a conversa que passou a ser dele.
    """
    contact.student = student
    contact.relationship = relationship
    contact.save(update_fields=["student", "relationship", "updated_at"])

    conversation = get_or_create_conversation(contact)
    conversation.assigned_teacher = conversation.resolve_assigned_teacher()
    conversation.save(update_fields=["assigned_teacher", "updated_at"])

    return contact


# ---------------------------------------------------------------------------
# Entrada: webhook
# ---------------------------------------------------------------------------

def process_webhook(payload: dict) -> dict:
    """
    Processa um POST inteiro do webhook.

    Nunca levanta: a Meta reentrega tudo quando não recebe 200, e uma exceção
    num evento derrubaria os outros do mesmo lote. Cada mudança é isolada e o
    que falhar fica registrado em WhatsAppWebhookEvent.error_message.
    """
    summary = {"processed": 0, "duplicated": 0, "ignored": 0, "errors": 0}

    for entry_id, field, value in wa.iter_changes(payload):
        account = resolve_account(wa.extract_phone_number_id(value))

        if not account:
            summary["ignored"] += 1
            print(f"[WhatsApp] Evento de número desconhecido: "
                  f"{wa.extract_phone_number_id(value)!r}")
            continue

        event_key = wa.webhook_event_key(entry_id, field, value)

        event, created = WhatsAppWebhookEvent.objects.get_or_create(
            event_key=event_key,
            defaults={"account": account, "payload": value},
        )
        if not created and event.processed:
            summary["duplicated"] += 1
            continue

        try:
            _process_change(account, field, value)
            event.processed = True
            event.processed_at = timezone.now()
            event.error_message = ""
            event.save(update_fields=["processed", "processed_at", "error_message"])
            summary["processed"] += 1
        except Exception as exc:  # noqa: BLE001 - resiliência é o ponto aqui
            event.error_message = str(exc)[:2000]
            event.save(update_fields=["error_message"])
            summary["errors"] += 1
            print(f"[WhatsApp] Falha ao processar evento {event_key[:12]}: {exc}")

    return summary


def _process_change(account: WhatsAppAccount, field: str, value: dict) -> None:
    """Encaminha a mudança para o tratador do tipo dela."""
    if field in (wa.FIELD_MESSAGES, wa.FIELD_HISTORY):
        profiles = _profile_names(value)

        for raw in value.get("messages", []) or []:
            _record_inbound(account, raw, profiles)

        for raw in value.get("statuses", []) or []:
            _apply_status(account, raw)

    elif field == wa.FIELD_ECHOES:
        for raw in value.get("message_echoes", []) or []:
            _record_echo(account, raw)

    elif field == wa.FIELD_APP_STATE:
        _sync_contacts(account, value)


def _profile_names(value: dict) -> dict:
    """Mapa wa_id -> nome do perfil, que vem separado das mensagens."""
    names = {}
    for contact in value.get("contacts", []) or []:
        wa_id = contact.get("wa_id", "")
        name = ((contact.get("profile") or {}).get("name") or "")
        if wa_id:
            names[wa_id] = name
    return names


@transaction.atomic
def _record_inbound(account: WhatsAppAccount, raw: dict, profiles: dict) -> None:
    """Registra uma mensagem recebida e reabre a janela de 24 horas."""
    parsed = wa.parse_message(raw)
    wamid = parsed["wamid"]
    if not wamid:
        return

    if WhatsAppMessage.objects.filter(wamid=wamid).exists():
        return

    contact = get_or_create_contact(
        account, parsed["from"], profiles.get(parsed["from"], "")
    )
    conversation = get_or_create_conversation(contact)
    when = wa.parse_timestamp(parsed["timestamp"])

    WhatsAppMessage.objects.create(
        conversation=conversation,
        wamid=wamid,
        direction=WhatsAppMessage.DIRECTION_INBOUND,
        origin=WhatsAppMessage.ORIGIN_CONTACT,
        status=WhatsAppMessage.STATUS_RECEIVED,
        message_type=parsed["type"] or "text",
        body=parsed["body"],
        media_id=parsed["media_id"],
        media_mime=parsed["media_mime"],
        media_filename=parsed["media_filename"],
        reply_to_wamid=parsed["reply_to_wamid"],
        timestamp=when,
    )

    # Mensagem recebida é o que abre a janela de 24h para responder pela API.
    if not conversation.last_inbound_at or when > conversation.last_inbound_at:
        conversation.last_inbound_at = when

    conversation.last_message_at = when
    conversation.last_message_preview = (parsed["body"] or f"[{parsed['type']}]")[:200]
    conversation.unread_count = (conversation.unread_count or 0) + 1
    conversation.save(update_fields=[
        "last_inbound_at", "last_message_at", "last_message_preview",
        "unread_count", "updated_at",
    ])

    _check_opt_out(contact, parsed["body"])


@transaction.atomic
def _record_echo(account: WhatsAppAccount, raw: dict) -> None:
    """
    Registra o que a professora enviou pelo aplicativo do celular.

    Sem isto a caixa de entrada mostra só o lado do contato, e a professora
    responde duas vezes a mesma pergunta.
    """
    parsed = wa.parse_echo(raw)
    wamid = parsed["wamid"]
    if not wamid:
        return

    # Apagar e editar se referem a uma mensagem que já existe aqui.
    original_id = parsed.get("original_message_id")
    if original_id:
        original = WhatsAppMessage.objects.filter(wamid=original_id).first()
        if original:
            original.body = parsed["body"]
            original.save(update_fields=["body", "updated_at"])
        return

    if WhatsAppMessage.objects.filter(wamid=wamid).exists():
        return

    contact = get_or_create_contact(account, parsed["to"])
    conversation = get_or_create_conversation(contact)
    when = wa.parse_timestamp(parsed["timestamp"])

    WhatsAppMessage.objects.create(
        conversation=conversation,
        wamid=wamid,
        direction=WhatsAppMessage.DIRECTION_OUTBOUND,
        origin=WhatsAppMessage.ORIGIN_APP,
        status=WhatsAppMessage.STATUS_SENT,
        message_type=parsed["type"] or "text",
        body=parsed["body"],
        media_id=parsed["media_id"],
        media_mime=parsed["media_mime"],
        media_filename=parsed["media_filename"],
        timestamp=when,
    )

    conversation.last_message_at = when
    conversation.last_message_preview = (parsed["body"] or f"[{parsed['type']}]")[:200]
    # A professora já respondeu no celular, então não há o que ler aqui.
    conversation.unread_count = 0
    conversation.save(update_fields=[
        "last_message_at", "last_message_preview", "unread_count", "updated_at",
    ])


def _apply_status(account: WhatsAppAccount, raw: dict) -> None:
    """Atualiza entrega e leitura de uma mensagem que saiu pelo sistema."""
    wamid = raw.get("id", "")
    status = raw.get("status", "")
    if not wamid or not status:
        return

    message = WhatsAppMessage.objects.filter(wamid=wamid).first()
    if not message:
        return

    # A ordem de chegada não é garantida: um 'sent' atrasado não pode
    # rebaixar uma mensagem que já foi marcada como lida.
    rank = {
        WhatsAppMessage.STATUS_QUEUED: 0,
        WhatsAppMessage.STATUS_SENT: 1,
        WhatsAppMessage.STATUS_DELIVERED: 2,
        WhatsAppMessage.STATUS_READ: 3,
    }
    if status == "failed":
        message.status = WhatsAppMessage.STATUS_FAILED
        errors = raw.get("errors") or []
        if errors:
            message.error_code = str(errors[0].get("code", ""))[:20]
            message.error_message = (
                errors[0].get("title") or errors[0].get("message") or ""
            )[:2000]
    elif rank.get(status, -1) > rank.get(message.status, -1):
        message.status = status
    else:
        return

    message.save(update_fields=["status", "error_code", "error_message", "updated_at"])


def _sync_contacts(account: WhatsAppAccount, value: dict) -> None:
    """Recebe os contatos que vieram da agenda do aplicativo."""
    for raw in value.get("contacts", []) or []:
        wa_id = raw.get("wa_id") or raw.get("phone_number") or ""
        if not wa_id:
            continue
        name = ((raw.get("profile") or {}).get("name")
                or (raw.get("name") or {}).get("formatted_name") or "")
        get_or_create_contact(account, wa.normalize_phone(wa_id) or wa_id, name)


# Palavras que, sozinhas numa mensagem, significam "pare de me mandar coisa".
# Verificar isto é obrigação da Meta e evita denúncia, que derruba a
# qualidade do número.
_OPT_OUT_WORDS = {
    "sair", "parar", "pare", "cancelar", "descadastrar", "remover",
    "stop", "unsubscribe", "nao quero", "não quero",
}


def _check_opt_out(contact: WhatsAppContact, body: str) -> None:
    if not body:
        return
    normalized = body.strip().lower().rstrip(".!")
    if normalized in _OPT_OUT_WORDS:
        contact.revoke_opt_in(source="pedido do contato no WhatsApp")
        print(f"[WhatsApp] Opt-out registrado para {contact.wa_id}")


# ---------------------------------------------------------------------------
# Saída: envio
# ---------------------------------------------------------------------------

def _guard_send(conversation: WhatsAppConversation) -> None:
    account = conversation.account
    if not account.can_send:
        raise WhatsAppSendError(
            "O canal WhatsApp não está ativo nesta conta."
        )
    if conversation.contact.is_blocked:
        raise WhatsAppSendError(
            f"{conversation.contact.display_name} está bloqueado para envios."
        )


@transaction.atomic
def send_text(conversation: WhatsAppConversation, body: str,
              sent_by=None) -> WhatsAppMessage:
    """
    Responde em texto livre. Só funciona dentro da janela de 24 horas.

    Fora da janela a Meta recusa, e o certo é o chamador oferecer um template
    em vez de tentar e falhar na cara da professora.
    """
    _guard_send(conversation)

    if not conversation.window_is_open:
        expires = conversation.window_expires_at
        raise WhatsAppSendError(
            "A janela de 24 horas fechou"
            + (f" em {timezone.localtime(expires):%d/%m às %H:%M}" if expires else "")
            + ". Para falar agora só com uma mensagem modelo aprovada."
        )

    client = conversation.account.get_client()
    try:
        result = client.send_text(conversation.contact.wa_id, body)
    except wa.WhatsAppAPIError as exc:
        conversation.account.register_error(str(exc))
        if exc.is_auth_error:
            raise WhatsAppSendError(
                "A conexão com o WhatsApp expirou. É preciso reconectar o número."
            ) from exc
        raise WhatsAppSendError(f"A Meta recusou o envio: {exc.message}") from exc

    return _record_outbound(
        conversation, result["wamid"], body, "text", sent_by=sent_by
    )


@transaction.atomic
def send_template(conversation: WhatsAppConversation,
                  template: WhatsAppTemplate,
                  body_params: list | None = None,
                  sent_by=None,
                  billing_log: BillingLog | None = None,
                  lesson=None,
                  require_opt_in: bool = True) -> WhatsAppMessage:
    """
    Envia mensagem modelo. É o único caminho fora da janela de 24 horas.

    `require_opt_in` só deve ser desligado para o próprio pedido de
    autorização, que por definição vai para quem ainda não autorizou.
    """
    _guard_send(conversation)

    if not template.is_usable:
        raise WhatsAppSendError(
            f"O modelo '{template.name}' não está aprovado pela Meta "
            f"(estado: {template.get_status_display()})."
        )

    if require_opt_in and not conversation.contact.can_receive_template:
        raise WhatsAppSendError(
            f"{conversation.contact.display_name} ainda não autorizou receber "
            f"mensagens iniciadas pela escola."
        )

    client = conversation.account.get_client()
    try:
        result = client.send_template(
            to=conversation.contact.wa_id,
            template_name=template.name,
            language=template.language,
            body_params=body_params or [],
        )
    except wa.WhatsAppAPIError as exc:
        conversation.account.register_error(str(exc))
        if exc.is_auth_error:
            raise WhatsAppSendError(
                "A conexão com o WhatsApp expirou. É preciso reconectar o número."
            ) from exc
        raise WhatsAppSendError(f"A Meta recusou o envio: {exc.message}") from exc

    preview = _render_template_preview(template, body_params or [])

    return _record_outbound(
        conversation, result["wamid"], preview, "template",
        sent_by=sent_by, template=template,
        billing_log=billing_log, lesson=lesson,
    )


def _render_template_preview(template: WhatsAppTemplate, params: list) -> str:
    """
    Monta o texto que a professora vê na caixa de entrada.

    A Meta não devolve o corpo renderizado, então guardamos a substituição das
    chaves {{1}}, {{2}}... para o histórico não virar uma lista de nomes de
    template sem sentido.
    """
    body = template.body_text or template.name
    for index, value in enumerate(params, start=1):
        body = body.replace(f"{{{{{index}}}}}", str(value))
    return body


def _record_outbound(conversation: WhatsAppConversation, wamid: str, body: str,
                     message_type: str, sent_by=None,
                     template: WhatsAppTemplate | None = None,
                     billing_log: BillingLog | None = None,
                     lesson=None) -> WhatsAppMessage:
    now = timezone.now()

    message = WhatsAppMessage.objects.create(
        conversation=conversation,
        wamid=wamid or f"local-{now.timestamp()}",
        direction=WhatsAppMessage.DIRECTION_OUTBOUND,
        origin=WhatsAppMessage.ORIGIN_API,
        status=WhatsAppMessage.STATUS_SENT,
        message_type=message_type,
        body=body,
        template=template,
        sent_by=sent_by,
        billing_log=billing_log,
        lesson=lesson,
        timestamp=now,
    )

    conversation.last_message_at = now
    conversation.last_message_preview = (body or "")[:200]
    conversation.unread_count = 0
    conversation.save(update_fields=[
        "last_message_at", "last_message_preview", "unread_count", "updated_at",
    ])

    return message


def mark_conversation_read(conversation: WhatsAppConversation) -> None:
    """
    Zera o não lido aqui e avisa a Meta.

    Em coexistence isto também limpa o não lido no celular da professora, o que
    evita ela reabrir uma conversa já respondida pelo sistema.
    """
    last_inbound = (
        conversation.messages
        .filter(direction=WhatsAppMessage.DIRECTION_INBOUND)
        .order_by("-timestamp")
        .first()
    )

    conversation.unread_count = 0
    conversation.save(update_fields=["unread_count", "updated_at"])

    if last_inbound and conversation.account.can_send:
        try:
            conversation.account.get_client().mark_as_read(last_inbound.wamid)
        except wa.WhatsAppAPIError as exc:
            # Falhar em marcar como lida não pode travar a interface.
            print(f"[WhatsApp] Não foi possível marcar como lida: {exc}")


# ---------------------------------------------------------------------------
# Atalhos usados pelo resto do sistema
# ---------------------------------------------------------------------------

def conversation_for_student(student: Student) -> WhatsAppConversation | None:
    """
    Acha por onde falar com um aluno.

    Prefere o contato do responsável, que é quem paga e quem responde sobre
    dinheiro. Cai para qualquer contato ligado ao aluno.
    """
    account = WhatsAppAccount.objects.filter(user=student.user).first()
    if not account:
        return None

    contact = (
        WhatsAppContact.objects
        .filter(account=account, student=student, is_blocked=False)
        .order_by("-relationship")  # 'guardian' vem antes de 'student'
        .first()
    )

    if not contact:
        # Aluno cadastrado que nunca escreveu: cria o contato a partir do
        # telefone da ficha, para o primeiro template poder sair daqui.
        e164 = wa.normalize_phone(student.phone)
        if not e164:
            return None
        contact = get_or_create_contact(account, e164)
        if not contact.student_id:
            link_contact_to_student(contact, student)

    return get_or_create_conversation(contact)


def template_for(account: WhatsAppAccount, purpose: str) -> WhatsAppTemplate | None:
    """Modelo aprovado para um uso interno, ou None se ainda não houver."""
    return (
        WhatsAppTemplate.objects
        .filter(account=account, purpose=purpose,
                status=WhatsAppTemplate.STATUS_APPROVED)
        .first()
    )
