# Análise da Landing v4 e definição como principal

## Resumo

A **landing v4** (`test_landing_v4.html`) foi analisada e configurada como a **landing principal** do EDUCAflowOne. Visitantes não logados em `/` e em `/landing/` passam a ver a v4.

---

## Links verificados

| Destino | Tipo | Status |
|--------|------|--------|
| `/login/` | Rota Django | ✅ Funcional |
| `/signup/?tier=basic&plan=monthly` (e variantes) | Rota Django | ✅ Funcional |
| `#top`, `#features`, `#screenshots`, `#pricing`, `#faq` | Âncoras na página | ✅ OK |
| `/api/landing/contact/` | API POST (formulário de contato) | ✅ Existe e funcional |
| Modal de contato (Fale conosco) | `.js-contact-trigger` | ✅ Abre o modal |
| Instagram / YouTube (footer) | Links externos | ✅ OK |

---

## Links placeholder (footer)

Estes itens do footer estão com `href="#"` (sem página própria no projeto):

- **Sobre**
- **Blog**
- **Contato** → abre o modal (não é placeholder)
- **Termos de uso**
- **Privacidade**

**Recomendação:** Quando houver páginas de Termos e Privacidade, criar rotas (ex.: `/termos/`, `/privacidade/`) e atualizar os links no template. Até lá, manter `#` é aceitável.

---

## Imagens (static)

A landing v4 usa `{% static 'img/...' %}`. Os arquivos são buscados em `frontend/templates/img/` (STATICFILES_DIRS):

- `img/educaflow-new.png` – logo (navbar e footer)
- `img/dash.png` – screenshot dashboard
- `img/calendario.png` – screenshot calendário
- `img/semanal.png` – screenshot visão semanal
- `img/finan.png` – screenshot financeiro

**Importante:** Confirme que esses arquivos existem em `frontend/templates/img/`. Se alguma imagem quebrar, adicione o arquivo nessa pasta (ou ajuste o nome no template para o arquivo que você tiver).

---

## Alterações feitas no código

1. **`core/views.py` – `HomeView`**  
   - Usuário **não logado** em `/`: passou a renderizar `test_landing_v4.html` em vez de `landing.html`.

2. **`core/urls.py`**  
   - Rota `landing/`: passou a usar `test_landing_v4.html` em vez de `landing.html`.

Assim, **`/`** e **`/landing/`** exibem a mesma landing v4. As antigas `landing.html` e `test_landing_v3.html` continuam disponíveis em rotas específicas se você quiser manter (`/landing-v3/` já existia; não há rota nomeada para a antiga `landing.html` a menos que você adicione).

---

## Como testar

1. Abra o site **deslogado**: `http://localhost:8000/` ou `http://localhost:8000/landing/`.
2. Confira: navbar (Recursos, Sistema, Planos, FAQ, Login, CTA), hero, seções, preços, FAQ, footer.
3. Clique em “Login” → deve ir para `/login/`.
4. Clique em “Testar 7 dias grátis” / “Começar 7 dias grátis” → deve ir para `/signup/?tier=basic&plan=monthly`.
5. Abra “Fale conosco” / Contato no footer → deve abrir o modal; envie o formulário e verifique se o email de contato é recebido (API `/api/landing/contact/`).
6. Verifique se as imagens da logo e dos screenshots carregam (depende dos arquivos em `frontend/templates/img/`).

---

## Conclusão

A landing v4 está configurada como principal. Links internos e API de contato estão corretos. Pendências opcionais: criar páginas e links para Termos, Privacidade, Sobre e Blog quando fizer sentido; garantir que as imagens em `frontend/templates/img/` existam.
