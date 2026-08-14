"""
Testes do canal WhatsApp.

Cobrem o que quebra em silêncio e só aparece com pai de aluno reclamando:
o nono dígito, a reentrega de webhook virando mensagem duplicada, a janela de
24 horas, e a visibilidade entre professores parceiros.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core import whatsapp as wa
from core import whatsapp_service as service
from core.models import (
    Student,
    WhatsAppAccount,
    WhatsAppContact,
    WhatsAppConversation,
    WhatsAppMessage,
    WhatsAppTemplate,
)

APP_SECRET = "segredo-de-teste"
VERIFY_TOKEN = "token-de-verificacao"

TEST_ENV = {
    "WHATSAPP_APP_SECRET": APP_SECRET,
    "WHATSAPP_WEBHOOK_VERIFY_TOKEN": VERIFY_TOKEN,
    "WHATSAPP_ENABLED": "true",
}


def sign(body: bytes) -> str:
    return "sha256=" + hmac.new(
        APP_SECRET.encode("utf-8"), body, hashlib.sha256
    ).hexdigest()


class PhoneNormalizationTests(TestCase):
    """O nono dígito é a maior fonte de contato duplicado no Brasil."""

    def test_normaliza_formatos_escritos_a_mao(self):
        esperado = "5541988369627"
        for entrada in [
            "+55 41 98836-9627",
            "(41) 98836-9627",
            "41988369627",
            "5541988369627",
            "+5541988369627",
            "041 98836 9627",
        ]:
            with self.subTest(entrada=entrada):
                self.assertEqual(wa.normalize_phone(entrada), esperado)

    def test_entrada_invalida_devolve_vazio(self):
        for entrada in ["", None, "abc", "123"]:
            self.assertEqual(wa.normalize_phone(entrada), "")

    def test_variantes_cobrem_celular_com_e_sem_nono_digito(self):
        com_nove = wa.phone_variants("+55 41 98836-9627")
        sem_nove = wa.phone_variants("+55 41 8836-9627")

        self.assertIn("5541988369627", com_nove)
        self.assertIn("554188369627", com_nove)
        # As duas formas precisam gerar o mesmo conjunto, senão o contato do
        # webhook não casa com o telefone do cadastro.
        self.assertEqual(set(com_nove), set(sem_nove))

    def test_fixo_nao_ganha_nono_digito(self):
        # 41 3333-4444 é telefone fixo: inventar um 9 criaria um número que
        # não existe e mandaria mensagem para desconhecido.
        variantes = wa.phone_variants("+55 41 3333-4444")
        self.assertEqual(variantes, ["554133334444"])

    def test_formatacao_para_exibicao(self):
        self.assertEqual(
            wa.format_phone_br("5541988369627"), "+55 (41) 98836-9627"
        )


class SignatureTests(TestCase):
    def test_assinatura_valida(self):
        body = b'{"objeto": "teste"}'
        self.assertTrue(
            wa.verify_webhook_signature(body, sign(body), APP_SECRET)
        )

    def test_corpo_alterado_invalida(self):
        body = b'{"objeto": "teste"}'
        assinatura = sign(body)
        self.assertFalse(
            wa.verify_webhook_signature(b'{"objeto": "outro"}', assinatura, APP_SECRET)
        )

    def test_sem_assinatura_ou_sem_segredo(self):
        body = b"{}"
        self.assertFalse(wa.verify_webhook_signature(body, "", APP_SECRET))
        self.assertFalse(wa.verify_webhook_signature(body, sign(body), ""))


class ServiceWindowTests(TestCase):
    def test_sem_mensagem_recebida_a_janela_esta_fechada(self):
        self.assertFalse(wa.window_is_open(None))

    def test_recem_recebida_abre(self):
        self.assertTrue(wa.window_is_open(timezone.now()))

    def test_passadas_24h_fecha(self):
        self.assertFalse(
            wa.window_is_open(timezone.now() - timedelta(hours=24, minutes=1))
        )

    def test_margem_de_seguranca_fecha_antes_do_limite(self):
        # Em cima da hora a Meta recusaria com 131047. Fechar antes evita
        # mostrar erro para a professora.
        self.assertFalse(
            wa.window_is_open(timezone.now() - timedelta(hours=23, minutes=58))
        )


class WhatsAppTestBase(TestCase):
    def setUp(self):
        self.dona = User.objects.create_user("bianca", password="x")
        self.parceira = User.objects.create_user("parceira", password="x")

        self.account = WhatsAppAccount.objects.create(
            user=self.dona,
            phone_number_id="123456",
            waba_id="waba-1",
            display_phone_number="+55 41 98836-9627",
            verified_name="Escola",
            status=WhatsAppAccount.STATUS_CONNECTED,
            is_active=True,
        )
        self.account.set_access_token("token-secreto")
        self.account.save()

        # Cadastro com o nono dígito, como a professora digita.
        self.aluno = Student.objects.create(
            name="João",
            phone="(41) 98836-9627",
            user=self.dona,
        )

    def build_message_payload(self, *, wa_id="554188369627", text="Oi professora",
                              wamid="wamid.AAA", timestamp=None):
        """Webhook de mensagem recebida. O wa_id vem SEM o nono dígito de propósito."""
        return {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "waba-1",
                "changes": [{
                    "field": "messages",
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {
                            "display_phone_number": "5541988369627",
                            "phone_number_id": "123456",
                        },
                        "contacts": [{
                            "profile": {"name": "Maria (mãe do João)"},
                            "wa_id": wa_id,
                        }],
                        "messages": [{
                            "from": wa_id,
                            "id": wamid,
                            "timestamp": timestamp or str(int(timezone.now().timestamp())),
                            "type": "text",
                            "text": {"body": text},
                        }],
                    },
                }],
            }],
        }


class InboundMessageTests(WhatsAppTestBase):
    def test_mensagem_recebida_cria_contato_conversa_e_liga_no_aluno(self):
        payload = self.build_message_payload()
        resumo = service.process_webhook(payload)

        self.assertEqual(resumo["processed"], 1)

        contato = WhatsAppContact.objects.get(account=self.account)
        # O casamento tem de funcionar apesar de o webhook mandar sem o 9
        # e o cadastro ter com o 9.
        self.assertEqual(contato.student, self.aluno)
        self.assertEqual(contato.profile_name, "Maria (mãe do João)")

        conversa = WhatsAppConversation.objects.get(contact=contato)
        self.assertEqual(conversa.unread_count, 1)
        self.assertTrue(conversa.window_is_open)
        self.assertEqual(conversa.last_message_preview, "Oi professora")

        mensagem = WhatsAppMessage.objects.get()
        self.assertEqual(mensagem.direction, WhatsAppMessage.DIRECTION_INBOUND)
        self.assertEqual(mensagem.origin, WhatsAppMessage.ORIGIN_CONTACT)

    def test_reentrega_do_mesmo_evento_nao_duplica(self):
        payload = self.build_message_payload()

        service.process_webhook(payload)
        resumo = service.process_webhook(payload)

        self.assertEqual(resumo["duplicated"], 1)
        self.assertEqual(WhatsAppMessage.objects.count(), 1)

    def test_numero_desconhecido_e_ignorado(self):
        payload = self.build_message_payload()
        payload["entry"][0]["changes"][0]["value"]["metadata"]["phone_number_id"] = "outro"

        resumo = service.process_webhook(payload)

        self.assertEqual(resumo["ignored"], 1)
        self.assertEqual(WhatsAppMessage.objects.count(), 0)

    def test_contato_sem_aluno_cadastrado_nao_se_perde(self):
        payload = self.build_message_payload(wa_id="5511999998888")
        service.process_webhook(payload)

        contato = WhatsAppContact.objects.get(wa_id="5511999998888")
        self.assertIsNone(contato.student)
        self.assertEqual(contato.relationship, WhatsAppContact.RELATIONSHIP_UNKNOWN)
        self.assertTrue(WhatsAppConversation.objects.filter(contact=contato).exists())

    def test_pedido_de_saida_revoga_consentimento(self):
        contato_payload = self.build_message_payload(text="Oi")
        service.process_webhook(contato_payload)

        contato = WhatsAppContact.objects.get(account=self.account)
        contato.grant_opt_in(source="matrícula")

        service.process_webhook(
            self.build_message_payload(text="SAIR", wamid="wamid.BBB")
        )

        contato.refresh_from_db()
        self.assertEqual(contato.opt_in_status, WhatsAppContact.OPT_IN_REVOKED)
        self.assertFalse(contato.can_receive_template)


class EchoTests(WhatsAppTestBase):
    """Coexistence: o que a professora manda pelo celular precisa aparecer aqui."""

    def build_echo_payload(self, *, to="554188369627", text="Bom dia!",
                           wamid="wamid.ECHO"):
        return {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "waba-1",
                "changes": [{
                    "field": "smb_message_echoes",
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {
                            "display_phone_number": "5541988369627",
                            "phone_number_id": "123456",
                        },
                        "message_echoes": [{
                            "from": "5541988369627",
                            "to": to,
                            "id": wamid,
                            "timestamp": str(int(timezone.now().timestamp())),
                            "type": "text",
                            "text": {"body": text},
                        }],
                    },
                }],
            }],
        }

    def test_echo_do_aplicativo_entra_como_mensagem_enviada(self):
        service.process_webhook(self.build_echo_payload())

        mensagem = WhatsAppMessage.objects.get()
        self.assertEqual(mensagem.direction, WhatsAppMessage.DIRECTION_OUTBOUND)
        self.assertEqual(mensagem.origin, WhatsAppMessage.ORIGIN_APP)
        self.assertTrue(mensagem.is_from_app)
        self.assertEqual(mensagem.body, "Bom dia!")

    def test_echo_nao_abre_a_janela_de_24h(self):
        # A janela depende de mensagem RECEBIDA. Resposta da professora pelo
        # celular não autoriza o sistema a enviar texto livre pela API.
        service.process_webhook(self.build_echo_payload())

        conversa = WhatsAppConversation.objects.get()
        self.assertIsNone(conversa.last_inbound_at)
        self.assertFalse(conversa.window_is_open)

    def test_echo_zera_o_nao_lido(self):
        service.process_webhook(self.build_message_payload())
        conversa = WhatsAppConversation.objects.get()
        self.assertEqual(conversa.unread_count, 1)

        service.process_webhook(self.build_echo_payload())

        conversa.refresh_from_db()
        self.assertEqual(conversa.unread_count, 0)


class StatusUpdateTests(WhatsAppTestBase):
    def setUp(self):
        super().setUp()
        service.process_webhook(self.build_message_payload())
        self.conversa = WhatsAppConversation.objects.get()
        self.mensagem = WhatsAppMessage.objects.create(
            conversation=self.conversa,
            wamid="wamid.OUT",
            direction=WhatsAppMessage.DIRECTION_OUTBOUND,
            origin=WhatsAppMessage.ORIGIN_API,
            status=WhatsAppMessage.STATUS_SENT,
            message_type="text",
            body="oi",
            timestamp=timezone.now(),
        )

    def build_status_payload(self, status, wamid="wamid.OUT", errors=None):
        value = {
            "messaging_product": "whatsapp",
            "metadata": {"display_phone_number": "5541988369627",
                         "phone_number_id": "123456"},
            "statuses": [{
                "id": wamid,
                "status": status,
                "timestamp": str(int(timezone.now().timestamp())),
                "recipient_id": "554188369627",
            }],
        }
        if errors:
            value["statuses"][0]["errors"] = errors
        return {"object": "whatsapp_business_account",
                "entry": [{"id": "waba-1",
                           "changes": [{"field": "messages", "value": value}]}]}

    def test_progride_ate_lida(self):
        service.process_webhook(self.build_status_payload("delivered"))
        self.mensagem.refresh_from_db()
        self.assertEqual(self.mensagem.status, WhatsAppMessage.STATUS_DELIVERED)

        service.process_webhook(self.build_status_payload("read"))
        self.mensagem.refresh_from_db()
        self.assertEqual(self.mensagem.status, WhatsAppMessage.STATUS_READ)

    def test_status_atrasado_nao_rebaixa(self):
        # A Meta não garante ordem: um 'sent' pode chegar depois do 'read'.
        service.process_webhook(self.build_status_payload("read"))
        service.process_webhook(self.build_status_payload("sent"))

        self.mensagem.refresh_from_db()
        self.assertEqual(self.mensagem.status, WhatsAppMessage.STATUS_READ)

    def test_falha_guarda_o_motivo(self):
        service.process_webhook(self.build_status_payload(
            "failed",
            errors=[{"code": 131047, "title": "Re-engagement message"}],
        ))

        self.mensagem.refresh_from_db()
        self.assertEqual(self.mensagem.status, WhatsAppMessage.STATUS_FAILED)
        self.assertEqual(self.mensagem.error_code, "131047")
        self.assertIn("Re-engagement", self.mensagem.error_message)


class SendingTests(WhatsAppTestBase):
    def setUp(self):
        super().setUp()
        service.process_webhook(self.build_message_payload())
        self.conversa = WhatsAppConversation.objects.get()

    @mock.patch.dict(os.environ, TEST_ENV)
    def test_texto_livre_dentro_da_janela(self):
        cliente = mock.Mock()
        cliente.send_text.return_value = {"wamid": "wamid.NOVA", "raw": {}}

        with mock.patch.object(WhatsAppAccount, "get_client", return_value=cliente):
            mensagem = service.send_text(self.conversa, "Tudo bem!", sent_by=self.dona)

        self.assertEqual(mensagem.status, WhatsAppMessage.STATUS_SENT)
        self.assertEqual(mensagem.origin, WhatsAppMessage.ORIGIN_API)
        cliente.send_text.assert_called_once()

    @mock.patch.dict(os.environ, TEST_ENV)
    def test_texto_livre_fora_da_janela_e_recusado_antes_de_chamar_a_meta(self):
        self.conversa.last_inbound_at = timezone.now() - timedelta(hours=25)
        self.conversa.save(update_fields=["last_inbound_at"])

        cliente = mock.Mock()
        with mock.patch.object(WhatsAppAccount, "get_client", return_value=cliente):
            with self.assertRaises(service.WhatsAppSendError) as ctx:
                service.send_text(self.conversa, "Oi", sent_by=self.dona)

        self.assertIn("24 horas", str(ctx.exception))
        cliente.send_text.assert_not_called()

    @mock.patch.dict(os.environ, TEST_ENV)
    def test_template_exige_consentimento(self):
        template = WhatsAppTemplate.objects.create(
            account=self.account,
            name="cobranca_atraso",
            purpose=WhatsAppTemplate.PURPOSE_BILLING_OVERDUE,
            status=WhatsAppTemplate.STATUS_APPROVED,
            body_text="Olá {{1}}, a mensalidade de {{2}} está em atraso.",
        )

        cliente = mock.Mock()
        with mock.patch.object(WhatsAppAccount, "get_client", return_value=cliente):
            with self.assertRaises(service.WhatsAppSendError):
                service.send_template(self.conversa, template, ["João", "R$ 300"])

        cliente.send_template.assert_not_called()

    @mock.patch.dict(os.environ, TEST_ENV)
    def test_template_aprovado_com_consentimento_guarda_texto_renderizado(self):
        self.conversa.contact.grant_opt_in(source="contrato de matrícula")
        template = WhatsAppTemplate.objects.create(
            account=self.account,
            name="cobranca_atraso",
            purpose=WhatsAppTemplate.PURPOSE_BILLING_OVERDUE,
            status=WhatsAppTemplate.STATUS_APPROVED,
            body_text="Olá {{1}}, a mensalidade de {{2}} está em atraso.",
        )

        cliente = mock.Mock()
        cliente.send_template.return_value = {"wamid": "wamid.TPL", "raw": {}}

        with mock.patch.object(WhatsAppAccount, "get_client", return_value=cliente):
            mensagem = service.send_template(
                self.conversa, template, ["João", "R$ 300"], sent_by=self.dona
            )

        # O histórico precisa mostrar o texto que a família recebeu, não o
        # nome do template.
        self.assertEqual(
            mensagem.body, "Olá João, a mensalidade de R$ 300 está em atraso."
        )

    @mock.patch.dict(os.environ, TEST_ENV)
    def test_template_nao_aprovado_e_recusado(self):
        template = WhatsAppTemplate.objects.create(
            account=self.account,
            name="cobranca_atraso",
            purpose=WhatsAppTemplate.PURPOSE_BILLING_OVERDUE,
            status=WhatsAppTemplate.STATUS_PENDING,
        )
        self.conversa.contact.grant_opt_in(source="contrato")

        with self.assertRaises(service.WhatsAppSendError):
            service.send_template(self.conversa, template, [])

    def test_conta_inativa_nao_envia(self):
        self.account.is_active = False
        self.account.save(update_fields=["is_active"])

        with self.assertRaises(service.WhatsAppSendError):
            service.send_text(self.conversa, "Oi")

    @mock.patch.dict(os.environ, TEST_ENV)
    def test_contato_bloqueado_nao_recebe(self):
        self.conversa.contact.is_blocked = True
        self.conversa.contact.save(update_fields=["is_blocked"])

        with self.assertRaises(service.WhatsAppSendError):
            service.send_text(self.conversa, "Oi")


class VisibilityTests(WhatsAppTestBase):
    """Uma escola tem vários professores num número só."""

    def test_parceira_ve_so_a_conversa_do_aluno_dela(self):
        self.aluno.assigned_teacher = self.parceira
        self.aluno.save(update_fields=["assigned_teacher"])

        outro_aluno = Student.objects.create(
            name="Ana", phone="(41) 97777-1111", user=self.dona
        )

        service.process_webhook(self.build_message_payload())
        service.process_webhook(self.build_message_payload(
            wa_id="5541977771111", wamid="wamid.CCC"
        ))

        conversa_joao = WhatsAppConversation.objects.get(
            contact__student=self.aluno
        )
        conversa_ana = WhatsAppConversation.objects.get(
            contact__student=outro_aluno
        )

        self.assertEqual(conversa_joao.assigned_teacher, self.parceira)
        self.assertTrue(conversa_joao.visible_to(self.parceira))
        self.assertFalse(conversa_ana.visible_to(self.parceira))

        # A dona do número enxerga tudo: é a conta dela e a responsabilidade
        # legal também.
        self.assertTrue(conversa_joao.visible_to(self.dona))
        self.assertTrue(conversa_ana.visible_to(self.dona))

    def test_ligar_contato_ao_aluno_reatribui_a_conversa(self):
        service.process_webhook(self.build_message_payload(wa_id="5511999998888"))
        contato = WhatsAppContact.objects.get(wa_id="5511999998888")

        self.aluno.assigned_teacher = self.parceira
        self.aluno.save(update_fields=["assigned_teacher"])

        service.link_contact_to_student(contato, self.aluno)

        conversa = WhatsAppConversation.objects.get(contact=contato)
        self.assertEqual(conversa.assigned_teacher, self.parceira)


class WebhookViewTests(WhatsAppTestBase):
    def setUp(self):
        super().setUp()
        self.url = reverse("whatsapp-webhook")

    @mock.patch.dict(os.environ, TEST_ENV)
    def test_handshake_de_verificacao(self):
        resposta = self.client.get(self.url, {
            "hub.mode": "subscribe",
            "hub.verify_token": VERIFY_TOKEN,
            "hub.challenge": "desafio-123",
        })

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.content.decode(), "desafio-123")

    @mock.patch.dict(os.environ, TEST_ENV)
    def test_handshake_com_token_errado(self):
        resposta = self.client.get(self.url, {
            "hub.mode": "subscribe",
            "hub.verify_token": "errado",
            "hub.challenge": "desafio-123",
        })
        self.assertEqual(resposta.status_code, 403)

    @mock.patch.dict(os.environ, TEST_ENV)
    def test_post_sem_assinatura_e_recusado(self):
        corpo = json.dumps(self.build_message_payload())
        resposta = self.client.post(
            self.url, data=corpo, content_type="application/json"
        )

        self.assertEqual(resposta.status_code, 403)
        self.assertEqual(WhatsAppMessage.objects.count(), 0)

    @mock.patch.dict(os.environ, TEST_ENV)
    def test_post_assinado_processa(self):
        corpo = json.dumps(self.build_message_payload()).encode("utf-8")
        resposta = self.client.post(
            self.url, data=corpo, content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=sign(corpo),
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(WhatsAppMessage.objects.count(), 1)

    @mock.patch.dict(os.environ, {**TEST_ENV, "WHATSAPP_ENABLED": "false"})
    def test_canal_desligado_confirma_sem_processar(self):
        corpo = json.dumps(self.build_message_payload()).encode("utf-8")
        resposta = self.client.post(
            self.url, data=corpo, content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=sign(corpo),
        )

        # 200 de propósito: erro faz a Meta reentregar e depois desativar o
        # webhook. Só não processa.
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(WhatsAppMessage.objects.count(), 0)


class TokenEncryptionTests(TestCase):
    def test_token_nao_fica_em_claro_no_banco(self):
        dono = User.objects.create_user("prof", password="x")
        conta = WhatsAppAccount.objects.create(user=dono, phone_number_id="999")
        conta.set_access_token("EAAG-token-real")
        conta.save()

        conta.refresh_from_db()
        self.assertNotIn("EAAG-token-real", conta.access_token_encrypted)
        self.assertEqual(conta.get_access_token(), "EAAG-token-real")
