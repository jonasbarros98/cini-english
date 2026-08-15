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
    Lesson,
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

    elif field == wa.FIELD_TEMPLATE_STATUS:
        _apply_template_status(account, value)


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

    # A Meta recusa quando a contagem não bate, com um erro genérico que não
    # ajuda ninguém. Melhor dizer aqui exatamente o que falta.
    esperados = wa.count_template_variables(template.body_text)
    recebidos = len(body_params or [])
    if esperados != recebidos:
        raise WhatsAppSendError(
            f"O modelo '{template.name}' espera {esperados} informação(ões) "
            f"e recebeu {recebidos}."
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


# ---------------------------------------------------------------------------
# Modelos de mensagem
# ---------------------------------------------------------------------------

def sync_templates(account: WhatsAppAccount) -> dict:
    """
    Traz da Meta o estado dos modelos e reflete no banco.

    A Meta é a fonte da verdade de nome, corpo e aprovação. O `purpose`, que é
    a ligação com o uso interno (cobrança, lembrete), é nosso e nunca é
    sobrescrito por esta sincronização.
    """
    client = account.get_client()
    data = client.list_templates()

    resumo = {"criados": 0, "atualizados": 0}
    vistos = []

    for raw in data.get("data", []) or []:
        nome = raw.get("name", "")
        idioma = raw.get("language", "") or "pt_BR"
        if not nome:
            continue

        corpo = wa.extract_template_body(raw.get("components"))

        template, criado = WhatsAppTemplate.objects.get_or_create(
            account=account, name=nome, language=idioma,
            defaults={"purpose": WhatsAppTemplate.PURPOSE_OTHER},
        )

        template.status = (raw.get("status") or "").upper() or template.status
        template.category = (raw.get("category") or "").upper() or template.category
        template.body_text = corpo
        template.rejected_reason = raw.get("rejected_reason") or ""
        template.last_synced_at = timezone.now()

        # Só preenche as dicas de variável quando ainda não há nada escrito à
        # mão: o texto do professor é melhor do que "variável 1".
        quantas = wa.count_template_variables(corpo)
        if quantas and not template.variable_hints:
            template.variable_hints = [f"variável {i}" for i in range(1, quantas + 1)]

        template.save()
        vistos.append(template.id)
        resumo["criados" if criado else "atualizados"] += 1

    resumo["total"] = len(vistos)
    return resumo


def create_template(account: WhatsAppAccount, name: str, body_text: str,
                    purpose: str, category: str = WhatsAppTemplate.CATEGORY_UTILITY,
                    language: str = "pt_BR",
                    variable_hints: list | None = None,
                    example_params: list | None = None) -> WhatsAppTemplate:
    """
    Cria o modelo na Meta e guarda como pendente até ela responder.

    A aprovação chega depois, sozinha, pelo webhook
    `message_template_status_update`. Pode levar minutos ou dias.
    """
    name = (name or "").strip().lower().replace(" ", "_")
    if not name:
        raise WhatsAppSendError("Dê um nome ao modelo.")
    if not body_text.strip():
        raise WhatsAppSendError("Escreva o corpo do modelo.")

    quantas = wa.count_template_variables(body_text)
    exemplos = example_params or []
    if quantas and len(exemplos) != quantas:
        raise WhatsAppSendError(
            f"O corpo tem {quantas} variável(is), então precisa de {quantas} "
            f"exemplo(s). A Meta reprova modelo sem exemplo."
        )

    client = account.get_client()
    try:
        client.create_template(
            name=name, category=category, language=language,
            body_text=body_text, example_params=exemplos,
        )
    except wa.WhatsAppAPIError as exc:
        raise WhatsAppSendError(f"A Meta recusou o modelo: {exc.message}") from exc

    template, _ = WhatsAppTemplate.objects.update_or_create(
        account=account, name=name, language=language,
        defaults={
            "purpose": purpose,
            "category": category,
            "body_text": body_text,
            "status": WhatsAppTemplate.STATUS_PENDING,
            "variable_hints": variable_hints or [
                f"variável {i}" for i in range(1, quantas + 1)
            ],
            "rejected_reason": "",
            "last_synced_at": timezone.now(),
        },
    )
    return template


def _apply_template_status(account: WhatsAppAccount, value: dict) -> None:
    """
    Reflete o veredito da Meta sobre um modelo.

    Chega pelo webhook, sem a gente pedir. Se o modelo não existir aqui, é
    porque foi criado direto no painel da Meta: cria como 'outro', para
    aparecer na interface em vez de sumir.
    """
    nome = value.get("message_template_name", "")
    idioma = value.get("message_template_language", "") or "pt_BR"
    estado = (value.get("event") or "").upper()

    if not nome or not estado:
        return

    template, _ = WhatsAppTemplate.objects.get_or_create(
        account=account, name=nome, language=idioma,
        defaults={"purpose": WhatsAppTemplate.PURPOSE_OTHER},
    )

    template.status = estado
    template.rejected_reason = value.get("reason") or ""
    template.last_synced_at = timezone.now()
    template.save(update_fields=[
        "status", "rejected_reason", "last_synced_at", "updated_at",
    ])

    print(f"[WhatsApp] Modelo '{nome}' agora está {estado}")


def template_for(account: WhatsAppAccount, purpose: str) -> WhatsAppTemplate | None:
    """Modelo aprovado para um uso interno, ou None se ainda não houver."""
    return (
        WhatsAppTemplate.objects
        .filter(account=account, purpose=purpose,
                status=WhatsAppTemplate.STATUS_APPROVED)
        .first()
    )


# ---------------------------------------------------------------------------
# Fase 3: cobrança e lembrete de aula saindo do sistema
# ---------------------------------------------------------------------------

# Cada tipo de cobrança que já existe no BillingLog tem um modelo próprio.
BILLING_PURPOSE_BY_TYPE = {
    BillingLog.MESSAGE_TYPE_FRIENDLY: WhatsAppTemplate.PURPOSE_BILLING_FRIENDLY,
    BillingLog.MESSAGE_TYPE_DUE_TODAY: WhatsAppTemplate.PURPOSE_BILLING_DUE_TODAY,
    BillingLog.MESSAGE_TYPE_OVERDUE: WhatsAppTemplate.PURPOSE_BILLING_OVERDUE,
    BillingLog.MESSAGE_TYPE_THANK_YOU: WhatsAppTemplate.PURPOSE_BILLING_THANK_YOU,
}


def _money(valor) -> str:
    """Formata em real, no padrão que a professora escreveria à mão."""
    try:
        return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return str(valor or "")


@transaction.atomic
def send_billing_message(financial_entry, message_type: str, user,
                         free_text: str = "") -> tuple:
    """
    Envia a cobrança de verdade e registra no BillingLog.

    Escolhe sozinho como falar:

    - **Janela aberta e texto escrito:** manda o texto livre, que é de graça e
      soa como a professora.
    - **Janela fechada:** usa o modelo aprovado do tipo pedido, com nome, valor
      e vencimento preenchidos.

    Devolve (WhatsAppMessage, BillingLog). Levanta WhatsAppSendError com o
    motivo em português quando não dá para enviar.
    """
    aluno = financial_entry.student
    conversa = conversation_for_student(aluno)

    if not conversa:
        raise WhatsAppSendError(
            f"Não há WhatsApp cadastrado para {aluno.name}. "
            f"Confira o telefone na ficha do aluno."
        )

    texto = (free_text or "").strip()

    if conversa.window_is_open and texto:
        mensagem = send_text(conversa, texto, sent_by=user)
        conteudo = texto
    else:
        purpose = BILLING_PURPOSE_BY_TYPE.get(message_type)
        modelo = template_for(conversa.account, purpose) if purpose else None

        if not modelo:
            rotulo = dict(BillingLog.MESSAGE_TYPE_CHOICES).get(message_type, message_type)
            raise WhatsAppSendError(
                f"A janela de 24 horas está fechada e ainda não há modelo "
                f"aprovado para '{rotulo}'. Aprove um modelo na Meta, ou espere "
                f"{aluno.name} escrever para responder livremente."
            )

        # A ordem dos parâmetros segue as chaves {{1}}, {{2}}, {{3}} do corpo
        # aprovado: nome, valor, vencimento.
        parametros = [
            aluno.name,
            _money(getattr(financial_entry, "amount", None)),
            (financial_entry.due_date.strftime("%d/%m/%Y")
             if getattr(financial_entry, "due_date", None) else ""),
        ]
        esperados = wa.count_template_variables(modelo.body_text)
        parametros = parametros[:esperados]

        mensagem = send_template(
            conversa, modelo, body_params=parametros, sent_by=user,
        )
        conteudo = mensagem.body

    registro = BillingLog.objects.create(
        financial_entry=financial_entry,
        user=user,
        message_type=message_type,
        send_method=BillingLog.SEND_METHOD_WHATSAPP,
        message_content=conteudo,
    )

    # Liga os dois lados: a ficha do aluno passa a mostrar "cobrança enviada"
    # com o status de entrega vindo da Meta.
    mensagem.billing_log = registro
    mensagem.save(update_fields=["billing_log", "updated_at"])

    return mensagem, registro


@transaction.atomic
def send_lesson_reminder(lesson, user, hours_label: str = "") -> WhatsAppMessage:
    """
    Lembrete de aula, disparado a partir do calendário.

    Sempre por modelo: lembrete é mensagem que a escola inicia, e quase nunca
    cai dentro da janela de 24 horas.
    """
    aluno = getattr(lesson, "student", None)
    if not aluno:
        raise WhatsAppSendError("Esta aula não está ligada a um aluno.")

    conversa = conversation_for_student(aluno)
    if not conversa:
        raise WhatsAppSendError(
            f"Não há WhatsApp cadastrado para {aluno.name}."
        )

    modelo = template_for(conversa.account, WhatsAppTemplate.PURPOSE_LESSON_REMINDER)
    if not modelo:
        raise WhatsAppSendError(
            "Ainda não há modelo aprovado para lembrete de aula."
        )

    quando = hours_label
    if not quando and getattr(lesson, "date", None):
        hora = getattr(lesson, "time", None)
        quando = f"{lesson.date.strftime('%d/%m')}" + (
            f" às {hora.strftime('%H:%M')}" if hora else ""
        )

    parametros = [aluno.name, quando][:wa.count_template_variables(modelo.body_text)]

    mensagem = send_template(
        conversa, modelo, body_params=parametros, sent_by=user, lesson=lesson,
    )
    return mensagem
