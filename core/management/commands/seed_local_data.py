"""Popula o banco LOCAL com dados de teste realistas.

Cria uma professora com alunos, aulas, lançamentos financeiros, planejamentos,
tarefas de casa, materiais e agendamentos, o suficiente para abrir qualquer
tela do sistema e ver conteúdo de verdade.

Este comando NUNCA deve rodar em produção. Ele aborta sozinho se detectar
ambiente Railway ou um banco que não seja localhost.

Uso:
    .venv/Scripts/python.exe dev_local.py seed_local_data
    .venv/Scripts/python.exe dev_local.py seed_local_data --reset
"""
import os
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core.models import (
    BillingLog,
    DayNote,
    FinancialEntry,
    Lesson,
    LessonPlan,
    PublicBookingRequest,
    Student,
    StudentHomework,
    StudentHomeworkMessage,
    StudentMaterial,
    StudentShareToken,
    Subscription,
    SupportTicket,
    TeacherMaterial,
    UserProfile,
)

# Usuários criados por este seed. Serve para o --reset saber o que apagar.
SEED_USERNAMES = ["cini", "parceiro_rafa"]
SEED_PASSWORD = "local-dev-2026"


def _abortar_se_nao_for_local():
    """Trava de segurança: só permite rodar contra um banco local."""
    railway = [k for k in ("RAILWAY_ENVIRONMENT", "RAILWAY_PROJECT_ID", "RAILWAY_SERVICE_ID") if os.environ.get(k)]
    if railway:
        raise CommandError(
            f"Ambiente Railway detectado ({', '.join(railway)}). "
            "Este comando cria dados fictícios e não pode rodar em produção."
        )

    host = (settings.DATABASES["default"].get("HOST") or "").strip()
    if host not in ("", "localhost", "127.0.0.1"):
        raise CommandError(
            f"O banco configurado aponta para '{host}', que não é local. "
            "Abortando para não escrever dados fictícios num banco remoto."
        )


class Command(BaseCommand):
    help = "Popula o banco local com dados de teste (professora, alunos, aulas, financeiro)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Apaga os dados de teste criados anteriormente antes de recriar.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        _abortar_se_nao_for_local()

        if options["reset"]:
            apagados, _ = User.objects.filter(username__in=SEED_USERNAMES).delete()
            self.stdout.write(self.style.WARNING(f"--reset: {apagados} registros removidos (cascata)."))

        hoje = timezone.localdate()
        agora = timezone.now()

        professora = self._criar_professora(agora)
        parceiro = self._criar_parceiro(professora)
        alunos = self._criar_alunos(professora, parceiro, hoje)
        n_aulas = self._criar_aulas(professora, alunos, hoje)
        n_fin = self._criar_financeiro(professora, alunos, hoje)
        self._criar_planejamentos(professora, alunos, hoje)
        self._criar_tarefas_de_casa(professora, alunos, hoje)
        self._criar_materiais(professora, alunos, hoje)
        self._criar_extras(professora, alunos, hoje)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Dados de teste criados."))
        self.stdout.write("")
        self.stdout.write(f"  Login professora : cini / {SEED_PASSWORD}")
        self.stdout.write(f"  Login parceiro   : parceiro_rafa / {SEED_PASSWORD}")
        self.stdout.write(f"  Alunos           : {len(alunos)}")
        self.stdout.write(f"  Aulas            : {n_aulas}")
        self.stdout.write(f"  Lançamentos      : {n_fin}")
        token = StudentShareToken.get_active_token(alunos[0])
        if token:
            self.stdout.write(f"  Área do aluno    : http://localhost:8000/aluno/{token.token}/")
        perfil = professora.profile
        if perfil.slug_publico:
            self.stdout.write(f"  Agenda pública   : http://localhost:8000/agendar/{perfil.slug_publico}/")

    # ── usuários ────────────────────────────────────────────────────────

    def _criar_professora(self, agora):
        user, criado = User.objects.get_or_create(
            username="cini",
            defaults={
                "email": "cini@local.test",
                "first_name": "Cini",
                "last_name": "Barros",
            },
        )
        if criado:
            user.set_password(SEED_PASSWORD)
            user.save()

        perfil, _ = UserProfile.objects.get_or_create(user=user)
        perfil.user_profile = UserProfile.PROFILE_TEACHER
        perfil.phone = "(41) 99999-0001"
        perfil.city = "Curitiba"
        perfil.state = "PR"
        perfil.slug_publico = "cini-barros"
        perfil.agenda_publica_ativa = True
        perfil.public_booking_duration = 60
        # 1 = segunda … 5 = sexta (0 = domingo)
        perfil.public_availability = {str(d): ["18:00", "21:00"] for d in range(1, 6)}
        perfil.welcome_dismissed_forever = True
        perfil.save()

        # Assinatura Premium ativa: libera aluno ilimitado, parceiros e agenda pública.
        Subscription.objects.update_or_create(
            user=user,
            defaults={
                "tier": Subscription.TIER_PREMIUM,
                "plan": Subscription.PLAN_MONTHLY,
                "status": Subscription.STATUS_ACTIVE,
                "current_period_start": agora - timedelta(days=10),
                "current_period_end": agora + timedelta(days=20),
            },
        )
        return user

    def _criar_parceiro(self, professora):
        user, criado = User.objects.get_or_create(
            username="parceiro_rafa",
            defaults={
                "email": "rafa@local.test",
                "first_name": "Rafael",
                "last_name": "Lima",
            },
        )
        if criado:
            user.set_password(SEED_PASSWORD)
            user.save()

        perfil, _ = UserProfile.objects.get_or_create(user=user)
        perfil.user_profile = UserProfile.PROFILE_PARTNER_TEACHER
        perfil.phone = "(41) 99999-0002"
        perfil.save()

        professora.profile.partner_teachers.add(perfil)
        return user

    # ── alunos ──────────────────────────────────────────────────────────

    def _criar_alunos(self, professora, parceiro, hoje):
        definicoes = [
            {
                "name": "Marina Alves",
                "level": "B2",
                "status": Student.STATUS_ACTIVE,
                "billing_type": Student.BILLING_MONTHLY_FIXED,
                "plan_name": "Mensal 8 aulas",
                "monthly_amount": Decimal("640.00"),
                "guardians": "Responsável próprio",
                "phone": "(41) 98888-1001",
                "email": "marina@local.test",
                "default_due_day": 5,
                "lessons_total": 8,
                "lessons_done": 5,
                "teacher_notes": "Prepara entrevista de emprego. Focar em fluência e vocabulário corporativo.",
            },
            {
                "name": "Pedro Henrique Costa",
                "level": "A2",
                "status": Student.STATUS_ACTIVE,
                "billing_type": Student.BILLING_PACKAGE,
                "plan_name": "Pacote 10 aulas",
                "guardians": "Juliana Costa (mãe)",
                "phone": "(41) 98888-1002",
                "email": "juliana.costa@local.test",
                "default_due_day": 10,
                "lessons_total": 10,
                "lessons_done": 3,
                "teacher_notes": "12 anos. Gosta de jogos, usar vocabulário de games.",
            },
            {
                "name": "Beatriz Nogueira",
                "level": "C1",
                "status": Student.STATUS_ACTIVE,
                "billing_type": Student.BILLING_PER_LESSON,
                "per_lesson_amount": Decimal("95.00"),
                "phone": "(41) 98888-1003",
                "email": "bia.nog@local.test",
                "guardians": "Responsável próprio",
                "lessons_total": 0,
                "lessons_done": 12,
                "teacher_notes": "Aulas avulsas conforme agenda. Prepara IELTS.",
                "assigned_teacher": parceiro,
            },
            {
                "name": "Lucas Ferreira",
                "level": "B1",
                "status": Student.STATUS_ACTIVE,
                "billing_type": Student.BILLING_MONTHLY_FIXED,
                "plan_name": "Mensal 4 aulas",
                "monthly_amount": Decimal("360.00"),
                "phone": "(41) 98888-1004",
                "email": "lucas.f@local.test",
                "guardians": "Responsável próprio",
                "default_due_day": 15,
                "lessons_total": 4,
                "lessons_done": 4,
                "teacher_notes": "Pagamento costuma atrasar alguns dias.",
            },
            {
                "name": "Sofia Ramos",
                "level": "A1",
                "status": Student.STATUS_PAUSED,
                "billing_type": Student.BILLING_PACKAGE,
                "plan_name": "Pacote 8 aulas",
                "guardians": "Marcos Ramos (pai)",
                "phone": "(41) 98888-1005",
                "email": "marcos.ramos@local.test",
                "lessons_total": 8,
                "lessons_done": 2,
                "teacher_notes": "Pausou em julho por viagem da família. Retorno previsto para setembro.",
            },
            {
                "name": "Diego Martins",
                "level": "B2",
                "status": Student.STATUS_ENDED,
                "billing_type": Student.BILLING_OTHER,
                "phone": "(41) 98888-1006",
                "email": "diego.m@local.test",
                "guardians": "Responsável próprio",
                "lessons_total": 20,
                "lessons_done": 20,
                "teacher_notes": "Concluiu o objetivo (intercâmbio). Encerrado em bons termos.",
            },
        ]

        alunos = []
        for d in definicoes:
            assigned = d.pop("assigned_teacher", None)
            aluno, _ = Student.objects.get_or_create(
                user=professora,
                name=d["name"],
                defaults={
                    **d,
                    "assigned_teacher": assigned,
                    "plan_start_date": hoje - timedelta(days=90),
                    "preferred_payment_method": Student.PAYMENT_METHOD_PIX,
                    "pix_key": "cini@local.test",
                },
            )
            alunos.append(aluno)

        # Um aluno com link público ativo, para testar a Área do Aluno.
        if not StudentShareToken.get_active_token(alunos[0]):
            StudentShareToken.create_new_active_token(alunos[0])

        return alunos

    # ── agenda ──────────────────────────────────────────────────────────

    def _criar_aulas(self, professora, alunos, hoje):
        ativos = [a for a in alunos if a.status == Student.STATUS_ACTIVE]
        criadas = 0

        # Passado: aulas realizadas. Futuro: confirmadas e pendentes.
        for offset in range(-21, 15):
            dia = hoje + timedelta(days=offset)
            if dia.weekday() > 4:  # sem aula no fim de semana
                continue

            aluno = ativos[(dia.toordinal()) % len(ativos)]
            professor = aluno.assigned_teacher or professora

            if offset < 0:
                status, realizada = "confirmed", True
            elif offset == 0:
                status, realizada = "confirmed", False
            elif offset % 3 == 0:
                status, realizada = "pending", False
            else:
                status, realizada = "confirmed", False

            _, criado = Lesson.objects.get_or_create(
                user=professor,
                student=aluno,
                date=dia,
                defaults={
                    "time": "18:00" if dia.weekday() % 2 == 0 else "19:30",
                    "title": f"Aula de inglês com {aluno.name.split()[0]}",
                    "info": "Revisão + conversação.",
                    "status": status,
                    "realized": realizada,
                },
            )
            criadas += int(criado)

        # Uma aula cancelada, para a tela mostrar os três status.
        _, criado = Lesson.objects.get_or_create(
            user=professora,
            student=ativos[0],
            date=hoje - timedelta(days=4),
            defaults={
                "time": "20:00",
                "title": "Aula extra (remarcada)",
                "info": "Aluna avisou no dia anterior.",
                "status": "canceled",
                "realized": False,
            },
        )
        return criadas + int(criado)

    # ── financeiro ──────────────────────────────────────────────────────

    def _criar_financeiro(self, professora, alunos, hoje):
        marina, pedro, beatriz, lucas = alunos[0], alunos[1], alunos[2], alunos[3]

        lancamentos = [
            # (aluno, descrição, valor, dias p/ vencimento, status, dias p/ pagamento)
            (marina, "Mensalidade agosto", Decimal("640.00"), -8, FinancialEntry.STATUS_PAID, -8),
            (marina, "Mensalidade setembro", Decimal("640.00"), 22, FinancialEntry.STATUS_PENDING, None),
            (pedro, "Pacote 10 aulas", Decimal("850.00"), 3, FinancialEntry.STATUS_PENDING, None),
            (beatriz, "Aulas avulsas de julho", Decimal("380.00"), -20, FinancialEntry.STATUS_PAID, -19),
            (beatriz, "Aulas avulsas de agosto", Decimal("285.00"), 12, FinancialEntry.STATUS_PENDING, None),
            (lucas, "Mensalidade agosto", Decimal("360.00"), -12, FinancialEntry.STATUS_OVERDUE, None),
            (lucas, "Mensalidade julho", Decimal("360.00"), -42, FinancialEntry.STATUS_PAID, -35),
        ]

        criados = 0
        for aluno, descricao, valor, dias_venc, status, dias_pag in lancamentos:
            vencimento = hoje + timedelta(days=dias_venc)
            beneficiario = aluno.assigned_teacher or professora
            entrada, criado = FinancialEntry.objects.get_or_create(
                user=professora,
                student=aluno,
                description=descricao,
                defaults={
                    "beneficiary_user": beneficiario,
                    "amount": valor,
                    "issue_date": vencimento - timedelta(days=25),
                    "due_date": vencimento,
                    "payment_date": hoje + timedelta(days=dias_pag) if dias_pag is not None else None,
                    "status": status,
                    "payment_method": FinancialEntry.PAYMENT_METHOD_PIX,
                },
            )
            criados += int(criado)

            # O lançamento vencido tem histórico de cobrança enviada.
            if criado and status == FinancialEntry.STATUS_OVERDUE:
                BillingLog.objects.create(
                    financial_entry=entrada,
                    user=professora,
                    message_type=BillingLog.MESSAGE_TYPE_OVERDUE,
                    send_method=BillingLog.SEND_METHOD_WHATSAPP,
                    message_content=(
                        f"Oi {aluno.name.split()[0]}! Passando para lembrar da mensalidade "
                        f"de R$ {valor} que venceu dia {vencimento:%d/%m}. Qualquer coisa me avisa!"
                    ),
                )
        return criados

    # ── planejamento ────────────────────────────────────────────────────

    def _criar_planejamentos(self, professora, alunos, hoje):
        planos = [
            (alunos[0], hoje + timedelta(days=1), "Simulação de entrevista em inglês.\nRevisar past perfect.",
             "https://docs.google.com/presentation/d/exemplo\nhttps://youtube.com/watch?v=exemplo"),
            (alunos[1], hoje + timedelta(days=2), "Vocabulário de games. Present continuous.", ""),
            (alunos[2], hoje + timedelta(days=3), "IELTS Speaking Part 2, cue cards.", "https://ielts.org/exemplo"),
        ]
        for aluno, data, objetivos, links in planos:
            LessonPlan.objects.get_or_create(
                user=professora,
                student=aluno,
                date=data,
                defaults={"goals": objetivos, "links": links},
            )

    # ── tarefas de casa ─────────────────────────────────────────────────

    def _criar_tarefas_de_casa(self, professora, alunos, hoje):
        marina, pedro = alunos[0], alunos[1]

        tarefa, criada = StudentHomework.objects.get_or_create(
            student=marina,
            assigned_by=professora,
            title="Gravar áudio de 2 minutos se apresentando",
            defaults={
                "description": "Fale sobre sua experiência profissional, como numa entrevista.",
                "due_date": hoje + timedelta(days=2),
                "status": StudentHomework.STATUS_PENDING,
            },
        )
        if criada:
            StudentHomeworkMessage.objects.create(
                homework=tarefa,
                sender=StudentHomeworkMessage.SENDER_STUDENT,
                message="Professora, posso entregar sexta? Estou com prova essa semana.",
            )
            StudentHomeworkMessage.objects.create(
                homework=tarefa,
                sender=StudentHomeworkMessage.SENDER_TEACHER,
                message="Claro, Marina! Sexta está ótimo.",
                created_by=professora,
            )

        StudentHomework.objects.get_or_create(
            student=pedro,
            assigned_by=professora,
            title="Exercícios de present continuous, págs. 24 e 25",
            defaults={
                "description": "Fazer os exercícios 1 a 6.",
                "due_date": hoje - timedelta(days=3),
                "status": StudentHomework.STATUS_DONE,
                "student_response": "Terminei! Tive dúvida no exercício 4.",
                "teacher_feedback": "Muito bom, Pedro. Vamos revisar o 4 na próxima aula.",
            },
        )

    # ── materiais ───────────────────────────────────────────────────────

    def _criar_materiais(self, professora, alunos, hoje):
        # Só materiais do tipo link, evita depender de upload de ficheiro real.
        StudentMaterial.objects.get_or_create(
            student=alunos[0],
            user=professora,
            title="Lista de phrasal verbs para entrevista",
            defaults={
                "material_type": StudentMaterial.TYPE_LINK,
                "external_url": "https://example.com/phrasal-verbs",
                "material_date": hoje - timedelta(days=5),
            },
        )
        for titulo, tags in [
            ("Warm-ups para aula de conversação", "conversação,warm-up"),
            ("Banco de cue cards IELTS", "ielts,speaking,C1"),
            ("Jogos de vocabulário para crianças", "kids,vocabulário,A1"),
        ]:
            TeacherMaterial.objects.get_or_create(
                user=professora,
                title=titulo,
                defaults={
                    "material_type": TeacherMaterial.TYPE_LINK,
                    "external_url": "https://example.com/material",
                    "tags": tags,
                    "description": "Material de apoio (dado de teste).",
                },
            )

    # ── extras ──────────────────────────────────────────────────────────

    def _criar_extras(self, professora, alunos, hoje):
        DayNote.objects.get_or_create(
            user=professora,
            date=hoje,
            defaults={"text": "Confirmar pagamento do Lucas e enviar material da Marina."},
        )
        DayNote.objects.get_or_create(
            user=professora,
            date=hoje + timedelta(days=7),
            defaults={"text": "Feriado, sem aulas."},
        )

        PublicBookingRequest.objects.get_or_create(
            teacher=professora,
            student_email="interessada@local.test",
            defaults={
                "requested_date": hoje + timedelta(days=4),
                "requested_time": "19:00",
                "student_name": "Camila Souza",
                "student_whatsapp": "(41) 97777-2020",
                "subject": "Inglês para viagem",
                "notes": "Viaja em novembro, quer aulas focadas em situações de viagem.",
                "status": PublicBookingRequest.STATUS_PENDING,
            },
        )

        SupportTicket.objects.get_or_create(
            ticket_id="LOCAL-0001",
            defaults={
                "user": professora,
                "category": SupportTicket.CATEGORY_UX,
                "impact": SupportTicket.IMPACT_LOW,
                "title": "Filtro do financeiro volta ao padrão",
                "description": "Ao voltar da ficha do aluno, o filtro de status do financeiro é resetado.",
                "page": "/financeiro/",
                "url": "http://localhost:8000/financeiro/",
            },
        )
