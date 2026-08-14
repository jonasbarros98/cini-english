---
name: educaflow-deploy
description: Publicar uma alteração do EducaflowOne em produção com segurança, do ambiente local até a verificação no ar. Use sempre que for fazer merge na main, deploy, redeploy, mexer em variável do Railway, ou quando precisar reverter algo que já subiu. Gatilhos, deploy, publicar, subir para produção, merge na main, mandar pro ar, reverter, rollback, voltar versão, mexer no Railway, criar variável, o site caiu, o deploy quebrou.
---

# Deploy do EducaflowOne

Sistema em produção com professores pagantes. Cada deploy vale um cuidado real.

## O terreno

- Repositório público `jonasbarros98/cini-english`, projeto em `C:\Users\jonas\OneDrive\Área de Trabalho\PYTHON\Cini English`.
- Merge na `main` mais push, e o Railway builda sozinho pelo **Dockerfile** (confirmado em Deployments, Details, Builder).
- O ambiente correto no Railway é o **`cini-english`**. Existe um segundo ambiente chamado `production` que está abandonado e engana: ele mostra um deploy antigo e um serviço sem domínio.
- `railway.json` roda no preDeploy: `migrate`, `collectstatic` e `create_master_user`. **Migração aplica sozinha em produção.**
- Imagem `python:3.12-slim`, Python 3.12.13, uma réplica, região us-west2, restart policy on failure.

## Antes de mexer

1. Trabalhe numa branch, nunca direto na `main`.
2. Rode local com `dev_local.py`, nunca `manage.py` (veja a skill do ambiente local).
3. Se a alteração criar migração, confira que ela só **adiciona** coisas. Migração que altera ou apaga coluna precisa de conversa antes: roda sozinha, sem revisão, contra o banco de produção.
4. Stageie ficheiro por ficheiro. **Nunca `git add -A` nem `git commit -a`**: já varreu ficheiro que não era para entrar.

## A armadilha que já apagou trabalho

Se o merge remove um ficheiro rastreado que tem alteração local não commitada, o `git checkout` da branch de destino sobrescreve o ficheiro no disco e a alteração local **some**. Foi assim que o `.env` do Jonas perdeu 20 chaves.

Antes de qualquer merge que apague ficheiro, copie o ficheiro para fora do repositório.

## Publicar

```bash
git checkout main && git merge --no-ff <branch> -m "..."
git push origin main
```

Use `--no-ff` sempre: a reversão vira um comando só, `git revert -m 1 <merge>`.

Enquanto o Railway builda, monitore a disponibilidade. O site continua no ar durante o build, e ver isso confirmado vale mais que supor:

```bash
for i in $(seq 1 14); do curl -s -o /dev/null -w "HTTP %{http_code}\n" -L https://www.educaflowone.com.br/; sleep 10; done
```

## Verificar depois, sempre

No Railway, abra o deploy e leia o **log de arranque**. Estas linhas provam que a configuração inteira subiu:

```
[R2] ENABLED bucket=educaflow-uploads ... access_key_set=True secret_key_set=True
[OK] EMAIL: Configurado para Resend (API)
Running migrations: No migrations to apply.      (ou a migração esperada)
Usuário 'Admin' atualizado com sucesso.
[INFO] Starting gunicorn 25.3.0
```

Se a linha do e-mail cair para `console backend`, alguma variável sumiu: o e-mail transacional parou de sair e ninguém vai perceber sozinho.

Depois teste de fora:

```bash
for p in "" "login/" "signup/" "planos/"; do curl -s -o /dev/null -w "/$p -> %{http_code}\n" -L "https://www.educaflowone.com.br/$p"; done
curl -s -o /dev/null -w "webhook stripe -> %{http_code}\n" https://www.educaflowone.com.br/api/webhooks/stripe/   # 405 e o esperado
```

## Variáveis do Railway

**Alterar variável não aplica sozinha.** Ela só entra em vigor no próximo arranque do container. Troque todas as que precisar e faça **um único Redeploy** no fim, pelo menu de três pontos do deploy ativo.

Cuidado com `MASTER_PASSWORD`: o `create_master_user` roda a cada deploy e **redefine a senha** do usuário `Admin`. Se a variável não existir, ele usa um valor que está escrito no código-fonte público.

## Voltar atrás

1. **Mais rápido:** Railway, Deployments, HISTORY, escolher o deploy anterior, menu de três pontos, Redeploy. Reaproveita a imagem já construída.
2. **Definitivo:** `git revert -m 1 <commit-do-merge>` e push.
3. A tag `producao-antes-do-pin` marca o estado de 13/08/2026, antes do pin de dependências.

Build que falha **não** substitui o que está no ar. O site nem pisca.

## Coisas que não se fazem por conta própria

- Autenticar no GitHub ou em qualquer serviço em nome do Jonas. O push pode pedir login pelo Credential Manager; nesse caso a janela é dele.
- Rotacionar ou digitar segredo.
- Rodar comando no console de produção sem ele pedir.
