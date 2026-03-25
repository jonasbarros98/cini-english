---
name: project_overview
description: What EducaflowOne does, its feature set, and current state
type: project
---

EducaflowOne is a SaaS web application for private language teachers (primarily English) in Brazil to manage their teaching business.

**Core features implemented:**
- Multi-tenant: each teacher gets their own account; partner teacher (prof. parceiro) role for sub-teachers
- Student management (ficha do aluno): status active/paused/ended, CEFR level, billing type, progress tracking
- Calendar (calendar_new): lesson scheduling with confirmed/pending/canceled/done statuses, day notes
- Financial module (financeiro): FinancialEntry (lançamentos), Invoice, BillingLog (cobrança via WhatsApp message generator)
- Lesson Planning (planejamento): LessonPlan with links, goals, and file attachments per student
- Student Area (área do aluno): public token-based page for students to view homework/lessons/materials
- Homework system (StudentHomework): assign tasks to students, messaging thread between teacher and student
- Student Materials: file/link sharing with students (independent of lesson planning)
- Tasks (tarefas): teacher's own to-do list
- Stripe subscription billing: 3 tiers (Basic/Premium/Platinum) x 3 periodicities (monthly/semestral/annual), trial system (7 days free)
- Google OAuth Sign-In
- Support ticket system: in-app bug/feedback reporting
- Public booking calendar (agenda publica): shareable scheduling link (Premium+)
- Admin panel (painel-admin): user management, retention email sending (manual)
- n8n webhook integration for onboarding automations
- Email via Resend (django-anymail) or SMTP fallback
- Deployed on Railway with PostgreSQL

**Current deployment:** https://www.educaflowone.com.br (Railway)

**State as of 2026-03-24:** Functionally complete and in production. Main issues are code quality/hardening concerns, not missing core features.
