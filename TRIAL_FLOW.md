# Trial gratuito de 7 dias (sem cartão)

## Fluxo

1. **Landing** → Clicar em criar conta
2. **Signup** → Cadastrar (usuário, email, senha, nome)
3. **Login automático** → Redireciona para `/` (dashboard/app)
4. **7 dias** → Uso completo sem pedir cartão
5. **Dia 5** → Aviso no sistema (banner) + email "Seu trial termina em 2 dias"
6. **Dia 7** → Sistema trava, redireciona para `/planos/`
7. **Planos** → Usuário escolhe plano e paga (Stripe, cobrança imediata)

## Por que sem cartão

O professor já investiu tempo: cadastrou alunos, criou aulas, viu a agenda. A probabilidade de converter sobe bastante em relação a pedir cartão antes de experimentar.

## Configuração técnica

- **trial_ends_at** (UserProfile): fim do trial = `created_at + 7 dias`
- **Banner**: contexto `trial_banner` (core/context_processors.py), exibido quando `trial_days_left <= 2`
- **Email dia 5**: `python manage.py send_trial_ending_email` (agendar no cron, ex: a cada 6h)

## Migração

Rodar: `python manage.py migrate` (0040_userprofile_trial)

## Usuários existentes

- Quem já assinou via Stripe: continua funcionando (subscription.is_active)
- Novos cadastros: passam pelo fluxo de trial sem cartão
