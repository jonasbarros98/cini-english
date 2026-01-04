"# aula0305" 
# Cini English – Dashboard inicial

Protótipo estático (HTML/CSS/JS puro) para o painel da professora de inglês. Ele oferece o esqueleto de navegação, calendário, cadastro de alunos, pré-visualização de cobranças e cards de tarefas – pronto para receber um back-end futuro.

## Como executar

Nenhuma dependência é necessária. Opcionalmente, use um servidor local para evitar bloqueios de segurança do navegador (recomendado):

```bash
# modo simples: abre diretamente o arquivo
xdg-open index.html
# ou copie o caminho absoluto do arquivo e abra no Chrome/Firefox

# modo recomendado: servidor local (evita bloqueios do clipboard e do crypto.randomUUID)
./start.sh
# depois acesse http://localhost:8000
```

## O que já está pronto

- Navegação lateral com atalhos para Calendário, Alunos, Cobrança e Tarefas.
- Calendário mensal com seleção de dia e alteração de status das anotações.
- Formulário para registrar novas anotações por dia.
- Cards de alunos com progresso de aulas.
- Gerador de mensagem de cobrança pronta para WhatsApp (com botão “copiar”).
- Cards de tarefas com atualização rápida de status.

> Dica: se o navegador bloquear recursos locais (clipboard ou geração de IDs), use o servidor local (`./start.sh`) para garantir o funcionamento completo.

## Próximos passos sugeridos

- Integrar autenticação e persistência de dados (ex.: Supabase, Firebase ou API própria).
- Conectar o calendário a um banco de dados real e sincronizar com Google Calendar.
- Disparar mensagens via WhatsApp API/Meta ou Twilio.
- Criar componentes reusáveis com React + TypeScript ou um design system leve.