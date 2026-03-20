# QA Report — Feature: Replicar Aula no Mês (modal de replicação)

**Data:** 2026-03-18
**Ambiente:** localhost:8000 · Django · Admin superuser
**Escopo:** TC-REPL-1 a TC-REPL-8 (modal de replicação automática de aulas)
**Arquivo alterado:** `frontend/templates/calendar_new.html`

---

## Resumo Executivo

| TC | Descrição | Resultado |
|----|-----------|-----------|
| TC-REPL-1 | Modal aparece e mostra datas sugeridas | ✅ PASSOU |
| TC-REPL-2 | Modal NÃO aparece na última ocorrência do dia da semana | ✅ PASSOU |
| TC-REPL-3 | Réplicas criadas sempre como Pendente | ✅ PASSOU |
| TC-REPL-4 | Modal NÃO aparece ao editar aula existente | ✅ PASSOU |
| TC-REPL-5 | Tratamento de erro de vinculação (smoke) | ⚠️ NÃO TESTÁVEL (conta Admin) |
| TC-REPL-6 | Botões totalmente visíveis | ✅ PASSOU |
| TC-REPL-7 | Calendário atualiza automaticamente após Replicar | ✅ PASSOU |
| TC-REPL-8 | Visual premium do modal | ✅ PASSOU (redesign aplicado) |

---

## Detalhamento

### TC-REPL-1 — Modal aparece com datas sugeridas ✅

**Passos:**
1. Abrir `/calendar/`
2. "+ Nova aula" → Aluno Teste Claude, 18/03/2026 (QUA), 20:00, Status Confirmado

**Resultado:**
- Modal "Replicar Aula no Mês" abriu automaticamente após salvar
- Texto: "Para **Aluno Teste Claude**, encontramos **1** quarta-feiras restantes neste mês. Deseja replicar esta aula para essas datas como **Pendente**?"
- Card "DATAS SUGERIDAS" com chip "25/03" visível
- Nota de rodapé com aviso sobre status Pendente
- **PASSOU**

---

### TC-REPL-2 — Modal NÃO aparece na última ocorrência ✅

**Passos:**
1. "+ Nova aula" → Aluno Teste Claude, **25/03/2026** (última QUA do mês), 21:00

**Resultado:**
- Aula criada diretamente, sem modal de replicação
- Comportamento esperado: março 2026 não tem outra quarta-feira após o dia 25
- **PASSOU**

---

### TC-REPL-3 — Réplicas criadas como Pendente (força override de status) ✅

**Passos:**
1. Criar aula com Status = **Confirmado** em data com ocorrências restantes
2. Modal aparece → clicar Replicar

**Resultado:**
- Aula original (18/03): status **Confirmado** (verde)
- Réplica (25/03): status **Pendente** (laranja)
- Override de status funcionando corretamente
- **PASSOU**

---

### TC-REPL-4 — Modal NÃO aparece ao editar ✅

**Passos:**
1. Clicar "Editar" em aula existente (Aluno Teste Claude, 25/03, 21:00)
2. Modal "Editar Aula" abre com dados preenchidos e botão "Salvar Alterações"
3. Clicar "Salvar Alterações"

**Resultado:**
- Modal de replicação NÃO apareceu
- A flag `editingLessonId` (null = criar, ID = editar) funciona corretamente
- **PASSOU**

---

### TC-REPL-5 — Tratamento de erro de vinculação ⚠️

**Resultado:**
- Não testável com conta Admin (bypass total de permissões)
- Requer conta de professor com alunos não vinculados a parceiros para reproduzir o erro de `student_assignment`
- **NÃO TESTÁVEL nesta sessão**

---

### TC-REPL-6 — Botões totalmente visíveis ✅

**Resultado:**
- "Agora não" e "Replicar →" completamente visíveis na área inferior do modal
- CSS `flex: 0 0 auto` nas `.modal-actions` garante que os botões não sejam empurrados para fora
- Testado em viewport 1920×893
- **PASSOU**

---

### TC-REPL-7 — Calendário atualiza automaticamente após Replicar ✅

**Passos:**
1. Criar aula para 21/03/2026 (SAB) → Modal aparece com 28/03 sugerido
2. Clicar "Replicar →"

**Resultado:**
- Modal fechou
- Dia 21 exibe "10:00 Aluno Test..." (original)
- Dia 28 exibe "10:00 Aluno Test..." (réplica)
- Sem F5, sem troca de tela
- **PASSOU**

---

### TC-REPL-8 — Visual premium do modal ✅ (redesign aplicado)

**Problemas identificados no design original:**
- Header com gradiente muito suave (quase branco), sem distinção visual forte
- Texto da mensagem pequeno (13px), cor muted, pouco legível
- Chips básicos sem hierarquia visual
- Footnote em cinza muted, difícil de ler
- Botões sem diferenciação clara entre primário e secundário

**Redesign aplicado (`calendar_new.html`):**

| Elemento | Antes | Depois |
|----------|-------|--------|
| Header | Gradiente azul 16% opacidade | Gradiente indigo→blue sólido (`#3730a3` → `#3b82f6`) com shimmer overlay |
| Ícone | 🔁 inline no h2 | Badge frosted glass 46×46px, border branca, sombra |
| Subtítulo | — | "Agendamento automático para o mês corrente" em rgba(255,255,255,.68) |
| Botão fechar | × texto básico | Frosted glass com border, hover scale(1.10) |
| Mensagem | 13px, `var(--muted)`, font-weight 800 | 14px, `#1e293b`, names/counts em `#2563eb` bold |
| Card datas | Fundo azul 5%, borda 14% | Gradiente `#f8faff→#eff6ff`, borda 1.5px, inner shadow |
| Título seção | 12.5px maiúsculas genéricas | 10.5px uppercase + 📆 ícone + `color: #2563eb` |
| Chips | Border 1px, shadow flat | Border 1.5px, shadow `0 4px 12px rgba(37,99,235,.08)`, hover lift |
| Footnote | 11px cinza muted | Flex com ℹ️ icon, blue-left-border, `color: #2563eb` |
| "Agora não" | Botão genérico sem estilo | Ghost button transparente, border 1.5px, hover background |
| "Replicar" | Botão primary básico | Gradiente azul, shadow glow, hover `translateY(-2px)` + brightness |
| Seta → | `<span>` (removido pelo JS) | CSS `::after { content: ' →' }` — imune ao `.textContent` do JS |
| Entrada | Sem animação | `@keyframes repl-modal-enter` scale + translateY com cubic-bezier spring |

**PASSOU** — TC-REPL-8 atendido com todos os requisitos: header premium, card com borda suave, chips com sombra leve, visual distinto do modal anterior.

---

## Bugs Corrigidos Durante o QA

### Bug 1 — Footnote quebrava "como" em linha separada
**Causa:** `display: flex` no `.replicate-footnote` tratava cada nó de texto como flex item separado, quebrando a frase "...cadastradas **como** Pendente..."
**Fix:** Envolver o texto em `<span>` para criar um único flex item

### Bug 2 — Seta → desaparecia no botão "Replicar"
**Causa:** JS fazia `replicateLessonBtnYes.textContent = 'Replicar'` removendo o `<span class="repl-cta-arrow">` do DOM
**Fix:** Migrar a seta para `::after { content: ' →' }` no CSS — pseudo-elements são imunes a mudanças de `textContent`

---

## Status Final

**Todos os TCs executáveis: PASSARAM ✅**
**TC-REPL-5: requer conta de professor com parceiros para teste completo ⚠️**
**Redesign de UX aplicado e verificado em browser ✅**
