---
name: codebase_models
description: All Django models in core/models.py and their purpose
type: project
---

All models live in `core/models.py` (1246 lines). 53 migrations total.

| Model | Purpose |
|-------|---------|
| Student | Core entity: student profile, billing type, CEFR level, plan, FK to User (teacher) + optional assigned_teacher |
| StudentShareToken | Public (no-login) access token for Student Area; one active per student |
| Lesson | Individual lesson event: date, time, status (confirmed/pending/canceled), realized flag |
| Task | Teacher's to-do item: title, status (todo/doing/done), date, due_date, notes |
| StudentHomework | Homework assigned to student: title, description, due_date, status (pending/done), student_response, teacher_feedback |
| StudentHomeworkMessage | Chat-style messages on a homework: sender (student/teacher), FK to User for teacher messages |
| StudentHomeworkMessageRead | Read-receipts for teacher (for unread badge) |
| Invoice | Monthly billing record per student (legacy — FinancialEntry is the active billing system) |
| FinancialEntry | Active financial record: amount, installments, due_date, status, payment_method, beneficiary_user |
| BillingLog | Log of billing messages sent to students (WhatsApp/email/SMS) |
| LessonPlan | Lesson plan per student+date: goals text, links (newline-separated) |
| LessonPlanAttachment | File attachments for LessonPlan (PDF, Word, audio, video, etc.) |
| StudentMaterial | Standalone material shared with student: file or link, independent of LessonPlan |
| UserProfile | Extended user profile: role (professor/prof_parceiro), subscription_exempt, trial_ends_at, Google OAuth fields, public booking settings, admin fields |
| Subscription | Stripe subscription record: tier (basic/premium/platinum), plan (monthly/semestral/annual), status, stripe IDs |
| DayNote | Per-user per-date free text note shown in calendar |
| StripeEvent | Idempotency log for Stripe webhook events |
| SupportTicket | In-app bug/feedback ticket: category, impact, title, description, context fields |
| PublicBookingRequest | Student booking request via public calendar link: student contact info + requested slot |
| RetentionEmailLog | History of manual retention emails sent by admin |
