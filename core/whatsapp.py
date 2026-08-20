"""
Camada de serviço do WhatsApp Business (Cloud API).

Este módulo concentra tudo o que fala com a Meta e tudo o que é regra de
negócio do canal. As views ficam finas: recebem o webhook, validam a
assinatura e chamam daqui.

Contexto do desenho (decisões que valem a pena não redescobrir):

1. **Coexistence.** O número da escola roda ao mesmo tempo no aplicativo do
   WhatsApp Business (no celular da professora) e na Cloud API. Mensagens
   enviadas pelo aplicativo chegam aqui como *echo* (`origin=app`), com a
   direção de saída. Ou seja: nem toda mensagem de saída foi disparada pelo
   sistema, e o histórico só fica completo se tratarmos os echoes.

2. **Janela de 24 horas.** Só vale para o que sai pela API. Mensagem enviada
   pela professora no aplicativo não está sujeita à janela. Por isso a janela
   é calculada a partir da última mensagem *recebida*, e é consultada apenas
   no momento de enviar pela API.

3. **O nono dígito.** No Brasil o `wa_id` que a Meta devolve às vezes vem sem
   o nono dígito (números antigos), e o telefone cadastrado pelo professor
   quase sempre vem com. Casar contato por igualdade de string perde metade
   dos casos, então toda busca passa por `phone_variants`.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
from datetime import timedelta

from django.utils import timezone

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

GRAPH_VERSION = os.environ.get("WHATSAPP_GRAPH_VERSION", "v25.0").strip() or "v25.0"
GRAPH_BASE_URL = f"https://graph.facebook.com/{GRAPH_VERSION}"

# Janela de atendimento da Meta: 24h a contar da última mensagem do cliente.
SERVICE_WINDOW = timedelta(hours=24)

# Margem de segurança para não tentar enviar texto livre em cima do limite e
# tomar erro 131047 da Meta.
SERVICE_WINDOW_MARGIN = timedelta(minutes=5)

REQUEST_TIMEOUT = 20  # segundos


def is_enabled() -> bool:
    """
    Interruptor geral da funcionalidade.

    Enquanto o piloto não estiver liberado, nada é enviado e o webhook
    responde 200 sem processar. Ligado por conta (WhatsAppAccount.is_active)
    e por ambiente (esta variável).
    """
    return (os.environ.get("WHATSAPP_ENABLED", "").strip().lower()
            in ("1", "true", "yes", "on"))


def pode_usar_canal(user) -> bool:
    """Quem enxerga o canal WhatsApp dentro do sistema.

    O piloto e de uma professora so. Enquanto for assim, a lista de convidados
    vive na variavel WHATSAPP_USUARIOS, com nome de utilizador ou e-mail
    separados por virgula, e todos os outros recebem 404: nao basta a tela
    aparecer vazia, ela nao deve existir para quem nao foi convidado.

    Lista vazia significa ninguem, de proposito. Ligar o canal e um ato
    deliberado, nao um efeito colateral de um deploy.
    """
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True

    convidados = {
        item.strip().lower()
        for item in os.environ.get("WHATSAPP_USUARIOS", "").split(",")
        if item.strip()
    }
    if not convidados:
        return False

    identificadores = {
        (getattr(user, "username", "") or "").lower(),
        (getattr(user, "email", "") or "").lower(),
    }
    identificadores.discard("")
    return bool(identificadores & convidados)


# ---------------------------------------------------------------------------
# Telefones brasileiros
# ---------------------------------------------------------------------------

def normalize_phone(raw: str, default_country: str = "55") -> str:
    """
    Converte um telefone escrito por humano em E.164 sem o '+'.

    Aceita "(41) 98836-9627", "+55 41 98836-9627", "41988369627" e devolve
    "5541988369627". Devolve "" quando não dá para reconhecer.
    """
    if not raw:
        return ""

    digits = re.sub(r"\D", "", str(raw))
    if not digits:
        return ""

    # Zeros de discagem nacional/internacional: 0 41 9..., 00 55 41 9...
    digits = digits.lstrip("0") or ""
    if not digits:
        return ""

    if digits.startswith(default_country) and len(digits) >= 12:
        return digits

    # 10 dígitos (fixo ou celular antigo) ou 11 (celular com nono dígito),
    # ambos já com DDD e sem código de país.
    if len(digits) in (10, 11):
        return f"{default_country}{digits}"

    # Já veio com outro código de país.
    if len(digits) > 11:
        return digits

    return ""


def phone_variants(phone: str) -> list[str]:
    """
    Devolve as formas equivalentes de um número brasileiro de celular.

    O WhatsApp identifica alguns números antigos sem o nono dígito, enquanto o
    cadastro do professor tem o número completo. As duas formas apontam para a
    mesma pessoa, então qualquer busca precisa considerar ambas.

    "5541988369627" -> ["5541988369627", "554188369627"]
    "554188369627"  -> ["554188369627", "5541988369627"]

    Números que não são celular brasileiro voltam sozinhos, sem invenção.
    """
    e164 = normalize_phone(phone)
    if not e164:
        return []

    variants = [e164]

    if not e164.startswith("55"):
        return variants

    national = e164[2:]

    # 11 dígitos: DDD + 9 + 8 dígitos. Gera a forma curta.
    if len(national) == 11 and national[2] == "9":
        variants.append(f"55{national[:2]}{national[3:]}")

    # 10 dígitos: DDD + 8 dígitos. Só é celular se começar por 6-9;
    # 2-5 é telefone fixo e não ganha nono dígito.
    elif len(national) == 10 and national[2] in "6789":
        variants.append(f"55{national[:2]}9{national[2:]}")

    return variants


def format_phone_br(e164: str) -> str:
    """Formata para exibição: "5541988369627" -> "+55 (41) 98836-9627"."""
    if not e164:
        return ""
    if not e164.startswith("55") or len(e164) not in (12, 13):
        return f"+{e164}"

    ddd = e164[2:4]
    rest = e164[4:]
    if len(rest) == 9:
        return f"+55 ({ddd}) {rest[:5]}-{rest[5:]}"
    return f"+55 ({ddd}) {rest[:4]}-{rest[4:]}"


# ---------------------------------------------------------------------------
# Segredos em repouso
# ---------------------------------------------------------------------------

def _encryption_key() -> bytes:
    """
    Chave Fernet para os tokens de acesso guardados no banco.

    Prefere WHATSAPP_ENCRYPTION_KEY (chave Fernet pronta, base64 de 32 bytes).
    Sem ela, deriva da SECRET_KEY do Django, o que já protege contra um dump
    de banco vazado. Trocar a SECRET_KEY invalida os tokens guardados e obriga
    a reconectar a conta, o que é aceitável e detectável.
    """
    explicit = os.environ.get("WHATSAPP_ENCRYPTION_KEY", "").strip()
    if explicit:
        return explicit.encode("utf-8")

    from django.conf import settings

    derived = hashlib.sha256(
        f"whatsapp-token-v1:{settings.SECRET_KEY}".encode("utf-8")
    ).digest()
    return base64.urlsafe_b64encode(derived)


def encrypt_secret(plaintext: str) -> str:
    """Cifra um token. Devolve "" para entrada vazia."""
    if not plaintext:
        return ""
    try:
        from cryptography.fernet import Fernet

        return Fernet(_encryption_key()).encrypt(plaintext.encode("utf-8")).decode("utf-8")
    except Exception as exc:  # pragma: no cover - depende do ambiente
        # Falhar aqui em silêncio guardaria o token em claro sem ninguém saber.
        raise RuntimeError(f"Não foi possível cifrar o token do WhatsApp: {exc}") from exc


def decrypt_secret(ciphertext: str) -> str:
    """Decifra um token guardado. Devolve "" se não der para ler."""
    if not ciphertext:
        return ""
    try:
        from cryptography.fernet import Fernet

        return Fernet(_encryption_key()).decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except Exception as exc:  # pragma: no cover - depende do ambiente
        print(f"[WhatsApp] Falha ao decifrar token guardado: {exc}")
        return ""


# ---------------------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------------------

def verify_webhook_signature(payload: bytes, signature_header: str, app_secret: str) -> bool:
    """
    Confere o cabeçalho X-Hub-Signature-256 enviado pela Meta.

    O corpo precisa ser o byte a byte recebido (request.body), nunca o JSON
    reserializado, senão a assinatura nunca bate.
    """
    if not app_secret or not signature_header:
        return False

    if not signature_header.startswith("sha256="):
        return False

    expected = hmac.new(
        app_secret.encode("utf-8"), payload, hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature_header[len("sha256="):])


def webhook_event_key(entry_id: str, field: str, change_value: dict) -> str:
    """
    Chave de idempotência de um evento.

    A Meta reentrega o mesmo webhook quando não recebe 200 rápido o bastante,
    e reentrega o status de uma mensagem várias vezes (sent, delivered, read).
    A chave junta o id da mensagem com o estado, para não descartar
    atualizações legítimas nem processar a mesma duas vezes.
    """
    parts = [entry_id or "", field or ""]

    for message in change_value.get("messages", []) or []:
        parts.append(f"msg:{message.get('id', '')}")

    for echo in change_value.get("message_echoes", []) or []:
        parts.append(f"echo:{echo.get('id', '')}")

    for status in change_value.get("statuses", []) or []:
        parts.append(f"st:{status.get('id', '')}:{status.get('status', '')}")

    # Eventos sem mensagem nem status (sincronização de contatos, histórico)
    # não têm id estável. O hash do corpo evita reprocessar a reentrega.
    if len(parts) == 2:
        parts.append(json.dumps(change_value, sort_keys=True, ensure_ascii=False)[:4000])

    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Janela de atendimento
# ---------------------------------------------------------------------------

def window_is_open(last_inbound_at) -> bool:
    """
    Diz se ainda dá para enviar texto livre pela API.

    Fora da janela, a Meta só aceita template aprovado. Vale só para a API:
    o aplicativo no celular da professora não tem essa restrição.
    """
    if not last_inbound_at:
        return False
    return timezone.now() < (last_inbound_at + SERVICE_WINDOW - SERVICE_WINDOW_MARGIN)


def window_expires_at(last_inbound_at):
    """Momento em que a janela fecha, ou None se nunca houve mensagem recebida."""
    if not last_inbound_at:
        return None
    return last_inbound_at + SERVICE_WINDOW


# ---------------------------------------------------------------------------
# Cliente da Cloud API
# ---------------------------------------------------------------------------

class WhatsAppAPIError(Exception):
    """Erro devolvido pela Meta, já com o código que interessa para decidir."""

    def __init__(self, message: str, code: int | None = None,
                 subcode: int | None = None, status_code: int | None = None,
                 payload: dict | None = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.subcode = subcode
        self.status_code = status_code
        self.payload = payload or {}

    @property
    def is_window_closed(self) -> bool:
        """131047: 'Message failed to send because more than 24 hours have passed'."""
        return self.code == 131047

    @property
    def is_reengagement_required(self) -> bool:
        return self.code in (131047, 131051)

    @property
    def is_rate_limited(self) -> bool:
        return self.code in (4, 80007, 130429, 131056)

    @property
    def is_auth_error(self) -> bool:
        """Token expirado ou revogado: a conta precisa reconectar."""
        return self.code in (190, 102, 10) or self.status_code == 401


class CloudAPIClient:
    """
    Cliente fino sobre a Graph API.

    Um cliente por conta conectada, porque token e phone_number_id são da
    conta. Não guarda estado entre chamadas.
    """

    def __init__(self, phone_number_id: str, access_token: str,
                 waba_id: str = "", timeout: int = REQUEST_TIMEOUT):
        if not phone_number_id:
            raise ValueError("phone_number_id é obrigatório")
        if not access_token:
            raise ValueError("access_token é obrigatório")

        self.phone_number_id = phone_number_id
        self.access_token = access_token
        self.waba_id = waba_id
        self.timeout = timeout

    # -- infraestrutura ----------------------------------------------------

    def _request(self, method: str, path: str, *, json_body: dict | None = None,
                 params: dict | None = None) -> dict:
        import requests

        url = f"{GRAPH_BASE_URL}/{path.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.request(
                method, url, headers=headers, json=json_body,
                params=params, timeout=self.timeout,
            )
        except Exception as exc:
            raise WhatsAppAPIError(f"Falha de rede ao falar com a Meta: {exc}") from exc

        try:
            data = response.json() if response.content else {}
        except ValueError:
            data = {"raw": (response.text or "")[:500]}

        if response.status_code >= 400:
            error = (data or {}).get("error", {}) or {}
            raise WhatsAppAPIError(
                message=error.get("message") or f"HTTP {response.status_code}",
                code=error.get("code"),
                subcode=error.get("error_subcode"),
                status_code=response.status_code,
                payload=data,
            )

        return data

    def _send(self, payload: dict) -> dict:
        payload = {"messaging_product": "whatsapp", **payload}
        return self._request("POST", f"{self.phone_number_id}/messages", json_body=payload)

    @staticmethod
    def _first_wamid(response: dict) -> str:
        messages = (response or {}).get("messages") or []
        return messages[0].get("id", "") if messages else ""

    # -- envio -------------------------------------------------------------

    def send_text(self, to: str, body: str, preview_url: bool = False) -> dict:
        """
        Texto livre. Só funciona dentro da janela de 24h.

        Quem chama deve ter conferido a janela antes; se não conferiu, a Meta
        devolve 131047 e o erro sobe como WhatsAppAPIError.is_window_closed.
        """
        response = self._send({
            "to": normalize_phone(to),
            "type": "text",
            "text": {"body": body, "preview_url": preview_url},
        })
        return {"wamid": self._first_wamid(response), "raw": response}

    def send_template(self, to: str, template_name: str, language: str = "pt_BR",
                      body_params: list | None = None,
                      header_params: list | None = None,
                      button_params: list | None = None) -> dict:
        """
        Template aprovado. Único caminho fora da janela de 24h.

        Os parâmetros entram por posição, na ordem das chaves {{1}}, {{2}}...
        do corpo aprovado na Meta.
        """
        components = []

        if header_params:
            components.append({
                "type": "header",
                "parameters": [{"type": "text", "text": str(p)} for p in header_params],
            })

        if body_params:
            components.append({
                "type": "body",
                "parameters": [{"type": "text", "text": str(p)} for p in body_params],
            })

        if button_params:
            for index, param in enumerate(button_params):
                components.append({
                    "type": "button",
                    "sub_type": "url",
                    "index": str(index),
                    "parameters": [{"type": "text", "text": str(param)}],
                })

        payload = {
            "to": normalize_phone(to),
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language},
            },
        }
        if components:
            payload["template"]["components"] = components

        response = self._send(payload)
        return {"wamid": self._first_wamid(response), "raw": response}

    def mark_as_read(self, wamid: str) -> dict:
        """
        Marca a mensagem como lida para o remetente.

        Em coexistence isto também sincroniza o não lido com o aplicativo da
        professora, o que evita ela reabrir no celular uma conversa que já foi
        respondida pelo sistema.
        """
        return self._send({"status": "read", "message_id": wamid})

    # -- mídia -------------------------------------------------------------

    def get_media_url(self, media_id: str) -> dict:
        """A URL devolvida é temporária e exige o token no download."""
        return self._request("GET", media_id)

    def download_media(self, media_url: str) -> bytes:
        import requests

        try:
            response = requests.get(
                media_url,
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.content
        except Exception as exc:
            raise WhatsAppAPIError(f"Falha ao baixar mídia: {exc}") from exc

    # -- conta -------------------------------------------------------------

    def get_phone_number(self) -> dict:
        """Nome de exibição, número formatado e qualidade do número."""
        return self._request(
            "GET", self.phone_number_id,
            params={"fields": "display_phone_number,verified_name,quality_rating,"
                              "code_verification_status,platform_type,throughput"},
        )

    def list_templates(self, limit: int = 100) -> dict:
        """Templates da WABA, com o estado de aprovação de cada um."""
        if not self.waba_id:
            raise ValueError("waba_id é obrigatório para listar templates")
        return self._request(
            "GET", f"{self.waba_id}/message_templates",
            params={"limit": limit,
                    "fields": "id,name,status,category,language,components,"
                              "rejected_reason"},
        )

    def create_template(self, name: str, category: str, language: str,
                        body_text: str, example_params: list | None = None) -> dict:
        """
        Submete um modelo para aprovação da Meta.

        O corpo usa as chaves {{1}}, {{2}}... e a Meta **exige um exemplo** para
        cada uma: sem exemplo ela reprova sem explicar direito. O nome só aceita
        minúsculas, números e sublinhado.
        """
        if not self.waba_id:
            raise ValueError("waba_id é obrigatório para criar template")

        body = {"type": "BODY", "text": body_text}
        if example_params:
            body["example"] = {"body_text": [[str(p) for p in example_params]]}

        return self._request("POST", f"{self.waba_id}/message_templates", json_body={
            "name": name,
            "category": category,
            "language": language,
            "components": [body],
        })

    def delete_template(self, name: str) -> dict:
        if not self.waba_id:
            raise ValueError("waba_id é obrigatório para apagar template")
        return self._request(
            "DELETE", f"{self.waba_id}/message_templates", params={"name": name}
        )


# ---------------------------------------------------------------------------
# Leitura do payload do webhook
# ---------------------------------------------------------------------------

# Campos do webhook que este módulo entende.
#
#   messages           mensagens recebidas dos contatos e status de entrega
#   smb_message_echoes cópia do que a professora enviou pelo aplicativo do
#                      celular. É o que faz a coexistence valer a pena: sem
#                      tratar isto, a caixa de entrada só mostra metade da
#                      conversa e ninguém confia nela.
#   history            importação das conversas antigas, nas primeiras 24h
#                      depois da conexão
#   smb_app_state_sync contatos do aplicativo sincronizados para a API
#   message_template_status_update  a Meta aprovou, reprovou ou pausou um
#                      modelo. Chega sozinho, horas ou dias depois de submeter.
FIELD_MESSAGES = "messages"
FIELD_ECHOES = "smb_message_echoes"
FIELD_HISTORY = "history"
FIELD_APP_STATE = "smb_app_state_sync"
FIELD_TEMPLATE_STATUS = "message_template_status_update"

SUPPORTED_FIELDS = (
    FIELD_MESSAGES, FIELD_ECHOES, FIELD_HISTORY, FIELD_APP_STATE,
    FIELD_TEMPLATE_STATUS,
)


def iter_changes(payload: dict):
    """
    Percorre o envelope do webhook e devolve (entry_id, field, value).

    A Meta agrupa várias mudanças num POST só, e nada garante que todas sejam
    da mesma conta nem do mesmo tipo. Cada uma é resolvida pelo
    phone_number_id de dentro.
    """
    for entry in (payload or {}).get("entry", []) or []:
        entry_id = entry.get("id", "")
        for change in entry.get("changes", []) or []:
            field = change.get("field", "")
            if field not in SUPPORTED_FIELDS:
                continue
            yield entry_id, field, (change.get("value") or {})


def extract_phone_number_id(change_value: dict) -> str:
    """Identifica a conta dona do evento."""
    return ((change_value or {}).get("metadata") or {}).get("phone_number_id", "")


def parse_message(raw: dict) -> dict:
    """
    Normaliza uma mensagem do webhook para os campos que guardamos.

    Trata os tipos que aparecem de verdade no dia a dia de uma escola: texto,
    áudio (pai mandando recado), imagem (comprovante de pagamento), documento,
    e a resposta a um botão de template.
    """
    message_type = raw.get("type", "")
    parsed = {
        "wamid": raw.get("id", ""),
        "type": message_type,
        "from": raw.get("from", ""),
        "timestamp": raw.get("timestamp", ""),
        "body": "",
        "media_id": "",
        "media_mime": "",
        "media_filename": "",
        "reply_to_wamid": ((raw.get("context") or {}).get("id") or ""),
    }

    if message_type == "text":
        parsed["body"] = (raw.get("text") or {}).get("body", "")

    elif message_type in ("image", "audio", "video", "document", "sticker", "voice"):
        media = raw.get(message_type) or {}
        parsed["media_id"] = media.get("id", "")
        parsed["media_mime"] = media.get("mime_type", "")
        parsed["media_filename"] = media.get("filename", "")
        parsed["body"] = media.get("caption", "")

    elif message_type == "button":
        parsed["body"] = (raw.get("button") or {}).get("text", "")

    elif message_type == "interactive":
        interactive = raw.get("interactive") or {}
        subtype = interactive.get("type", "")
        parsed["body"] = ((interactive.get(subtype) or {}).get("title")
                          or (interactive.get(subtype) or {}).get("id") or "")

    elif message_type == "location":
        location = raw.get("location") or {}
        parsed["body"] = (f"{location.get('latitude', '')},{location.get('longitude', '')} "
                          f"{location.get('name', '')}").strip()

    elif message_type == "contacts":
        names = [((c.get("name") or {}).get("formatted_name") or "")
                 for c in (raw.get("contacts") or [])]
        parsed["body"] = ", ".join(n for n in names if n)

    else:
        # Tipo novo ou não suportado: guarda o cru para não perder a conversa.
        parsed["body"] = f"[{message_type or 'desconhecido'}]"
        parsed["raw_fallback"] = json.dumps(raw, ensure_ascii=False)[:2000]

    return parsed


def extract_template_body(components: list | None) -> str:
    """
    Tira o texto do corpo da lista de componentes que a Meta devolve.

    Um template tem cabeçalho, corpo, rodapé e botões. Só o corpo interessa
    para mostrar na conversa e para contar as variáveis.
    """
    for component in components or []:
        if (component or {}).get("type", "").upper() == "BODY":
            return component.get("text", "") or ""
    return ""


def count_template_variables(body_text: str) -> int:
    """
    Quantas chaves {{n}} o corpo tem.

    É o que diz quantos parâmetros o envio precisa. Mandar a menos faz a Meta
    recusar; mandar a mais também.
    """
    if not body_text:
        return 0
    numeros = {int(n) for n in re.findall(r"\{\{\s*(\d+)\s*\}\}", body_text)}
    return max(numeros) if numeros else 0


def parse_echo(raw: dict) -> dict:
    """
    Normaliza um echo: mensagem que a professora enviou pelo aplicativo.

    Tem a mesma forma de uma mensagem recebida, com duas diferenças que
    importam: o destinatário vem em `to` em vez de `from`, e existem os tipos
    `revoke` (apagou para todos) e `edit` (editou), que se referem a uma
    mensagem anterior em vez de criar uma nova.
    """
    parsed = parse_message(raw)
    parsed["to"] = raw.get("to", "")
    parsed["from"] = raw.get("from", "")

    message_type = raw.get("type", "")

    if message_type == "revoke":
        parsed["original_message_id"] = (
            (raw.get("revoke") or {}).get("original_message_id", "")
            or raw.get("original_message_id", "")
        )
        parsed["body"] = "[mensagem apagada]"

    elif message_type == "edit":
        edit = raw.get("edit") or {}
        parsed["original_message_id"] = (
            edit.get("original_message_id", "") or raw.get("original_message_id", "")
        )
        parsed["body"] = (edit.get("text") or {}).get("body", "") or parsed["body"]

    return parsed


def parse_timestamp(raw_timestamp) -> "timezone.datetime":
    """
    Converte o timestamp Unix da Meta (string, em segundos) para datetime aware.

    Se vier vazio ou ilegível, usa a hora atual: perder a mensagem por causa do
    carimbo de tempo seria pior do que registrar a hora aproximada.
    """
    from datetime import datetime, timezone as dt_timezone

    try:
        return datetime.fromtimestamp(int(raw_timestamp), tz=dt_timezone.utc)
    except (TypeError, ValueError):
        return timezone.now()
