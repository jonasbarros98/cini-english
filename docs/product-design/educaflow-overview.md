## EDUCAflowOne – Visão Geral

O EDUCAflowOne é uma plataforma de gestão criada para **professores particulares** que querem tirar a rotina do improviso (WhatsApp + planilha + memória) e ter **clareza total** sobre aulas, alunos e financeiro em um só lugar.  
Ele nasceu para ser “o sistema do professor particular”, com foco em simplicidade visual, poucos cliques para cada ação importante e uma curva de aprendizado mínima.

### Posição na rotina do professor
- **Antes:** o professor espalha informações entre cadernos, Google Calendar, prints de conversa e comprovantes de Pix.
- **Com o EDUCAflowOne:** tudo passa a girar em torno de um **dashboard único**, onde ele:
  - enxerga o mês (aulas, pendências e faturamento),
  - organiza alunos e planos,
  - planeja aulas,
  - e cobra os responsáveis com poucos toques.

O sistema é pensado para ser usado **no dia a dia**, não só “uma vez por mês para faturar”.

---

## Pilares Principais

### 1. Agenda e aulas como centro da operação
- **Calendário mensal unificado**: o professor vê rapidamente quais dias têm aulas, quais estão pendentes, confirmadas ou realizadas.
- **Aula como unidade de verdade**: status de aula (confirmada, realizada, cancelada) alimenta:
  - o controle de presença,
  - o planejamento de conteúdos,
  - e a cobrança (quando o plano é por aula realizada).
- **Visão rápida no dashboard**: cards de “aulas confirmadas”, “pendentes” e “realizadas” aparecem em destaque, conectando o trabalho pedagógico ao impacto financeiro.

**Intenção de produto:** o sistema nunca perde de vista que o negócio do professor é **dar aula**. Todo o resto (financeiro, tarefas, cobrança) nasce em torno do calendário.

---

### 2. Gestão de alunos e planos realmente utilizável
- **Cadastro de alunos enxuto**, com foco em:
  - quem é o aluno / responsável,
  - forma de contato,
  - plano e forma de cobrança.
- **Planos flexíveis**, cobrindo os principais modelos de professores particulares:
  - mensal fixo,
  - pacote de aulas,
  - por aula realizada,
  - outros arranjos personalizados.
- **Relação forte aluno ←→ plano ←→ financeiro**:
  - o status do plano orienta geração de cobranças,
  - o histórico financeiro preserva o que já foi feito, mesmo que o aluno mude de plano.

**Intenção de produto:** permitir que o professor ajuste o sistema ao seu jeito de trabalhar, sem precisar se enquadrar em um único modelo rígido.

---

### 3. Financeiro claro, focado em “a receber”
- **Tela Financeiro dedicada (`/financeiro/`)**:
  - visão por mês, com agrupamento por dia de vencimento,
  - destaques para **a receber**, **recebido**, **vencido** e **total de lançamentos**,
  - filtros rápidos (Mês, Hoje, 7 dias, Vencidos).
- **Lançamentos financeiros estruturados** (`FinancialEntry`):
  - valor, vencimento, status (pendente, pago, vencido, cancelado),
  - parcelamento (quantas parcelas e qual parcela atual),
  - forma de pagamento (Pix, dinheiro, cartão, transferência, etc.).
- **Geração automática de cobranças do mês**:
  - para quem trabalha “por aula realizada”, o sistema gera os lançamentos com base nas aulas do período.

**Intenção de produto:** transformar o “caos do Pix” em uma lista clara do que falta entrar, o que já entrou e o que está virando problema (vencido).

---

### 4. Cobrança integrada (WhatsApp + Pix)
- **Tela de cobrança** que parte sempre de um lançamento financeiro:
  - escolhe o lançamento,
  - gera automaticamente mensagem contextualizada (valor, aluno, vencimento, atraso),
  - registra logs de cobrança (`BillingLog`), guardando:
    - quando foi enviado,
    - por qual canal (WhatsApp, email, etc.),
    - e qual tipo de mensagem (lembrete amigável, vence hoje, em atraso, agradecimento).
- **Integração leve com WhatsApp**:
  - o foco não é ser uma “API de WhatsApp”, e sim **preparar o texto certo** para o professor copiar/encaminhar,
  - reduz o tempo de escrever manualmente cada cobrança e diminui erros de valor/data.

**Intenção de produto:** deixar a cobrança menos desgastante, mais padronizada e com tom profissional, sem exigir do professor conhecimento técnico ou automações complexas.

---

### 5. Assinatura do professor e modelo de negócio
- **Trial gratuito de 7 dias sem cartão**:
  - o professor testa o sistema em produção (com alunos reais) antes de assumir qualquer compromisso,
  - banner e email avisam no 5º dia que o trial está acabando,
  - no 7º dia o acesso passa a exigir escolha de plano em `/planos/`.
- **Planos pagos via Stripe**:
  - planos mensal, semestral e anual,
  - webhooks atualizam automaticamente o status da assinatura no sistema,
  - o professor vê e gerencia seu próprio plano na tela de planos.
- **Emails transacionais e de retenção**:
  - onboarding 24h após ativar a assinatura,
  - recuperação de checkout pendente,
  - avisos de problemas de pagamento, cancelamento, etc.

**Intenção de produto:** ter um modelo de assinatura saudável para o negócio, sem atritos desnecessários para o professor (especialmente na fase de teste).

---

### 6. Experiência de uso pensada para não cansar
- **Interface limpa, cores suaves, foco no essencial**:
  - poucos elementos por tela,
  - textos explicativos curtos e diretos,
  - ícones e etiquetas de status para leitura rápida (Pago, Pendente, Vencido).
- **Mesma linguagem em todo o produto**:
  - rótulos em português, voltados ao vocabulário do professor (“Lançamentos a Receber”, “Cobrança”, “Planejamento”),
  - detalhes de microcópia para reduzir dúvidas (“Use ‘Vence em 7 dias’ pra atacar o que vai virar problema”).
- **Pensado para desktop e celular**:
  - navegação lateral + mobile nav com hambúrguer,
  - componentes responsivos, respeitando a hierarquia visual do dashboard.

**Intenção de produto:** o professor precisa conseguir usar o sistema no meio da correria do dia, sem tutorial longo; a própria interface “ensina” o que fazer.

---

### 7. Confiabilidade silenciosa (emails, cron, falhas)
- **Envio de emails resiliente**:
  - comandos de cron isolados do app principal (Railway),
  - `fail_silently=True` e `try/except` em volta de todos os envios,
  - falhas de email nunca derrubam fluxos críticos (cadastro, login, uso diário).
- **Jobs automáticos bem definidos**:
  - onboarding 24h,
  - recuperação de assinatura pendente,
  - aviso de trial terminando em 2 dias.
- **Documentação operacional** (Railway, Resend, SMTP) para facilitar manutenção.

**Intenção de produto:** o professor não precisa saber que existem crons ou webhooks; para ele “simplesmente funciona” — e, quando falha, falha de forma segura.

---

## Em resumo

Na prática, o EDUCAflowOne se posiciona como:

- **Uma central de comando para professores particulares**, não apenas “um financeiro”.
- **Um sistema que conecta aulas, alunos, planejamento e dinheiro** de forma coerente.
- **Uma ferramenta opinativa, mas flexível**, que orienta boas práticas sem engessar.

O objetivo final é que o professor:

- tenha **clareza** do que vai acontecer na semana,
- saiba **quem deve o quê e quando**,
- e consiga **cobrar e organizar tudo em poucos minutos**, liberando tempo e energia para o que realmente importa: dar boas aulas.

