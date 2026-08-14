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
from core import whatsapp_signup as signup
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


class InboxApiTests(WhatsAppTestBase):
    """
    A caixa de entrada expõe conversas por HTTP, então a regra de visibilidade
    deixa de ser detalhe de interface e passa a ser limite de segurança.
    """

    def setUp(self):
        super().setUp()

        # João é da parceira; Ana fica com a dona.
        self.aluno.assigned_teacher = self.parceira
        self.aluno.save(update_fields=["assigned_teacher"])
        self.outro_aluno = Student.objects.create(
            name="Ana", phone="(41) 97777-1111", user=self.dona
        )

        service.process_webhook(self.build_message_payload())
        service.process_webhook(self.build_message_payload(
            wa_id="5541977771111", wamid="wamid.CCC"
        ))

        self.conversa_joao = WhatsAppConversation.objects.get(
            contact__student=self.aluno
        )
        self.conversa_ana = WhatsAppConversation.objects.get(
            contact__student=self.outro_aluno
        )

    def test_sem_sessao_devolve_401(self):
        resposta = self.client.get(reverse("whatsapp-conversations"))
        self.assertEqual(resposta.status_code, 401)

    def test_dona_ve_todas_as_conversas(self):
        self.client.force_login(self.dona)
        resposta = self.client.get(reverse("whatsapp-conversations"))

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(len(resposta.json()["conversations"]), 2)

    def test_parceira_ve_so_a_sua(self):
        self.client.force_login(self.parceira)
        resposta = self.client.get(reverse("whatsapp-conversations"))

        conversas = resposta.json()["conversations"]
        self.assertEqual(len(conversas), 1)
        self.assertEqual(conversas[0]["id"], self.conversa_joao.id)

    def test_parceira_nao_le_conversa_de_outro_aluno(self):
        self.client.force_login(self.parceira)
        resposta = self.client.get(reverse(
            "whatsapp-messages", args=[self.conversa_ana.id]
        ))
        self.assertEqual(resposta.status_code, 404)

    @mock.patch.dict(os.environ, TEST_ENV)
    def test_parceira_nao_envia_em_conversa_alheia(self):
        self.client.force_login(self.parceira)

        cliente = mock.Mock()
        with mock.patch.object(WhatsAppAccount, "get_client", return_value=cliente):
            resposta = self.client.post(
                reverse("whatsapp-send", args=[self.conversa_ana.id]),
                data=json.dumps({"body": "oi"}),
                content_type="application/json",
            )

        self.assertEqual(resposta.status_code, 404)
        cliente.send_text.assert_not_called()

    @mock.patch.dict(os.environ, TEST_ENV)
    def test_erro_de_negocio_volta_com_texto_legivel(self):
        # Fora da janela, a resposta precisa explicar o que fazer, não devolver
        # um código que a professora não sabe interpretar.
        self.conversa_ana.last_inbound_at = timezone.now() - timedelta(hours=30)
        self.conversa_ana.save(update_fields=["last_inbound_at"])

        self.client.force_login(self.dona)
        resposta = self.client.post(
            reverse("whatsapp-send", args=[self.conversa_ana.id]),
            data=json.dumps({"body": "oi"}),
            content_type="application/json",
        )

        self.assertEqual(resposta.status_code, 422)
        self.assertIn("24 horas", resposta.json()["detail"])

    def test_ligar_aluno_move_a_conversa_para_o_professor_dele(self):
        service.process_webhook(self.build_message_payload(
            wa_id="5511999998888", wamid="wamid.DDD"
        ))
        contato = WhatsAppContact.objects.get(wa_id="5511999998888")
        conversa = WhatsAppConversation.objects.get(contact=contato)

        self.client.force_login(self.dona)
        resposta = self.client.post(
            reverse("whatsapp-link-student", args=[conversa.id]),
            data=json.dumps({"student_id": self.aluno.id}),
            content_type="application/json",
        )

        self.assertEqual(resposta.status_code, 200)
        conversa.refresh_from_db()
        self.assertEqual(conversa.assigned_teacher, self.parceira)

    def test_marcar_como_lida_zera_o_contador(self):
        self.client.force_login(self.dona)
        self.assertEqual(self.conversa_ana.unread_count, 1)

        resposta = self.client.post(
            reverse("whatsapp-read", args=[self.conversa_ana.id])
        )

        self.assertEqual(resposta.status_code, 200)
        self.conversa_ana.refresh_from_db()
        self.assertEqual(self.conversa_ana.unread_count, 0)

    def test_filtro_de_nao_lidas(self):
        self.client.force_login(self.dona)
        self.conversa_ana.unread_count = 0
        self.conversa_ana.save(update_fields=["unread_count"])

        resposta = self.client.get(
            reverse("whatsapp-conversations"), {"filter": "unread"}
        )

        conversas = resposta.json()["conversations"]
        self.assertEqual(len(conversas), 1)
        self.assertEqual(conversas[0]["id"], self.conversa_joao.id)

    def test_busca_por_telefone_acha_com_e_sem_o_nono_digito(self):
        self.client.force_login(self.dona)

        resposta = self.client.get(
            reverse("whatsapp-conversations"), {"q": "41988369627"}
        )

        conversas = resposta.json()["conversations"]
        self.assertEqual(len(conversas), 1)
        self.assertEqual(conversas[0]["id"], self.conversa_joao.id)


SIGNUP_ENV = {
    "WHATSAPP_APP_ID": "app-123",
    "WHATSAPP_CONFIG_ID": "config-123",
    "WHATSAPP_APP_SECRET": APP_SECRET,
    "WHATSAPP_ES_FEATURE_TYPE": "whatsapp_business_app_onboarding",
}


class SignupTests(TestCase):
    """
    Conexão do número pelo Embedded Signup.

    O que mais importa aqui: na coexistência o número **não** é registrado,
    porque já está registrado no aplicativo do celular. Chamar /register
    quebraria a conexão, e nenhum teste de caminho feliz pegaria isso.
    """

    def setUp(self):
        self.dona = User.objects.create_user("bianca", password="x")

    def _fake_graph(self, chamadas):
        """Substitui a Graph API e guarda o que foi chamado, na ordem."""
        def falso(method, path, *, token="", params=None, json_body=None):
            chamadas.append((method, path, json_body))

            if path == "oauth/access_token":
                return {"access_token": "token-de-longa-duracao"}
            if path.endswith("/phone_numbers"):
                return {"data": [{
                    "id": "numero-1",
                    "display_phone_number": "+55 41 98836-9627",
                    "verified_name": "Cini English",
                    "quality_rating": "GREEN",
                }]}
            return {"success": True}

        return falso

    @mock.patch.dict(os.environ, SIGNUP_ENV)
    def test_conexao_completa_cria_a_conta(self):
        chamadas = []
        with mock.patch.object(signup, "_graph", self._fake_graph(chamadas)):
            account = signup.complete_signup(
                user=self.dona, code="codigo-do-popup", waba_id="waba-9"
            )

        self.assertEqual(account.status, WhatsAppAccount.STATUS_CONNECTED)
        self.assertTrue(account.is_active)
        self.assertTrue(account.is_coexistence)
        self.assertEqual(account.phone_number_id, "numero-1")
        self.assertEqual(account.waba_id, "waba-9")
        self.assertEqual(account.verified_name, "Cini English")
        self.assertEqual(account.get_access_token(), "token-de-longa-duracao")

    @mock.patch.dict(os.environ, SIGNUP_ENV)
    def test_nao_registra_o_numero(self):
        # A coexistência quebra se chamarmos /register: o número já está
        # registrado pelo aplicativo do celular.
        chamadas = []
        with mock.patch.object(signup, "_graph", self._fake_graph(chamadas)):
            signup.complete_signup(self.dona, "codigo", "waba-9")

        caminhos = [c[1] for c in chamadas]
        self.assertNotIn("numero-1/register", caminhos)
        self.assertFalse(any(p.endswith("/register") for p in caminhos))

    @mock.patch.dict(os.environ, SIGNUP_ENV)
    def test_assina_a_waba_e_dispara_as_duas_sincronizacoes(self):
        chamadas = []
        with mock.patch.object(signup, "_graph", self._fake_graph(chamadas)):
            signup.complete_signup(self.dona, "codigo", "waba-9")

        caminhos = [c[1] for c in chamadas]
        self.assertIn("waba-9/subscribed_apps", caminhos)

        # Contatos e histórico. A janela é de 24h e não se repete.
        sincronias = [c[2]["sync_type"] for c in chamadas
                      if c[1] == "numero-1/smb_app_data"]
        self.assertEqual(set(sincronias), {"smb_app_state_sync", "history"})

    @mock.patch.dict(os.environ, SIGNUP_ENV)
    def test_falha_na_importacao_nao_derruba_a_conexao(self):
        def falso(method, path, *, token="", params=None, json_body=None):
            if path == "oauth/access_token":
                return {"access_token": "tok"}
            if path.endswith("/phone_numbers"):
                return {"data": [{"id": "numero-1", "display_phone_number": "+55 41 9"}]}
            if path.endswith("/smb_app_data"):
                raise signup.SignupError("janela de sincronização expirada")
            return {}

        with mock.patch.object(signup, "_graph", falso):
            account = signup.complete_signup(self.dona, "codigo", "waba-9")

        # O canal fica de pé: as conversas novas continuam chegando, só o
        # passado não veio junto.
        self.assertEqual(account.status, WhatsAppAccount.STATUS_CONNECTED)
        self.assertTrue(account.is_active)
        self.assertIn("importação do histórico", account.last_error)

    @mock.patch.dict(os.environ, SIGNUP_ENV)
    def test_reconectar_nao_duplica_conta_nem_perde_conversas(self):
        chamadas = []
        with mock.patch.object(signup, "_graph", self._fake_graph(chamadas)):
            primeira = signup.complete_signup(self.dona, "codigo-1", "waba-9")
            segunda = signup.complete_signup(self.dona, "codigo-2", "waba-9")

        self.assertEqual(primeira.id, segunda.id)
        self.assertEqual(WhatsAppAccount.objects.count(), 1)

    @mock.patch.dict(os.environ, SIGNUP_ENV)
    def test_numero_ja_ligado_a_outra_conta_e_recusado(self):
        outro = User.objects.create_user("outro", password="x")
        WhatsAppAccount.objects.create(user=outro, phone_number_id="numero-1")

        chamadas = []
        with mock.patch.object(signup, "_graph", self._fake_graph(chamadas)):
            with self.assertRaises(signup.SignupError) as ctx:
                signup.complete_signup(self.dona, "codigo", "waba-9")

        self.assertIn("outra conta", str(ctx.exception))

    @mock.patch.dict(os.environ, SIGNUP_ENV)
    def test_waba_sem_numero_da_erro_util(self):
        def falso(method, path, *, token="", params=None, json_body=None):
            if path == "oauth/access_token":
                return {"access_token": "tok"}
            if path.endswith("/phone_numbers"):
                return {"data": []}
            return {}

        with mock.patch.object(signup, "_graph", falso):
            with self.assertRaises(signup.SignupError) as ctx:
                signup.complete_signup(self.dona, "codigo", "waba-9")

        self.assertIn("nenhum número", str(ctx.exception).lower())

    @mock.patch.dict(os.environ, {"WHATSAPP_APP_ID": "", "WHATSAPP_CONFIG_ID": "",
                                 "WHATSAPP_APP_SECRET": ""})
    def test_ambiente_sem_configuracao_recusa_cedo(self):
        with self.assertRaises(signup.SignupError):
            signup.complete_signup(self.dona, "codigo", "waba-9")

    @mock.patch.dict(os.environ, SIGNUP_ENV)
    def test_desconectar_apaga_o_token_e_mantem_o_historico(self):
        chamadas = []
        with mock.patch.object(signup, "_graph", self._fake_graph(chamadas)):
            account = signup.complete_signup(self.dona, "codigo", "waba-9")

        signup.disconnect(account)
        account.refresh_from_db()

        self.assertFalse(account.is_active)
        self.assertEqual(account.status, WhatsAppAccount.STATUS_DISCONNECTED)
        self.assertEqual(account.access_token_encrypted, "")
        self.assertFalse(account.can_send)
        # A conta continua existindo, e com ela as conversas guardadas.
        self.assertEqual(WhatsAppAccount.objects.count(), 1)


class ManualConnectTests(TestCase):
    """
    Conexão por token colado à mão, o caminho do piloto.

    O risco aqui não é falhar, é *parecer* que funcionou: uma conta marcada
    como conectada com token inválido, ou sem a app assinada à WABA, fica
    muda sem dar erro nenhum.
    """

    def setUp(self):
        self.dona = User.objects.create_user("bianca", password="x")

    def _fake_graph(self, chamadas, falhar_em=""):
        def falso(method, path, *, token="", params=None, json_body=None):
            chamadas.append((method, path, json_body))
            if falhar_em and falhar_em in path:
                raise signup.SignupError("recusado pela Meta")
            if path.endswith("/phone_numbers"):
                return {"data": [{
                    "id": "numero-1",
                    "display_phone_number": "+55 41 98836-9627",
                    "verified_name": "Cini English",
                    "quality_rating": "GREEN",
                }]}
            return {"success": True}
        return falso

    def test_conecta_e_guarda_o_token_cifrado(self):
        chamadas = []
        with mock.patch.object(signup, "_graph", self._fake_graph(chamadas)):
            account = signup.connect_manually(
                self.dona, access_token="EAAG-token", waba_id="waba-9"
            )

        self.assertEqual(account.status, WhatsAppAccount.STATUS_CONNECTED)
        self.assertTrue(account.is_active)
        self.assertEqual(account.phone_number_id, "numero-1")
        self.assertEqual(account.get_access_token(), "EAAG-token")
        self.assertNotIn("EAAG-token", account.access_token_encrypted)

    def test_nao_registra_o_numero(self):
        # Vale aqui pelo mesmo motivo do Embedded Signup: na coexistência o
        # número já está registrado pelo aplicativo do celular.
        chamadas = []
        with mock.patch.object(signup, "_graph", self._fake_graph(chamadas)):
            signup.connect_manually(self.dona, "tok", "waba-9")

        self.assertFalse(any(c[1].endswith("/register") for c in chamadas))

    def test_assina_a_app_a_waba(self):
        chamadas = []
        with mock.patch.object(signup, "_graph", self._fake_graph(chamadas)):
            signup.connect_manually(self.dona, "tok", "waba-9")

        self.assertIn("waba-9/subscribed_apps", [c[1] for c in chamadas])

    def test_falha_ao_assinar_a_waba_aborta_a_conexao(self):
        # É a falha mais traiçoeira do caminho manual: sem a assinatura, nada
        # chega e tudo parece certo. Melhor não conectar do que conectar mudo.
        chamadas = []
        falso = self._fake_graph(chamadas, falhar_em="subscribed_apps")

        with mock.patch.object(signup, "_graph", falso):
            with self.assertRaises(signup.SignupError) as ctx:
                signup.connect_manually(self.dona, "tok", "waba-9")

        self.assertIn("nenhuma mensagem chega", str(ctx.exception))
        self.assertEqual(WhatsAppAccount.objects.count(), 0)

    def test_token_invalido_nao_cria_conta(self):
        chamadas = []
        falso = self._fake_graph(chamadas, falhar_em="phone_numbers")

        with mock.patch.object(signup, "_graph", falso):
            with self.assertRaises(signup.SignupError):
                signup.connect_manually(self.dona, "token-podre", "waba-9")

        self.assertEqual(WhatsAppAccount.objects.count(), 0)

    def test_campos_obrigatorios(self):
        with self.assertRaises(signup.SignupError):
            signup.connect_manually(self.dona, "", "waba-9")
        with self.assertRaises(signup.SignupError):
            signup.connect_manually(self.dona, "tok", "")

    def test_pode_pular_a_importacao_do_historico(self):
        chamadas = []
        with mock.patch.object(signup, "_graph", self._fake_graph(chamadas)):
            signup.connect_manually(self.dona, "tok", "waba-9", sync_history=False)

        self.assertFalse(any("smb_app_data" in c[1] for c in chamadas))

    def test_numero_de_outra_conta_e_recusado(self):
        outro = User.objects.create_user("outro", password="x")
        WhatsAppAccount.objects.create(user=outro, phone_number_id="numero-1")

        chamadas = []
        with mock.patch.object(signup, "_graph", self._fake_graph(chamadas)):
            with self.assertRaises(signup.SignupError) as ctx:
                signup.connect_manually(self.dona, "tok", "waba-9")

        self.assertIn("outra conta", str(ctx.exception))

    def test_endpoint_nao_devolve_o_token(self):
        self.client.force_login(self.dona)
        chamadas = []

        with mock.patch.object(signup, "_graph", self._fake_graph(chamadas)):
            resposta = self.client.post(
                reverse("whatsapp-connect-manual"),
                data=json.dumps({"access_token": "EAAG-segredo", "waba_id": "waba-9"}),
                content_type="application/json",
            )

        self.assertEqual(resposta.status_code, 200)
        self.assertNotIn("EAAG-segredo", resposta.content.decode())

    def test_parceiro_nao_conecta_pelo_caminho_manual(self):
        from core.models import UserProfile

        parceira = User.objects.create_user("parceira", password="x")
        UserProfile.objects.update_or_create(
            user=parceira,
            defaults={"user_profile": UserProfile.PROFILE_PARTNER_TEACHER},
        )
        self.client.force_login(parceira)

        resposta = self.client.post(
            reverse("whatsapp-connect-manual"),
            data=json.dumps({"access_token": "tok", "waba_id": "waba-9"}),
            content_type="application/json",
        )

        self.assertEqual(resposta.status_code, 403)
        self.assertEqual(WhatsAppAccount.objects.count(), 0)


class SignupApiTests(TestCase):
    def setUp(self):
        self.dona = User.objects.create_user("bianca", password="x")

    @mock.patch.dict(os.environ, SIGNUP_ENV)
    def test_config_nao_expoe_o_segredo_da_app(self):
        self.client.force_login(self.dona)
        resposta = self.client.get(reverse("whatsapp-signup-config"))

        dados = resposta.json()
        self.assertTrue(dados["configured"])
        self.assertEqual(dados["app_id"], "app-123")
        self.assertNotIn("app_secret", dados)
        self.assertNotIn(APP_SECRET, json.dumps(dados))

    def test_config_exige_sessao(self):
        self.assertEqual(
            self.client.get(reverse("whatsapp-signup-config")).status_code, 401
        )

    @mock.patch.dict(os.environ, SIGNUP_ENV)
    def test_professor_parceiro_nao_conecta_numero(self):
        from core.models import UserProfile

        parceira = User.objects.create_user("parceira", password="x")
        UserProfile.objects.update_or_create(
            user=parceira,
            defaults={"user_profile": UserProfile.PROFILE_PARTNER_TEACHER},
        )

        self.client.force_login(parceira)
        resposta = self.client.post(
            reverse("whatsapp-signup-complete"),
            data=json.dumps({"code": "x", "waba_id": "y"}),
            content_type="application/json",
        )

        self.assertEqual(resposta.status_code, 403)
        self.assertEqual(WhatsAppAccount.objects.count(), 0)

    @mock.patch.dict(os.environ, SIGNUP_ENV)
    def test_erro_da_meta_volta_como_422_legivel(self):
        self.client.force_login(self.dona)

        def falso(method, path, *, token="", params=None, json_body=None):
            raise signup.SignupError("O código de autorização expirou.")

        with mock.patch.object(signup, "_graph", falso):
            resposta = self.client.post(
                reverse("whatsapp-signup-complete"),
                data=json.dumps({"code": "velho", "waba_id": "waba-9"}),
                content_type="application/json",
            )

        self.assertEqual(resposta.status_code, 422)
        self.assertIn("expirou", resposta.json()["detail"])


class TokenEncryptionTests(TestCase):
    def test_token_nao_fica_em_claro_no_banco(self):
        dono = User.objects.create_user("prof", password="x")
        conta = WhatsAppAccount.objects.create(user=dono, phone_number_id="999")
        conta.set_access_token("EAAG-token-real")
        conta.save()

        conta.refresh_from_db()
        self.assertNotIn("EAAG-token-real", conta.access_token_encrypted)
        self.assertEqual(conta.get_access_token(), "EAAG-token-real")
