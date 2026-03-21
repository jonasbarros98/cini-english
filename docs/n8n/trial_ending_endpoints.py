# =============================================================================
# TRIAL ENDING — Referência (implementação no Django)
# =============================================================================
#
# As views e rotas estão integradas no projeto:
#   - core/views.py: _n8n_internal_token_ok, trial_ending_users, mark_trial_email_sent
#   - core/urls.py:
#       GET  /api/internal/trial-ending-users/
#       POST /api/internal/mark-trial-email-sent/
#
# Token: N8N_ONBOARDING_STATUS_TOKEN (header X-Internal-Token ou ?token= /
#        ?onboarding_check_token=) — mesmo mecanismo de onboarding_progress_internal.
#
# Workflow n8n: docs/n8n/Trial Ending - EducaFlowOne - oficial.json
# Documentação: docs/n8n/README.md — seção "Workflow: Trial Ending"
#
# =============================================================================
