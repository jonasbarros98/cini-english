"""
Conexão do número pelo Embedded Signup da Meta.

É o único caminho: a coexistência não é liberada por cadastro manual no painel.
O professor clica em conectar, passa por um popup da Meta que cria o Business
Manager e a WABA dele, e devolve um código. O resto acontece aqui.

O fluxo, em ordem:

  1. O popup devolve um `code` e o `waba_id` do cliente.
  2. Trocamos o código por um token de acesso de longa duração.
  3. Assinamos a nossa app à WABA dele, para os webhooks passarem a chegar.
  4. Descobrimos o número: no fluxo de coexistência o popup manda só o
     `waba_id`, então o `phone_number_id` vem de uma consulta.
  5. **Não registramos o número.** Ele já está registrado no aplicativo do
     celular, e chamar `/register` aqui quebraria a coexistência.
  6. Disparamos a importação de contatos e de histórico, que tem janela de
     24 horas e não se repete.

Referência: Meta for Developers, "Onboard WhatsApp Business app users".
"""

from __future__ import annotations

import os

from django.db import transaction
from django.utils import timezone

from core import whatsapp as wa
from core.models import WhatsAppAccount

# Tipos de sincronização aceitos pela Meta depois do onboarding.
SYNC_CONTACTS = "smb_app_state_sync"
SYNC_HISTORY = "history"

# Campos que precisamos receber na WABA do cliente. Os três últimos são o que
# faz a coexistência valer: sem eles, o que a professora escreve no celular
# nunca chega ao sistema.
WEBHOOK_FIELDS = [
    "messages",
    "smb_message_echoes",
    "smb_app_state_sync",
    "history",
    "message_template_status_update",
]


class SignupError(Exception):
    """Falha na conexão, já em texto que o professor entende."""


def is_configured() -> bool:
    """A app da Meta está configurada neste ambiente?"""
    return bool(app_id() and config_id() and app_secret())


def app_id() -> str:
    return os.environ.get("WHATSAPP_APP_ID", "").strip()


def config_id() -> str:
    """ID da configuração do Embedded Signup, criada no painel da Meta."""
    return os.environ.get("WHATSAPP_CONFIG_ID", "").strip()


def app_secret() -> str:
    return os.environ.get("WHATSAPP_APP_SECRET", "").strip()


def feature_type() -> str:
    """
    Variante do Embedded Signup pedida ao popup.

    `whatsapp_business_app_onboarding` é o que oferece a coexistência ao
    professor. Fica em variável porque a Meta às vezes move esta escolha para
    dentro da própria configuração, e aí o valor precisa ir vazio.
    """
    return os.environ.get(
        "WHATSAPP_ES_FEATURE_TYPE", "whatsapp_business_app_onboarding"
    ).strip()


# ---------------------------------------------------------------------------
# Chamadas à Graph API feitas com o token da nossa app, não o do cliente
# ---------------------------------------------------------------------------

def _graph(method: str, path: str, *, token: str = "",
           params: dict | None = None, json_body: dict | None = None) -> dict:
    import requests

    url = f"{wa.GRAPH_BASE_URL}/{path.lstrip('/')}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        response = requests.request(
            method, url, headers=headers, params=params,
            json=json_body, timeout=wa.REQUEST_TIMEOUT,
        )
    except Exception as exc:
        raise SignupError(f"Não foi possível falar com a Meta: {exc}") from exc

    try:
        data = response.json() if response.content else {}
    except ValueError:
        data = {}

    if response.status_code >= 400:
        error = (data or {}).get("error", {}) or {}
        raise SignupError(
            error.get("message") or f"A Meta recusou a conexão (HTTP {response.status_code})."
        )

    return data


def exchange_code(code: str) -> str:
    """
    Troca o código do popup por um token de acesso de longa duração.

    O código é de uso único e expira em minutos, então isto tem de acontecer
    na mesma requisição em que ele chega.
    """
    if not code:
        raise SignupError("A Meta não devolveu o código de autorização.")

    data = _graph("GET", "oauth/access_token", params={
        "client_id": app_id(),
        "client_secret": app_secret(),
        "code": code,
    })

    token = data.get("access_token", "")
    if not token:
        raise SignupError("A Meta não devolveu um token de acesso.")
    return token


def subscribe_app_to_waba(waba_id: str, token: str) -> None:
    """
    Assina a nossa app à WABA do cliente.

    Sem isto o webhook nunca dispara para este número, e a caixa de entrada
    fica muda sem dar erro nenhum.
    """
    _graph("POST", f"{waba_id}/subscribed_apps", token=token)


def list_phone_numbers(waba_id: str, token: str) -> list[dict]:
    """
    Números da WABA do cliente.

    No fluxo de coexistência o popup devolve só o `waba_id`, então o
    `phone_number_id` sai daqui.
    """
    data = _graph("GET", f"{waba_id}/phone_numbers", token=token, params={
        "fields": "id,display_phone_number,verified_name,quality_rating,"
                  "code_verification_status,platform_type",
    })
    return data.get("data", []) or []


def trigger_sync(phone_number_id: str, token: str, sync_type: str) -> None:
    """
    Pede à Meta a importação dos contatos e do histórico do aplicativo.

    Janela de 24 horas depois do onboarding, e não se repete. Falhar aqui não
    invalida a conexão: as conversas novas continuam chegando, só o passado
    não vem junto.
    """
    _graph("POST", f"{phone_number_id}/smb_app_data", token=token,
           json_body={"messaging_product": "whatsapp", "sync_type": sync_type})


# ---------------------------------------------------------------------------
# Orquestração
# ---------------------------------------------------------------------------

def _pick_phone_number(numbers: list[dict], preferred_id: str = "") -> dict:
    """
    Escolhe o número conectado.

    Quase sempre há um só. Quando o popup já informou qual, respeitamos.
    """
    if not numbers:
        raise SignupError(
            "A conta da Meta foi criada, mas nenhum número apareceu nela. "
            "Confira se o número foi selecionado durante a conexão."
        )

    if preferred_id:
        for number in numbers:
            if number.get("id") == preferred_id:
                return number

    return numbers[0]


@transaction.atomic
def complete_signup(user, code: str, waba_id: str,
                    phone_number_id: str = "") -> WhatsAppAccount:
    """
    Fecha a conexão e devolve a conta pronta para usar.

    Idempotente do lado do professor: reconectar substitui o token e os
    identificadores sem duplicar conta nem perder as conversas já guardadas.
    """
    if not is_configured():
        raise SignupError(
            "A integração com a Meta ainda não está configurada neste ambiente."
        )

    if not waba_id:
        raise SignupError("A Meta não informou a conta de negócio (WABA).")

    token = exchange_code(code)
    subscribe_app_to_waba(waba_id, token)

    numero = _pick_phone_number(list_phone_numbers(waba_id, token), phone_number_id)
    numero_id = numero.get("id", "")

    # Um número só pode pertencer a uma conta. Se já estiver noutra, é engano
    # de quem conectou, e sobrescrever em silêncio seria pior.
    dono = WhatsAppAccount.objects.filter(phone_number_id=numero_id).exclude(user=user).first()
    if dono:
        raise SignupError(
            "Este número já está conectado a outra conta do EducaflowOne."
        )

    account, _ = WhatsAppAccount.objects.get_or_create(
        user=user, defaults={"phone_number_id": numero_id}
    )

    account.phone_number_id = numero_id
    account.waba_id = waba_id
    account.display_phone_number = numero.get("display_phone_number", "")
    account.verified_name = numero.get("verified_name", "")
    account.quality_rating = numero.get("quality_rating", "") or ""
    # `platform_type` volta como CLOUD_API quando o número também roda no
    # aplicativo do celular, que é o caso da coexistência.
    account.is_coexistence = True
    account.status = WhatsAppAccount.STATUS_CONNECTED
    account.is_active = True
    account.connected_at = timezone.now()
    account.last_synced_at = timezone.now()
    account.last_error = ""
    account.last_error_at = None
    account.set_access_token(token)
    account.save()

    # A importação do passado é o único passo com prazo. Não pode derrubar a
    # conexão, que já está boa a esta altura.
    for sync_type in (SYNC_CONTACTS, SYNC_HISTORY):
        try:
            trigger_sync(numero_id, token, sync_type)
        except SignupError as exc:
            print(f"[WhatsApp signup] Sincronização '{sync_type}' falhou: {exc}")
            account.last_error = (
                f"Conexão feita, mas a importação do histórico falhou: {exc}"
            )[:2000]
            account.last_error_at = timezone.now()
            account.save(update_fields=["last_error", "last_error_at", "updated_at"])

    return account


@transaction.atomic
def connect_manually(user, access_token: str, waba_id: str,
                     phone_number_id: str = "",
                     sync_history: bool = True) -> WhatsAppAccount:
    """
    Conecta com um token colado à mão, sem passar pelo popup.

    Caminho do piloto. Um usuário do sistema no portfólio gera um token
    permanente, e ele entra aqui. Dispensa Embedded Signup, Tech Provider e
    revisão de permissões pela Meta, o que corta semanas.

    A app da Meta continua sendo necessária: o token de usuário do sistema é
    gerado escolhendo uma app. O que se dispensa é a burocracia em volta dela.

    O token é validado contra a Meta antes de ser guardado. Guardar um token
    inválido deixaria a conta "conectada" e muda, que é o pior estado possível.
    """
    access_token = (access_token or "").strip()
    waba_id = (waba_id or "").strip()
    phone_number_id = (phone_number_id or "").strip()

    if not access_token:
        raise SignupError("Cole o token de acesso.")
    if not waba_id:
        raise SignupError("Informe o ID da conta de negócio do WhatsApp (WABA).")

    numeros = list_phone_numbers(waba_id, access_token)
    numero = _pick_phone_number(numeros, phone_number_id)
    numero_id = numero.get("id", "")

    dono = WhatsAppAccount.objects.filter(
        phone_number_id=numero_id
    ).exclude(user=user).first()
    if dono:
        raise SignupError(
            "Este número já está conectado a outra conta do EducaflowOne."
        )

    # Assinar a app à WABA é o passo que mais some no caminho manual, e a
    # falha dele é silenciosa: tudo parece certo e nenhuma mensagem chega.
    try:
        subscribe_app_to_waba(waba_id, access_token)
    except SignupError as exc:
        raise SignupError(
            f"O token funciona, mas não foi possível assinar a app à WABA: {exc} "
            f"Sem isso nenhuma mensagem chega ao sistema."
        ) from exc

    account, _ = WhatsAppAccount.objects.get_or_create(
        user=user, defaults={"phone_number_id": numero_id}
    )

    account.phone_number_id = numero_id
    account.waba_id = waba_id
    account.display_phone_number = numero.get("display_phone_number", "")
    account.verified_name = numero.get("verified_name", "")
    account.quality_rating = numero.get("quality_rating", "") or ""
    account.is_coexistence = True
    account.status = WhatsAppAccount.STATUS_CONNECTED
    account.is_active = True
    account.connected_at = timezone.now()
    account.last_synced_at = timezone.now()
    account.last_error = ""
    account.last_error_at = None
    account.set_access_token(access_token)
    account.save()

    # A importação do passado só existe para número que vem do aplicativo, e
    # só vale nas primeiras 24 horas depois do vínculo na Meta.
    if sync_history:
        for sync_type in (SYNC_CONTACTS, SYNC_HISTORY):
            try:
                trigger_sync(numero_id, access_token, sync_type)
            except SignupError as exc:
                print(f"[WhatsApp manual] Sincronização '{sync_type}' falhou: {exc}")
                account.last_error = (
                    f"Conectado, mas a importação do histórico falhou: {exc}"
                )[:2000]
                account.last_error_at = timezone.now()
                account.save(update_fields=[
                    "last_error", "last_error_at", "updated_at",
                ])

    return account


def disconnect(account: WhatsAppAccount) -> None:
    """
    Desliga o canal sem apagar conversa nenhuma.

    O histórico continua no sistema e no celular da professora; só para de
    enviar e de receber.
    """
    account.is_active = False
    account.status = WhatsAppAccount.STATUS_DISCONNECTED
    account.access_token_encrypted = ""
    account.save(update_fields=[
        "is_active", "status", "access_token_encrypted", "updated_at",
    ])
