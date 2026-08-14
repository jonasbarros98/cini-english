#!/usr/bin/env python
"""Runner de desenvolvimento local: use este ficheiro em vez do manage.py.

Motivo: o `.env` deste repositório contém credenciais REAIS (Resend, n8n).
Se você rodar o `manage.py` diretamente na sua máquina, qualquer fluxo que
dispare e-mail envia e-mail de verdade para usuários reais, e o signup chama
o webhook de produção do n8n.

Este runner neutraliza as integrações externas ANTES de o Django carregar as
definições:

  - E-mail: sem RESEND_API_KEY e sem SMTP, o `config/settings.py` cai no
    backend de consola, o e-mail é impresso no terminal em vez de enviado.
  - n8n: webhook de onboarding desligado.
  - Estáticos: modo simples, para o runserver os servir sem `collectstatic`.

O truque está na ordem: o `load_dotenv()` chamado dentro do settings.py não
sobrescreve variáveis que já existam no ambiente, por isso definir estas
chaves aqui (mesmo vazias) vence o que estiver no .env.

Uso:
    .venv/Scripts/python.exe dev_local.py runserver 8000 --insecure
"""
import os
import sys

# Precisa acontecer antes de qualquer import do Django.
os.environ.update({
    "RESEND_API_KEY": "",
    "EMAIL_HOST_USER": "",
    "EMAIL_HOST_PASSWORD": "",
    "N8N_ONBOARDING_WEBHOOK_ENABLED": "false",
    "DJANGO_STATICFILES_SIMPLE": "1",
})


def main():
    """Run administrative tasks com as integrações externas desligadas."""
    print("[dev_local] e-mail -> consola | n8n -> desligado | estaticos -> modo simples")
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
