# QA Report — Feature: Área do Aluno — Link de Acesso

**Data:** 2026-03-18
**Ambiente:** localhost:8000 · Admin superuser
**Aluno testado:** "Aluno Teste Claude" (id=35)

---

## Resumo dos TCs

| TC | Descrição | Resultado |
|----|-----------|-----------|
| TC-SHARE-1 | Abrir modal, link carrega, copiar | ✅ PASSOU |
| TC-SHARE-2 | Regenerar link invalida o anterior | ✅ PASSOU |
| TC-SHARE-3 | WhatsApp/E-mail usam link atual | ✅ PASSOU |
| ERR-SHARE-1 | Sem autenticação redireciona | ⚠️ Não testado (requer logout) |
| ERR-SHARE-2 | Permissão de aluno inválido | ⚠️ Não testado (requer 2ª conta) |

---

## TC-SHARE-1 — Modal abre e link carrega ✅

- Botão "Área do Aluno" visível na ficha do aluno `/alunos/35/`
- Modal abre com `#shareUrl` já preenchido (não ficou em "Carregando...")
- URL no formato correto: `http://localhost:8000/aluno/tok_Xv97T3PSsRMoRIcscxq8Ob/`
- Copiar funciona (toast desaparece rápido mas clipboard foi populado — confirmado via JS)
- Página pública `/aluno/<token>/` carrega com status 200
- Exibe nome do aluno real e `teacher_name` real ("Administração")

---

## TC-SHARE-2 — Regenerar link invalida o anterior ✅

- Token antigo: `tok_Xv97T3PSsRMoRIcscxq8Ob`
- Após "Gerar novo link": `tok_NRyt2S6pAPfkxuNs94H57ea`
- Token antigo → Django 404 ✅
- Token novo → 200 ✅
- `#shareUrl` atualizado imediatamente no modal ✅

---

## TC-SHARE-3 — WhatsApp/E-mail usam link atual ✅

- Interceptado `window.open` via JS
- WhatsApp: `containsCurrentLink: true` ✅
- E-mail: `containsCurrentLink: true` ✅

---

## 🐛 BUG GRAVE — `area_aluno.html` exibe dados hardcoded/mock para todos os alunos

**Severidade:** Alta
**URL:** `/aluno/<token>/` (qualquer token de qualquer aluno)

### Descrição
A view `StudentAreaView` (`core/views.py` linha ~700) passa para o template **apenas**:
- `student` (objeto Student)
- `teacher_name` (string)

Porém o template `area_aluno.html` renderiza dados estáticos hardcoded que não pertencem ao aluno:

| Campo exibido | Valor hardcoded | Valor real (Aluno Teste Claude) |
|---|---|---|
| Aulas realizadas | **24** | 0 |
| HW Concluído | **78% (7 de 9)** | 0% |
| Última aula | **10/03 · Present Perfect** | — |
| Próxima aula | **Terça, 17 mar · 14h-15h** | 18/03 · 20h00 |
| Progresso HW | **78%** | 0% |
| Materiais | PDFs fictícios (Present Perfect, Business Vocab) | Nenhum |
| Homework | 4 tarefas fictícias | 0 |
| Calendário | Dias hardcoded `[3, 10, 17, 24, 31]` | — |

### Causa raiz
O template `area_aluno.html` foi criado como **design mockup** (ver comentário no `<head>`: `Design Mockup · Acesso via link único`) e nunca foi integrado com dados reais do backend. A view foi implementada e o sistema de token funciona, mas o template ainda usa dados de demonstração.

### Impacto
- Todos os alunos que receberem o link verão **as mesmas informações fictícias** (aulas de inglês para negócios de um aluno de exemplo) em vez de seus próprios dados reais.
- Isso torna a feature de "Área do Aluno" **inutilizável em produção**.

### O que precisa ser feito (para o Cursor)
A view precisa enriquecer o contexto com dados reais do aluno:
```python
# Em get_context_data():
lessons = Lesson.objects.filter(student=student)
homeworks = StudentHomework.objects.filter(student=student)
materials = ...  # materiais do aluno
context["lessons_done"] = lessons.filter(status='done').count()
context["next_lesson"] = lessons.filter(date__gte=today).order_by('date').first()
context["hw_stats"] = { ... }
# etc.
```
E o template deve usar `{{ lessons_done }}`, `{{ next_lesson.date }}`, etc. em vez dos valores fixos.

---

## Observação — Toast de "Copiar" muito rápido

O toast "Link copiado!" aparece mas desaparece muito rápido para ser capturado em screenshot. Funcionalmente ok (clipboard foi populado), mas considerar aumentar a duração do toast de ~1.5s para ~3s para melhor UX.

---

## Status Final

| Funcionalidade | Status |
|---|---|
| Modal abre e carrega link via API | ✅ Funcionando |
| Token único por aluno | ✅ Funcionando |
| Regeneração revoga token antigo | ✅ Funcionando |
| Link antigo retorna 404 | ✅ Funcionando |
| WhatsApp/E-mail usam link correto | ✅ Funcionando |
| Dados reais na Área do Aluno | ❌ Bug grave — dados mockados |
