# Incidente: 500 em massa, CSS quebrado e uploads fora do R2 (mar/2026)

**Audiência:** agente `educaflow-codebase-expert` e quem faz deploy.  
**Stack:** Django 6, Railway, Gunicorn, WhiteNoise, Cloudflare R2 (`django-storages` + S3 API).

---

## Sintomas observados

1. **HTTP 500** em muitas rotas de uma vez.
2. **Páginas sem CSS** (HTML cru, logo partido): estáticos não servidos ou URLs incorretas.
3. **Bucket R2 vazio** (ou uploads só em disco local efémero): ficheiros não persistiam no object storage.
4. Logs exportados do hosting por vezes **só mostravam boot** (migrations, Gunicorn), **sem traceback** — diagnóstico via ficheiro de log isolado era insuficiente.

---

## Causas raiz (resumo técnico)

### A. Django 6 e `STORAGES` vs `DEFAULT_FILE_STORAGE` / `STATICFILES_STORAGE`

- A partir do Django 5+, **`DEFAULT_FILE_STORAGE` deixou de aplicar** o backend de ficheiros para `FileField` — o que vale é **`STORAGES["default"]`**.
- **`STATICFILES_STORAGE` sozinho não substitui** `STORAGES["staticfiles"]` em Django 4.2+: o motor de static usa **`settings.STORAGES["staticfiles"]`**.

Se o projeto só definia `STORAGES` quando `USE_R2_STORAGE=true`, **em ambientes sem essa flag** (ex.: **build Docker** antes do runtime no Railway) o Django usava o **default global** (`StaticFilesStorage` para staticfiles). O código até definia `STATICFILES_STORAGE = whitenoise...`, mas isso **era ignorado** para `collectstatic` e para `{% static %}`.

### B. Build Docker vs runtime (manifest WhiteNoise)

- **`collectstatic` no Dockerfile** corria com **`USE_R2_STORAGE` tipicamente desligado** → staticfiles com backend “simples”.
- **No Railway**, com R2 ligado, o bloco de settings podia ativar **`CompressedManifestStaticFilesStorage`** para `staticfiles`.
- **Mismatch:** ficheiros na imagem gerados **sem** o mesmo pipeline de manifest/hashing que o runtime esperava → **CSS/imagens em 404** ou comportamento inconsistente (UI “bizarra”).

### C. `collectstatic` mascarado no Dockerfile

- `2>/dev/null || true` após `collectstatic` **escondia falhas** e permitia imagens **sem estáticos válidos**.

### D. WhiteNoise + manifest estrito (contribuiu aos 500)

- Com **`CompressedManifestStaticFilesStorage`** e **`manifest_strict=True`** (padrão), qualquer `{% static '...' %}` **sem entrada** em `staticfiles.json` podia levantar **`Missing staticfiles manifest entry`** → **500 em cascata** em todas as templates que usam static.

**Mitigação aplicada:** `WHITENOISE_MANIFEST_STRICT` controlado por env; por defeito **não strict** em produção (evita derrubar o site inteiro por um ficheiro em falta no manifest). Opcional: `WHITENOISE_MANIFEST_STRICT=1` só em CI/staging para detetar problemas.

### E. R2 “finalmente” a encher o bucket

- Com **`STORAGES["default"] = S3Boto3Storage`** quando `USE_R2_STORAGE=true`, credenciais e endpoint corretos, e **sem** depender de APIs obsoletas só para mídia, os uploads passam a ir para o bucket no caminho esperado (ex. `teacher_materials/YYYY/MM/...`).
- **Bucket com “Public access: Disabled”** é normal: com **`AWS_QUERYSTRING_AUTH = True`**, downloads usam **URLs assinadas**; não é obrigatório bucket público.

---

## Soluções implementadas (código)

1. **`STORAGES` sempre definido** em `config/settings.py`:
   - `"default"`: `FileSystemStorage` por defeito; **substituído por S3/R2** só quando `USE_R2_STORAGE` está ativo.
   - `"staticfiles"`: **sempre** o mesmo `STATICFILES_STORAGE` escolhido (WhiteNoise ou simples via `DJANGO_STATICFILES_SIMPLE`).
2. **Dockerfile:** `python manage.py collectstatic --noinput` **sem** mascarar erro — falha o build se estáticos não gerarem.
3. **`WHITENOISE_MANIFEST_STRICT`:** configurável por env; omissão evita strict por defeito (ver acima).

Ficheiros tocados (época do incidente): `config/settings.py`, `Dockerfile`; comando `create_master_user` ajustado para **não imprimir senhas** nos logs.

---

## Respostas operacionais rápidas

| Pergunta | Resposta |
|----------|----------|
| **Agora vai funcionar?** | Sim, **desde que** o deploy em produção inclua as alterações acima, variáveis R2 corretas no Railway, e uma imagem em que **`collectstatic` tenha corrido com sucesso**. |
| **Preciso redeploy só para testar?** | **Não**, se **já** está em produção com CSS ok e objeto visível no bucket — isso **é** o teste. Novo redeploy só para mudança de código/env ou rebuild limpo. |
| **Como validar R2?** | Objeto aparece no prefixo esperado + na app, download/abrir ficheiro funciona (URL assinada ou fluxo da view). |

---

## Aprendizados: não experimentar em PRD

**Problema:** utilizadores reais sofrem com 500, UI partida e uploads perdidos.

**Práticas recomendadas:**

1. **Ambiente de staging** (Railway second service ou branch preview) com **mesmas** flags (`USE_R2_STORAGE`, `STORAGES`, Dockerfile) e bucket R2 de **teste**.
2. **Checklist pré-deploy** (ver também `docs/deploy-ops/pre-deploy-checklist.md`): `collectstatic` local ou em CI, smoke test de uma página com `{% static %}`, um upload de teste para R2 **antes** de promover a produção.
3. **Logs com traceback** para erros 500 (nível ERROR no Gunicorn/Django) ao diagnosticar produção — logs só de boot não chegam.
4. **Não mascarar** erros de build (`|| true` em passos críticos).
5. **Mudanças de storage/static** são alterações **de alto risco**: tratá-las como release dedicada, não misturadas com várias features.

---

## Documentação relacionada

- `docs/educaflow-codebase-expert/r2-storage-debug.md` — notas mais antigas sobre variáveis R2 e sintomas de bucket vazio (parte do conteúdo refere settings legados; cruzar com **este** documento para Django 6 + `STORAGES`).
- `docs/deploy-ops/railway-deploy-guide.md` / `pre-deploy-checklist.md` — operações gerais.

---

*Última atualização: 2026-03-25*
