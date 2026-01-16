// ==========================
// Configuração e estado
// ==========================

const API_BASE_URL = "/api";

const state = {
  today: new Date(),
  currentMonth: new Date(),
  financeViewMonth: new Date(), // Mês atual da visualização financeira (pode ser diferente do calendário)
  selectedDate: null,
  notes: {},     // { 'YYYY-MM-DD': [ { id, status, title, info, studentId, studentName } ] }
  students: [],  // vindo da API
  tasks: [],     // vindo da API
  finances: [],   // <--- NOVO: lista de cobranças do mês
  financialEntries: [], // lançamentos financeiros a receber
  currentUser: null, // usuário atual autenticado
  users: [], // lista de usuários (apenas para admins)
  lessonPlans: [], // planejamentos de aulas
};

let editingLessonId = null;
let editingTaskId = null;
let editingFinancialEntryId = null;
let editingUserId = null;
let editingPlanId = null;


// Labels separados pra não misturar aula x tarefa
const lessonStatusLabels = {
  confirmed: "Confirmado",
  pending: "Pendente",
  canceled: "Cancelado",
};
const RECEIVABLE_STATUSES = ["pending", "overdue", "reminder"];

const lessonStatusEmoji = {
  confirmed: "✔",
  pending: "•",
  canceled: "✖",
};

const taskStatusLabels = {
  todo: "A fazer",
  doing: "Fazendo",
  done: "Concluída",
};

const financeStatusLabels = {
  pending: "Pendente",
  paid: "Pago",
  overdue: "Vencido",
  remind: "Lembrar de cobrar",
};

const financialEntryStatusLabels = {
  pending: "Pendente",
  paid: "Pago",
  overdue: "Vencido",
  cancelled: "Cancelado",
};

const paymentMethodLabels = {
  pix: "PIX",
  cash: "Dinheiro",
  card: "Cartão",
  transfer: "Transferência",
  other: "Outro",
};

function formatBRL(value) {
  const num = Number(value || 0);
  return num.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

// controle da tela de aluno
let editingStudentId = null;


// ==========================
// Funções utilitárias
// ==========================

function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(";").shift();
  return null;
}

const CSRF_TOKEN = getCookie("csrftoken");

async function fetchJSON(path, options = {}) {
  const method = (options.method || "GET").toUpperCase();

  // monta headers mesclando os que já vierem em options
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  // só manda CSRF em métodos que escrevem
  if (!["GET", "HEAD", "OPTIONS", "TRACE"].includes(method)) {
    const csrf = CSRF_TOKEN || getCookie("csrftoken");
    if (csrf) {
      headers["X-CSRFToken"] = csrf;
    }
  }

  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    method,
    headers,
    credentials: "same-origin", // envia cookies (inclui csrftoken e sessão)
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    console.error("API error", res.status, res.statusText, text);
    throw new Error(`Erro na API (${res.status})`);
  }

  if (res.status === 204) return null;
  return res.json();
}

// resto continua igual:
function toISO(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}


function monthName(date) {
  return date.toLocaleDateString("pt-BR", { month: "long", year: "numeric" });
}

function ensureDayArray(dateKey) {
  if (!state.notes[dateKey]) state.notes[dateKey] = [];
  return state.notes[dateKey];
}



// ==========================
// Carregamento de dados da API
// ==========================

async function loadStudents() {
  const students = await fetchJSON("/students/");
  state.students = students.map((s) => ({
    contractPdfUrl: s.contract_pdf_url || null,
    id: s.id,
    name: s.name,
    guardians: s.guardians,
    phone: s.phone,
    address: s.address,
    plan: s.plan_name,
    progress: {
      done: s.lessons_done,
      total: s.lessons_total,
    },
    pix: s.pix_key || "",
    active: s.active,
  }));
}

async function loadTasks() {
  try {
    const tasks = await fetchJSON("/tasks/");
    state.tasks = tasks.map((t) => ({
      id: t.id,
      title: t.title,
      status: t.status,               // 'todo', 'doing', 'done'
      date: t.date || null,           // "2026-01-05"
      dueDate: t.due_date || null,    // "2026-01-10"
      tags: t.tags || "",
      notes: t.notes || "",
      createdAt: t.created_at,
      updatedAt: t.updated_at,
    }));
  } catch (error) {
    console.error("Erro ao carregar tarefas:", error);
    state.tasks = [];
  }
}



function openTaskForm(task = null) {
  const card = document.getElementById("taskFormCard");
  const form = document.getElementById("taskForm");

  const title = document.getElementById("taskTitle");
  const date = document.getElementById("taskDate");
  const due = document.getElementById("taskDue");
  const status = document.getElementById("taskStatus");
  const notes = document.getElementById("taskNotes");

  if (task) {
    // edição
    form.dataset.id = task.id;
    title.value = task.title || "";
    date.value = task.date || "";
    due.value = task.due_date || "";
    status.value = task.status || "todo";
    notes.value = task.notes || "";
  } else {
    // nova tarefa
    delete form.dataset.id;
    title.value = "";
    // padrão: hoje
    const today = new Date().toISOString().slice(0, 10);
    date.value = today;
    due.value = "";
    status.value = "todo";
    notes.value = "";
  }

  card.hidden = false;
  title.focus();
}

function closeTaskForm() {
  const card = document.getElementById("taskFormCard");
  card.hidden = true;
}

async function onTaskFormSubmit(event) {
  event.preventDefault();
  const form = event.target;

  const payload = {
    title: document.getElementById("taskTitle").value.trim(),
    date: document.getElementById("taskDate").value || null,
    due_date: document.getElementById("taskDue").value || null,
    status: document.getElementById("taskStatus").value,
    notes: document.getElementById("taskNotes").value.trim(),
  };

  if (!payload.title) {
    alert("Dá um título pra tarefa primeiro 😉");
    return;
  }

  const id = form.dataset.id;

  try {
    if (id) {
      // editar
      await fetchJSON(`/tasks/${id}/`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
    } else {
      // criar
      await fetchJSON("/tasks/", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    }

    await loadTasks(); // garante state.tasks atualizado
    closeTaskForm();
  } catch (err) {
    console.error(err);
    alert("Não foi possível salvar a tarefa.");
  }
}


async function loadLessonsForCurrentMonth() {
  const year = state.currentMonth.getFullYear();
  const month = String(state.currentMonth.getMonth() + 1).padStart(2, "0");
  const lessons = await fetchJSON(`/lessons/?month=${year}-${month}`);

  state.notes = {};
  lessons.forEach((lesson) => {
    const key = lesson.date; // 'YYYY-MM-DD'
    if (!state.notes[key]) state.notes[key] = [];
    state.notes[key].push({
      id: lesson.id,
      status: lesson.status,
      title: lesson.title,
      info: lesson.info,
      studentId: lesson.student,
      studentName: lesson.student_name,
      time: lesson.time, // 👈 AGORA VAI
    });
  });
}

async function loadFinancesForCurrentMonth() {
  const year = state.currentMonth.getFullYear();
  const month = String(state.currentMonth.getMonth() + 1).padStart(2, "0");
  const invoices = await fetchJSON(`/invoices/?month=${year}-${month}`);

  state.finances = invoices.map((inv) => ({
    id: inv.id,
    studentId: inv.student,
    studentName: inv.student_name,
    month: inv.month,          // "2026-01-01"
    dueDate: inv.due_date,
    amount: inv.amount,
    status: inv.status,        // "pending" | "paid" | "overdue" | "remind"
    notes: inv.notes || "",
  }));
}

async function loadFinancialEntries() {
  const year = state.financeViewMonth.getFullYear();
  const month = String(state.financeViewMonth.getMonth() + 1).padStart(2, "0");
  const url = `/financial-entries/?month=${year}-${month}`;
  console.log("Carregando lançamentos financeiros:", url);
  try {
    const entries = await fetchJSON(url);
    console.log("Lançamentos recebidos:", entries);
    state.financialEntries = entries.map((e) => ({
      id: e.id,
      studentId: e.student,
      studentName: e.student_name,
      description: e.description,
      amount: e.amount,
      installments: e.installments,
      currentInstallment: e.current_installment,
      issueDate: e.issue_date,
      dueDate: e.due_date,
      paymentDate: e.payment_date,
      status: e.status,
      paymentMethod: e.payment_method,
      notes: e.notes || "",
    }));
    console.log("Lançamentos processados:", state.financialEntries.length);
  } catch (error) {
    console.error("Erro ao carregar lançamentos financeiros:", error);
    state.financialEntries = [];
  }
}

async function loadInitialData() {
  await Promise.all([
    loadStudents(),
    loadTasks(),
    loadLessonsForCurrentMonth(),
    loadFinancesForCurrentMonth(),
    loadFinancialEntries()
  ]);
}


// ==========================
// Stats (cards + sidebar)
// ==========================

function renderStats() {
  let confirmed = 0;
  let pending = 0;
  let canceled = 0;

  Object.values(state.notes).forEach((noteList) => {
    noteList.forEach((note) => {
      if (note.status === "confirmed") confirmed += 1;
      if (note.status === "pending") pending += 1;
      if (note.status === "canceled") canceled += 1;
    });
  });

  const studentsCount = state.students.filter((s) => s.active !== false).length;

  document.getElementById("statConfirmed").textContent = confirmed;
  document.getElementById("statPending").textContent = pending;
  document.getElementById("statCanceled").textContent = canceled;
  document.getElementById("statStudents").textContent = studentsCount;

  document.getElementById("sidebarConfirmed").textContent = confirmed;
  document.getElementById("sidebarPending").textContent = pending;
  document.getElementById("sidebarStudents").textContent = studentsCount;
}


// ==========================
// Calendário
// ==========================

async function changeMonth(delta) {
  const current = state.currentMonth;
  state.currentMonth = new Date(
    current.getFullYear(),
    current.getMonth() + delta,
    1
  );

  await Promise.all([
    loadLessonsForCurrentMonth(),
    loadFinancesForCurrentMonth(),
    loadFinancialEntries(),
  ]);

  renderCalendar();
  renderDayDetails();
  renderStats();
  renderFinance();
  renderFinanceTotal();
  renderFinancialEntries();
  renderFinancialStats();
}


function renderCalendar() {
  const grid = document.getElementById("calendarGrid");
  grid.innerHTML = "";

  const year = state.currentMonth.getFullYear();
  const month = state.currentMonth.getMonth();
  const label = monthName(state.currentMonth);

  // título do mês
  document.getElementById("monthTitle").textContent =
    label.charAt(0).toUpperCase() + label.slice(1);

  // ---------- CÉLULAS DO MÊS ----------

  // Usando UTC pra evitar bug de fuso
  const daysInMonth = new Date(Date.UTC(year, month + 1, 0)).getUTCDate();
  const firstWeekday = new Date(Date.UTC(year, month, 1)).getUTCDay(); // 0 = DOM

  // placeholders vazios antes do dia 1 para alinhar com o dia da semana certo
  for (let i = 0; i < firstWeekday; i++) {
    const empty = document.createElement("div");
    empty.className = "day empty";
    grid.append(empty);
  }

  // dias do mês
  for (let day = 1; day <= daysInMonth; day++) {
    // chave de data SEM usar Date/toISOString => sem “dia anterior”
    const key = `${year}-${String(month + 1).padStart(2, "0")}-${String(
      day
    ).padStart(2, "0")}`;

    const notes = state.notes[key] || [];

    const dayEl = document.createElement("button");
    dayEl.type = "button";
    dayEl.className = "day";
    if (state.selectedDate === key) dayEl.classList.add("selected");

    const header = document.createElement("div");
    header.className = "day-header";

    const dateEl = document.createElement("span");
    dateEl.className = "day-date";
    dateEl.textContent = day.toString().padStart(2, "0");

    const countEl = document.createElement("span");
    countEl.className = "pill pending";
    countEl.textContent = `${notes.length} notas`;

    header.append(dateEl, countEl);

    const list = document.createElement("div");
    list.className = "day-notes";

    notes.slice(0, 3).forEach((note) => {
      const chip = document.createElement("div");
      chip.className = "note-chip";
      chip.innerHTML = `
        <span class="pill ${note.status}">
          ${lessonStatusEmoji[note.status] || "•"}
        </span>
        <span>${note.title}</span>
      `;
      list.append(chip);
    });

    dayEl.append(header, list);
    dayEl.addEventListener("click", () => selectDay(key));
    grid.append(dayEl);
  }
}




function selectDay(key) {
  state.selectedDate = key;
  renderCalendar();
  renderDayDetails();
}

function startEditLesson(note) {
  editingLessonId = note.id;

  const form = document.getElementById("noteForm");
  const submitBtn = form.querySelector('button[type="submit"]');

  document.getElementById("noteTitle").value = note.title || "";
  document.getElementById("noteStatus").value = note.status || "confirmed";
  document.getElementById("noteInfo").value = note.info || "";

  if (note.studentId) {
    document.getElementById("noteStudent").value = String(note.studentId);
  }

  if (note.time) {
    document.getElementById("noteTime").value = note.time.slice(0, 5);
  } else {
    document.getElementById("noteTime").value = "";
  }

  if (submitBtn) submitBtn.textContent = "Atualizar anotação";

  document.getElementById("noteTitle").focus();
  form.scrollIntoView({ behavior: "smooth", block: "start" });
}


function resetLessonFormMode() {
  const form = document.getElementById("noteForm");
  const submitBtn = form.querySelector('button[type="submit"]');
  editingLessonId = null;
  form.reset();
  if (submitBtn) {
    submitBtn.textContent = "Salvar anotação";
  }
}

function renderDayDetails() {
  const titleEl = document.getElementById("selectedDateTitle");
  const notesContainer = document.getElementById("dayNotes");
  notesContainer.innerHTML = "";

  if (!state.selectedDate) {
    titleEl.textContent = "Selecione um dia";
    return;
  }

  const date = parseISODateLocal(state.selectedDate);  // <-- aqui
  titleEl.textContent = date.toLocaleDateString("pt-BR", {
    weekday: "long",
    day: "2-digit",
    month: "long",
  });

  const notes = state.notes[state.selectedDate] || [];
  if (notes.length === 0) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent = "Nenhuma anotação para este dia. Adicione a primeira!";
    notesContainer.append(empty);
    return;
  }

  notes.forEach((note) => {
    const row = document.createElement("div");
    row.className = "note-row";

    const header = document.createElement("header");
    const title = document.createElement("strong");
    title.textContent = note.title;

    const badge = document.createElement("span");
    badge.className = `pill status ${note.status}`;
    badge.textContent = lessonStatusLabels[note.status] || "Status";

    header.append(title, badge);

    const info = document.createElement("p");
    info.className = "muted";
    info.textContent = note.info || "Sem observações.";

    const actions = document.createElement("div");
    actions.className = "note-actions";

    // STATUS BUTTONS
    ["confirmed", "pending", "canceled"].forEach((status) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "tag";
      button.textContent = `Marcar ${lessonStatusLabels[status]}`;
      button.addEventListener("click", () => {
        updateLessonStatus(note, status);
      });
      actions.append(button);
    });

    // EDIT BUTTON
    const editBtn = document.createElement("button");
    editBtn.type = "button";
    editBtn.className = "tag";
    editBtn.textContent = "Editar";
    editBtn.addEventListener("click", () => startEditLesson(note));
    actions.append(editBtn);

    // DELETE BUTTON
    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.className = "tag danger";
    deleteBtn.textContent = "Excluir aula";
    deleteBtn.addEventListener("click", () => {
      if (confirm("Tem certeza que deseja excluir esta aula?")) {
        deleteLesson(note, state.selectedDate);
      }
    });
    actions.append(deleteBtn);

    row.append(header, info, actions);
    notesContainer.append(row);
  });
}

async function deleteLesson(note, dateKey) {
  try {
    await fetchJSON(`/lessons/${note.id}/`, {
      method: "DELETE",
    });

    const list = state.notes[dateKey] || [];
    const idx = list.findIndex((n) => n.id === note.id);
    if (idx !== -1) {
      list.splice(idx, 1);
      if (list.length === 0) {
        delete state.notes[dateKey];
      }
    }

    renderStats();
    renderCalendar();
    renderDayDetails();
  } catch (error) {
    console.error(error);
    alert("Não foi possível excluir a aula.");
  }
}


async function updateLessonStatus(note, newStatus) {
  try {
    await fetchJSON(`/lessons/${note.id}/`, {
      method: "PATCH",
      body: JSON.stringify({ status: newStatus }),
    });
    note.status = newStatus;
    renderStats();
    renderCalendar();
    renderDayDetails();
  } catch (error) {
    console.error(error);
    alert("Não foi possível atualizar o status da aula.");
  }
}


// ==========================
// Alunos (lista + tela de cadastro/edição)
// ==========================

function renderStudents() {
  const list = document.getElementById("studentList");
  const select = document.getElementById("billingStudent");

  // Guardas de segurança
  if (!list) return;
  if (!select) {
    list.innerHTML = "";
    return;
  }

  list.innerHTML = "";
  select.innerHTML = "";

  state.students.forEach((student) => {
    if (student.active === false) return;

    const card = document.createElement("div");
    card.className = "student-card";

    const heading = document.createElement("div");
    heading.className = "note-row-header";

    const name = document.createElement("strong");
    name.textContent = student.name;

    const plan = document.createElement("span");
    plan.className = "pill";
    plan.textContent = student.plan || "Plano não informado";

    heading.append(name, plan);

    const meta = document.createElement("div");
    meta.className = "student-meta";
    meta.innerHTML = `
      👪 ${student.guardians || "Responsável próprio"}<br/>
      📞 ${student.phone || "Sem telefone"}<br/>
      📍 ${student.address || "Endereço não informado"}
    `;

    const progress = document.createElement("div");
    progress.className = "progress";

    const bar = document.createElement("span");
    const prog = student.progress || { done: 0, total: 0 };  // <- safe fallback
    const total = prog.total || 0;
    const done = prog.done || 0;
    const pct = total > 0 ? Math.min(100, Math.round((done / total) * 100)) : 0;
    bar.style.width = `${pct}%`;

    progress.append(bar);

    const info = document.createElement("p");
    info.className = "muted";
    info.textContent = `${done} aulas de ${total || "?"}`;

    const actions = document.createElement("div");
    actions.className = "student-actions";

    const editBtn = document.createElement("button");
    editBtn.type = "button";
    editBtn.className = "primary ghost";
    editBtn.textContent = "Editar cadastro";
    editBtn.addEventListener("click", () => openStudentForm(student.id));

    const deactivateBtn = document.createElement("button");
    deactivateBtn.type = "button";
    deactivateBtn.className = "primary ghost danger";
    deactivateBtn.textContent = "Inativar aluno";
    deactivateBtn.addEventListener("click", () => inactivateStudent(student.id));

    actions.append(editBtn, deactivateBtn);

    card.append(heading, meta, progress, info, actions);
    list.append(card);

    const option = document.createElement("option");
    option.value = student.id;
    option.textContent = student.name;
    select.append(option);
  });

  populateBilling();
  populateNoteStudentSelect();
  renderStats();
}


// select de aluno do formulário de aula
function populateNoteStudentSelect() {
  const select = document.getElementById("noteStudent");
  if (!select) return;

  const previous = select.value;
  select.innerHTML = "";

  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "Selecione um aluno";
  placeholder.disabled = true;
  placeholder.selected = true;
  select.append(placeholder);

  state.students.forEach((student) => {
    if (student.active === false) return;
    const opt = document.createElement("option");
    opt.value = student.id;
    opt.textContent = student.name;
    select.append(opt);
  });

  if (previous) {
    select.value = previous;
  }
}

function openBillingWhatsApp() {
  const select = document.getElementById("billingStudent");
  const studentId = select.value;
  const student = state.students.find((s) => String(s.id) === String(studentId));

  if (!student) {
    alert("Selecione um aluno para enviar a cobrança.");
    return;
  }

  if (!student.phone) {
    alert(`O aluno ${student.name} não tem telefone cadastrado.`);
    return;
  }

  const message = document.getElementById("billingPreview").textContent.trim();
  if (!message) {
    alert("Preencha os dados de cobrança antes de enviar.");
    return;
  }

  // limpa telefone: só dígitos
  let phoneDigits = student.phone.replace(/\D/g, ""); // "(11) 99999-0000" -> "11999990000"

  // se não tiver DDI, supõe Brasil (55)
  if (phoneDigits.length <= 11) {
    phoneDigits = "55" + phoneDigits;
  }

  const url = `https://wa.me/${phoneDigits}?text=${encodeURIComponent(message)}`;
  window.open(url, "_blank");
}


// cria uma card-form no meio da tela de alunos (se ainda não existir)
function ensureStudentFormCard() {
  let card = document.getElementById("studentFormCard");
  if (card) return card;

  const view = document.getElementById("view-students");
  const studentsSection = view.querySelector(".detail-card");

  card = document.createElement("section");
  card.id = "studentFormCard";
  card.className = "card detail-card";
  card.style.display = "none";

  card.innerHTML = `
    <div class="section-header">
      <div>
        <p class="eyebrow">Cadastro de aluno</p>
        <h3 id="studentFormTitle">Novo aluno</h3>
        <p class="muted">Preencha os dados básicos para controlar plano e aulas.</p>
      </div>
    </div>
    <form id="studentForm" class="form">
      <div class="form-row">
        <label for="studentName">Nome completo</label>
        <input id="studentName" name="studentName" type="text" required />
      </div>
      <div class="form-row">
        <label for="studentGuardians">Responsáveis (pai/mãe) ou "Responsável próprio"</label>
        <input id="studentGuardians" name="studentGuardians" type="text" />
      </div>
      <div class="form-row">
        <label for="studentPhone">Telefone</label>
        <input id="studentPhone" name="studentPhone" type="text" />
      </div>
      <div class="form-row">
        <label for="studentAddress">Endereço / cidade</label>
        <input id="studentAddress" name="studentAddress" type="text" />
      </div>
      <div class="form-row">
        <label for="studentPlan">Plano atual (ex.: Intensivo - 8 aulas)</label>
        <input id="studentPlan" name="studentPlan" type="text" />
      </div>
      <div class="form-row grid-two">
        <div>
          <label for="studentLessonsTotal">Aulas do plano</label>
          <input id="studentLessonsTotal" name="studentLessonsTotal" type="number" min="0" />
        </div>
        <div>
          <label for="studentLessonsDone">Aulas realizadas</label>
          <input id="studentLessonsDone" name="studentLessonsDone" type="number" min="0" />
        </div>
      </div>
      <div class="form-row">
        <label for="studentPix">Chave Pix (opcional)</label>
        <input id="studentPix" name="studentPix" type="text" />
      </div>
      <div class="form-row">
        <label for="studentContractPdf">Contrato PDF (opcional)</label>
        <input id="studentContractPdf" name="studentContractPdf" type="file" accept=".pdf" />
        <small class="muted">Apenas arquivos PDF são aceitos</small>
        <div id="studentContractPreview" style="margin-top: 12px; display: none;">
          <div style="display: flex; align-items: center; gap: 8px; padding: 8px; background: #f9fbff; border-radius: 8px; border: 1px solid var(--border);">
            <span>📄</span>
            <a id="studentContractLink" href="#" target="_blank" style="color: var(--accent); text-decoration: none; flex: 1;">Ver contrato atual</a>
            <button type="button" id="removeContractBtn" class="tag" style="background: #fee; color: #c33; padding: 4px 8px; font-size: 12px;">Remover</button>
          </div>
        </div>
      </div>
      <div class="form-row" style="display:flex; gap:8px; flex-wrap:wrap;">
        <button type="submit" class="primary">Salvar aluno</button>
        <button type="button" class="primary ghost" id="cancelStudentForm">Cancelar</button>
      </div>
    </form>
 `;

  const form = card.querySelector("#studentForm");
  const cancelBtn = card.querySelector("#cancelStudentForm");
  const removeContractBtn = card.querySelector("#removeContractBtn");
  const contractInput = card.querySelector("#studentContractPdf");

  form.addEventListener("submit", onStudentFormSubmit);
  cancelBtn.addEventListener("click", () => hideStudentForm());

  // Event listener para remover contrato
  if (removeContractBtn) {
    removeContractBtn.addEventListener("click", () => {
      const preview = document.getElementById("studentContractPreview");
      const link = document.getElementById("studentContractLink");
      if (preview) preview.style.display = "none";
      if (link) {
        link.href = "#";
        link.textContent = "";
      }
      if (contractInput) contractInput.value = "";
      removeContractBtn.dataset.shouldRemove = "true";
    });
  }

  // Event listener para mudança de arquivo
  if (contractInput) {
    contractInput.addEventListener("change", (e) => {
      const removeBtn = document.getElementById("removeContractBtn");
      if (removeBtn) {
        removeBtn.dataset.shouldRemove = "false";
      }
      if (e.target.files && e.target.files.length > 0) {
        const preview = document.getElementById("studentContractPreview");
        const link = document.getElementById("studentContractLink");
        if (preview) {
          preview.style.display = "block";
          if (link) {
            link.href = URL.createObjectURL(e.target.files[0]);
            link.textContent = e.target.files[0].name;
            link.download = e.target.files[0].name;
          }
        }
      }
    });
  }

  view.insertBefore(card, studentsSection);
  return card;
}

function showStudentForm() {
  const card = ensureStudentFormCard();
  card.style.display = "flex";
  window.scrollTo({ top: card.offsetTop - 80, behavior: "smooth" });
}

function hideStudentForm() {
  const card = document.getElementById("studentFormCard");
  if (card) card.style.display = "none";
  editingStudentId = null;
}

function resetStudentForm(student = null) {
  const form = document.getElementById("studentForm");
  const titleEl = document.getElementById("studentFormTitle");
  const contractPreview = document.getElementById("studentContractPreview");
  const contractLink = document.getElementById("studentContractLink");
  const contractInput = document.getElementById("studentContractPdf");
  if (!form || !titleEl) return;

  if (student) {
    titleEl.textContent = "Editar aluno";
    form.studentName.value = student.name || "";
    form.studentGuardians.value = student.guardians || "";
    form.studentPhone.value = student.phone || "";
    form.studentAddress.value = student.address || "";
    form.studentPlan.value = student.plan || "";
    form.studentLessonsTotal.value = student.progress.total || 0;
    form.studentLessonsDone.value = student.progress.done || 0;
    form.studentPix.value = student.pix || "";

    // Mostra preview do contrato se existir
    if (student.contractPdfUrl) {
      contractLink.href = student.contractPdfUrl;
      contractLink.textContent = "Ver contrato atual";
      contractPreview.style.display = "block";
    } else {
      contractPreview.style.display = "none";
    }
    contractInput.value = ""; // Limpa o input de arquivo
  } else {
    titleEl.textContent = "Novo aluno";
    form.reset();
    form.studentLessonsTotal.value = "";
    form.studentLessonsDone.value = "";
    contractPreview.style.display = "none";
    contractInput.value = "";
  }
}

function openStudentForm(studentId = null) {
  editingStudentId = studentId;
  const student = studentId ? state.students.find((s) => s.id === studentId) : null;
  ensureStudentFormCard();
  resetStudentForm(student || null);
  showStudentForm();
}
async function inactivateStudent(studentId) {
  const student = state.students.find((s) => s.id === studentId);
  if (!student) return;

  const ok = confirm(`Tem certeza que deseja inativar o aluno "${student.name}"?`);
  if (!ok) return;

  try {
    await fetchJSON(`/students/${studentId}/`, {
      method: "PATCH",
      body: JSON.stringify({ active: false }),
    });

    await loadStudents();
    renderStudents();
    renderStats();
  } catch (error) {
    console.error(error);
    alert("Não foi possível inativar o aluno. Tente novamente.");
  }
}


async function onStudentFormSubmit(event) {
  event.preventDefault();
  const form = event.target;
  const contractInput = document.getElementById("studentContractPdf");
  const removeContractBtn = document.getElementById("removeContractBtn");
  const shouldRemoveContract = removeContractBtn && removeContractBtn.dataset.shouldRemove === "true";

  // Verifica se há arquivo para upload ou se deve remover
  const hasFile = contractInput && contractInput.files && contractInput.files.length > 0;
  const useFormData = hasFile || shouldRemoveContract;

  let payload;
  let options = {};

  if (useFormData) {
    // Usa FormData para upload de arquivo
    const formData = new FormData();
    formData.append("name", form.studentName.value.trim());
    formData.append("guardians", form.studentGuardians.value.trim() || "Responsável próprio");
    formData.append("phone", form.studentPhone.value.trim());
    formData.append("address", form.studentAddress.value.trim());
    formData.append("plan_name", form.studentPlan.value.trim());
    formData.append("lessons_total", Number(form.studentLessonsTotal.value || 0));
    formData.append("lessons_done", Number(form.studentLessonsDone.value || 0));
    formData.append("pix_key", form.studentPix.value.trim());
    formData.append("active", "true");

    if (hasFile) {
      formData.append("contract_pdf", contractInput.files[0]);
    } else if (shouldRemoveContract) {
      // Para remover, envia string vazia
      formData.append("contract_pdf", "");
    }

    payload = formData;
    // Para FormData, não define Content-Type (o browser define automaticamente com boundary)
    options = {
      method: editingStudentId ? "PATCH" : "POST",
      body: payload,
      headers: {
        "X-CSRFToken": getCookie("csrftoken") || "",
      },
      credentials: "same-origin",
    };
  } else {
    // Usa JSON normal (sem arquivo)
    payload = {
      name: form.studentName.value.trim(),
      guardians: form.studentGuardians.value.trim() || "Responsável próprio",
      phone: form.studentPhone.value.trim(),
      address: form.studentAddress.value.trim(),
      plan_name: form.studentPlan.value.trim(),
      lessons_total: Number(form.studentLessonsTotal.value || 0),
      lessons_done: Number(form.studentLessonsDone.value || 0),
      pix_key: form.studentPix.value.trim(),
      active: true,
    };

    options = {
      method: editingStudentId ? "PATCH" : "POST",
      body: JSON.stringify(payload),
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken") || "",
      },
      credentials: "same-origin",
    };
  }

  // Validação do nome
  if (!form.studentName.value.trim()) {
    alert("Informe o nome do aluno.");
    return;
  }

  // 1) API: PATCH / POST
  try {
    const url = editingStudentId ? `/students/${editingStudentId}/` : "/students/";
    const response = await fetch(`${API_BASE_URL}${url}`, options);

    if (!response.ok) {
      const errorText = await response.text().catch(() => "");
      throw new Error(errorText || `Erro ${response.status}`);
    }

    const data = await response.json();
    console.log("Aluno salvo:", data);
  } catch (error) {
    console.error(error);
    alert(error.message || "Não foi possível salvar o aluno na API.");
    return;
  }

  // 2) Atualizar tela
  try {
    await loadStudents();
    renderStudents();
    hideStudentForm();
  } catch (error) {
    console.error(error);
    alert("Aluno salvo, mas houve erro ao atualizar a tela. Recarregue a página.");
  }
}

// ==========================
// Cobrança
// ==========================



function populateBilling() {
  const select = document.getElementById("billingStudent");
  if (!select) return; // ainda não montou a tela de cobrança

  const studentId = select.value;
  const student = state.students.find(
    (s) => String(s.id) === String(studentId)
  );
  if (!student) return;

  const planInput = document.getElementById("billingPlan");
  const installmentsInput = document.getElementById("billingInstallments");
  const deliveredInput = document.getElementById("billingDelivered");
  const totalInput = document.getElementById("billingTotal");
  const pixInput = document.getElementById("billingPix");
  const valueInput = document.getElementById("BillingValue"); // só se existir

  if (planInput) {
    planInput.value = student.plan || "";
  }
  if (installmentsInput) {
    installmentsInput.value = "Mensal - Vencimento dia 05";
  }
  if (deliveredInput) {
    deliveredInput.value = student.progress.done || 0;
  }
  if (totalInput) {
    totalInput.value = student.progress.total || 0;
  }
  if (pixInput) {
    // se tiver pix do aluno usa, senão cai na chave padrão
    pixInput.value = student.pix || "61.185.079/0001-67";
  }
  if (valueInput) {
    valueInput.value = "R$: 0,00";
  }

  renderBillingPreview();
}


function renderBillingPreview() {
  const select = document.getElementById("billingStudent");
  const studentId = select.value;
  const student = state.students.find((s) => String(s.id) === String(studentId));
  if (!student) {
    document.getElementById("billingPreview").textContent = "";
    return;
  }

  const plan = document.getElementById("billingPlan").value;
  const installments = document.getElementById("billingInstallments").value;
  const delivered = document.getElementById("billingDelivered").value || 0;
  const total = document.getElementById("billingTotal").value || 0;
  const pix = document.getElementById("billingPix").value;
  const total_value = document.getElementById("billingValue").value;

  const preview = `Olá ${student.name}. Espero que você esteja bem!

Este é um lembrete automático do seu Plano: ${plan}
Parcelamento: ${installments}
Valor R$: ${total_value}
Progresso: ${delivered}/${total} Aulas Concluídas
Chave Pix: ${pix || "informar no contato"}

Conte comigo para qualquer dúvida. Obrigado por estudar comigo! `;
  document.getElementById("billingPreview").textContent = preview;
}


// ==========================
// Tarefas
// ==========================

function renderTaskStats() {
  const todo = state.tasks.filter((t) => t.status === "todo").length;
  const doing = state.tasks.filter((t) => t.status === "doing").length;
  const done = state.tasks.filter((t) => t.status === "done").length;
  const total = state.tasks.length;

  const todoEl = document.getElementById("taskStatsTodo");
  const doingEl = document.getElementById("taskStatsDoing");
  const doneEl = document.getElementById("taskStatsDone");
  const totalEl = document.getElementById("taskStatsTotal");

  if (todoEl) todoEl.textContent = todo;
  if (doingEl) doingEl.textContent = doing;
  if (doneEl) doneEl.textContent = done;
  if (totalEl) totalEl.textContent = total;
}

function getFilteredTasks() {
  const statusFilter = document.getElementById("taskFilterStatus")?.value || "";
  const dateFilter = document.getElementById("taskFilterDate")?.value || "";
  const tagsFilter = document.getElementById("taskFilterTags")?.value.toLowerCase().trim() || "";

  let filtered = [...state.tasks];

  if (statusFilter) {
    filtered = filtered.filter((t) => t.status === statusFilter);
  }

  if (dateFilter) {
    filtered = filtered.filter((t) => {
      if (!t.date && !t.dueDate) return false;
      return t.date === dateFilter || t.dueDate === dateFilter;
    });
  }

  if (tagsFilter) {
    const tagsArray = tagsFilter.split(",").map((t) => t.trim().toLowerCase());
    filtered = filtered.filter((t) => {
      if (!t.tags) return false;
      const taskTags = t.tags.toLowerCase();
      return tagsArray.some((tag) => taskTags.includes(tag));
    });
  }

  return filtered;
}

function renderTasks() {
  const list = document.getElementById("taskList");
  if (!list) return;

  const filteredTasks = getFilteredTasks();
  const titleEl = document.getElementById("taskListTitle");
  const subtitleEl = document.getElementById("taskListSubtitle");

  if (titleEl && subtitleEl) {
    if (filteredTasks.length === state.tasks.length) {
      titleEl.textContent = "Todas as Tarefas";
      subtitleEl.textContent = `${filteredTasks.length} tarefa(s) no total`;
    } else {
      titleEl.textContent = "Tarefas Filtradas";
      subtitleEl.textContent = `${filteredTasks.length} de ${state.tasks.length} tarefa(s)`;
    }
  }

  if (filteredTasks.length === 0) {
    list.innerHTML = `
      <div style="text-align: center; padding: 48px; color: var(--text-muted);">
        <p style="font-size: 18px; margin-bottom: 8px;">Nenhuma tarefa encontrada</p>
        <p style="font-size: 14px;">${state.tasks.length === 0 ? 'Clique em "+ Nova Tarefa" para começar' : 'Tente ajustar os filtros'}</p>
      </div>
    `;
    return;
  }

  // Agrupa por status
  const tasksByStatus = {
    todo: filteredTasks.filter((t) => t.status === "todo"),
    doing: filteredTasks.filter((t) => t.status === "doing"),
    done: filteredTasks.filter((t) => t.status === "done"),
  };

  // Ordena cada grupo por data de vencimento (mais próximas primeiro)
  Object.keys(tasksByStatus).forEach((status) => {
    tasksByStatus[status].sort((a, b) => {
      const dateA = a.dueDate || a.date || "9999-12-31";
      const dateB = b.dueDate || b.date || "9999-12-31";
      return dateA.localeCompare(dateB);
    });
  });

  list.innerHTML = `
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px;">
      ${["todo", "doing", "done"]
        .map((status) => {
          const tasks = tasksByStatus[status];
          const statusLabels = {
            todo: "A fazer",
            doing: "Fazendo",
            done: "Concluída",
          };
          const statusColors = {
            todo: { bg: "#fff3cd", border: "#ffc107", text: "#856404" },
            doing: { bg: "#cfe2ff", border: "#0d6efd", text: "#084298" },
            done: { bg: "#d1e7dd", border: "#198754", text: "#0f5132" },
          };

          return `
            <div style="background: ${statusColors[status].bg}; border: 2px solid ${statusColors[status].border}; border-radius: 12px; padding: 16px;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; padding-bottom: 12px; border-bottom: 2px solid ${statusColors[status].border};">
                <h4 style="margin: 0; font-size: 16px; font-weight: 600; color: ${statusColors[status].text};">
                  ${statusLabels[status]}
                </h4>
                <span style="background: ${statusColors[status].border}; color: white; padding: 4px 8px; border-radius: 12px; font-size: 12px; font-weight: 600;">
                  ${tasks.length}
                </span>
              </div>
              <div style="display: flex; flex-direction: column; gap: 12px;">
                ${tasks.length === 0
                  ? `<p style="text-align: center; color: ${statusColors[status].text}; font-size: 14px; font-style: italic; padding: 16px;">Nenhuma tarefa</p>`
                  : tasks
                      .map((task) => {
                        // Verifica se está vencida (cria data local para evitar problema de fuso horário)
                        const isOverdue = (() => {
                          if (!task.dueDate || task.status === "done") return false;
                          const [year, month, day] = task.dueDate.split("-").map(Number);
                          const dueDate = new Date(year, month - 1, day);
                          const today = new Date();
                          today.setHours(0, 0, 0, 0); // Zera horas para comparar apenas datas
                          return dueDate < today;
                        })();
                        const tagsArray = task.tags
                          ? task.tags.split(",").map((t) => t.trim()).filter((t) => t)
                          : [];

                        return `
                          <div class="task-card" style="background: white; border: 1px solid ${statusColors[status].border}; border-radius: 8px; padding: 12px; ${isOverdue ? "border-left: 4px solid #dc3545;" : ""}">
                            <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 8px;">
                              <h5 style="margin: 0; font-size: 14px; font-weight: 600; color: var(--text-primary); flex: 1;">
                                ${task.title}
                              </h5>
                              <div style="display: flex; gap: 4px;">
                                <button class="tag edit-task-btn" data-task-id="${task.id}" style="background: var(--accent-light); color: var(--accent); padding: 4px 8px; font-size: 11px; border: none; border-radius: 4px; cursor: pointer;">
                                  Editar
                                </button>
                                <button class="tag delete-task-btn" data-task-id="${task.id}" style="background: #fee; color: #c33; padding: 4px 8px; font-size: 11px; border: none; border-radius: 4px; cursor: pointer;">
                                  Excluir
                                </button>
                              </div>
                            </div>
                            
                            ${task.date || task.dueDate
                              ? `
                              <div style="margin-bottom: 8px; font-size: 12px; color: var(--text-muted);">
                                ${task.date ? `<span>📅 ${formatDate(task.date)}</span>` : ""}
                                ${task.dueDate
                                  ? `<span style="margin-left: 8px; ${isOverdue ? "color: #dc3545; font-weight: 600;" : ""}">⏰ ${formatDate(task.dueDate)} ${isOverdue ? "(Vencida)" : ""}</span>`
                                  : ""}
                              </div>
                            `
                              : ""}
                            
                            ${tagsArray.length > 0
                              ? `
                              <div style="margin-bottom: 8px; display: flex; flex-wrap: wrap; gap: 4px;">
                                ${tagsArray
                                  .map(
                                    (tag) =>
                                      `<span style="background: #e9ecef; color: #495057; padding: 2px 6px; border-radius: 4px; font-size: 11px;">#${tag}</span>`
                                  )
                                  .join("")}
                              </div>
                            `
                              : ""}
                            
                            ${task.notes
                              ? `<p style="margin: 0; font-size: 12px; color: var(--text-muted); line-height: 1.4;">${task.notes}</p>`
                              : ""}
                            
                            <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid #e9ecef; display: flex; gap: 4px; flex-wrap: wrap;">
                              ${["todo", "doing", "done"]
                                .filter((s) => s !== task.status)
                                .map(
                                  (s) => `
                                <button class="tag change-status-btn" data-task-id="${task.id}" data-status="${s}" style="background: ${statusColors[s].bg}; color: ${statusColors[s].text}; padding: 4px 8px; font-size: 11px; border: 1px solid ${statusColors[s].border}; border-radius: 4px; cursor: pointer;">
                                  ${statusLabels[s]}
                                </button>
                              `
                                )
                                .join("")}
                            </div>
                          </div>
                        `;
                      })
                      .join("")}
              </div>
            </div>
          `;
        })
        .join("")}
    </div>
  `;

  // Anexa event listeners
  list.querySelectorAll(".edit-task-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const taskId = parseInt(btn.dataset.taskId);
      openTaskForm(taskId);
    });
  });

  list.querySelectorAll(".delete-task-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const taskId = parseInt(btn.dataset.taskId);
      deleteTask(taskId);
    });
  });

  list.querySelectorAll(".change-status-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const taskId = parseInt(btn.dataset.taskId);
      const newStatus = btn.dataset.status;
      await changeTaskStatus(taskId, newStatus);
    });
  });
}

function formatDate(dateString) {
  if (!dateString) return "";
  // Evita problema de fuso horário: cria a data localmente
  const [year, month, day] = dateString.split("-").map(Number);
  const date = new Date(year, month - 1, day); // month - 1 porque janeiro = 0
  return date.toLocaleDateString("pt-BR");
}

function changeTaskStatus(taskId, newStatus) {
  return fetchJSON(`/tasks/${taskId}/`, {
    method: "PATCH",
    body: JSON.stringify({ status: newStatus }),
  })
    .then(async () => {
      await loadTasks();
      renderTasks();
      renderTaskStats();
    })
    .catch((error) => {
      console.error(error);
      alert("Não foi possível atualizar o status da tarefa.");
    });
}

function deleteTask(taskId) {
  const task = state.tasks.find((t) => t.id === taskId);
  if (!task) return;

  const ok = confirm(`Tem certeza que deseja excluir a tarefa "${task.title}"?`);
  if (!ok) return;

  fetchJSON(`/tasks/${taskId}/`, {
    method: "DELETE",
  })
    .then(async () => {
      await loadTasks();
      renderTasks();
      renderTaskStats();
    })
    .catch((error) => {
      console.error(error);
      alert("Não foi possível excluir a tarefa.");
    });
}

function openTaskForm(taskId = null) {
  editingTaskId = taskId;
  const formCard = document.getElementById("taskFormCard");
  const titleEl = document.getElementById("taskFormTitle");
  const form = document.getElementById("taskForm");

  if (!formCard || !form || !titleEl) return;

  if (taskId) {
    const task = state.tasks.find((t) => t.id === taskId);
    if (task) {
      titleEl.textContent = "Editar Tarefa";
      form.taskTitle.value = task.title;
      form.taskDate.value = task.date || "";
      form.taskDueDate.value = task.dueDate || "";
      form.taskStatus.value = task.status;
      form.taskTags.value = task.tags || "";
      form.taskNotes.value = task.notes || "";
    }
  } else {
    titleEl.textContent = "Nova Tarefa";
    form.reset();
    form.taskStatus.value = "todo";
  }

  formCard.style.display = "flex";
  window.scrollTo({ top: formCard.offsetTop - 80, behavior: "smooth" });
}

function closeTaskForm() {
  const formCard = document.getElementById("taskFormCard");
  if (formCard) {
    formCard.style.display = "none";
  }
  editingTaskId = null;
}

async function onTaskFormSubmit(event) {
  event.preventDefault();
  const form = event.target;

  const payload = {
    title: form.taskTitle.value.trim(),
    date: form.taskDate.value || null,
    due_date: form.taskDueDate.value || null,
    status: form.taskStatus.value,
    tags: form.taskTags.value.trim(),
    notes: form.taskNotes.value.trim(),
  };

  if (!payload.title) {
    alert("Informe um título para a tarefa.");
    return;
  }

  try {
    if (editingTaskId) {
      await fetchJSON(`/tasks/${editingTaskId}/`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
    } else {
      await fetchJSON("/tasks/", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    }

    await loadTasks();
    renderTasks();
    renderTaskStats();
    closeTaskForm();
  } catch (error) {
    console.error(error);
    alert(error.message || "Não foi possível salvar a tarefa.");
  }
}

function initTasksUI() {
  // Botão nova tarefa
  const newTaskBtn = document.getElementById("newTaskBtn");
  if (newTaskBtn) {
    newTaskBtn.addEventListener("click", () => openTaskForm(null));
  }

  // Botão cancelar formulário
  const cancelTaskBtn = document.getElementById("cancelTaskForm");
  if (cancelTaskBtn) {
    cancelTaskBtn.addEventListener("click", closeTaskForm);
  }

  // Submit do formulário
  const taskForm = document.getElementById("taskForm");
  if (taskForm) {
    taskForm.addEventListener("submit", onTaskFormSubmit);
  }

  // Filtros
  const statusFilter = document.getElementById("taskFilterStatus");
  const dateFilter = document.getElementById("taskFilterDate");
  const tagsFilter = document.getElementById("taskFilterTags");
  const clearFiltersBtn = document.getElementById("clearTaskFilters");

  const applyFilters = () => {
    renderTasks();
    renderTaskStats();
  };

  if (statusFilter) {
    statusFilter.addEventListener("change", applyFilters);
  }
  if (dateFilter) {
    dateFilter.addEventListener("change", applyFilters);
  }
  if (tagsFilter) {
    tagsFilter.addEventListener("input", applyFilters);
  }
  if (clearFiltersBtn) {
    clearFiltersBtn.addEventListener("click", () => {
      if (statusFilter) statusFilter.value = "";
      if (dateFilter) dateFilter.value = "";
      if (tagsFilter) tagsFilter.value = "";
      applyFilters();
    });
  }
}




function renderFinance() {
  const list = document.getElementById("financeList");
  const monthTitleEl = document.getElementById("financeMonthTitle");
  if (!list || !monthTitleEl) return;

  list.innerHTML = "";

  const label = monthName(state.currentMonth);
  monthTitleEl.textContent = label.charAt(0).toUpperCase() + label.slice(1);

  if (state.finances.length === 0) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent =
      "Nenhum lançamento financeiro para este mês. Crie as cobranças pelo admin por enquanto.";
    list.append(empty);
    return;
  }

  state.finances.forEach((inv) => {
    const row = document.createElement("div");
    row.className = `finance-row ${inv.status}`;

    const main = document.createElement("div");
    main.className = "finance-main";

    const nameEl = document.createElement("div");
    nameEl.className = "finance-name";
    nameEl.textContent = inv.studentName || "Aluno desconhecido";

    const infoEl = document.createElement("div");
    infoEl.className = "finance-info";

    const statusLabel = financeStatusLabels[inv.status] || inv.status;
    const dueText = inv.dueDate
      ? `Vencimento: ${new Date(inv.dueDate).toLocaleDateString("pt-BR")}`
      : "Sem vencimento definido";

    infoEl.textContent = `${formatBRL(inv.amount)} • ${statusLabel} • ${dueText}`;

    main.append(nameEl, infoEl);

    const actions = document.createElement("div");
    actions.className = "finance-actions";

    ["paid", "pending", "overdue", "remind"].forEach((statusKey) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "tag";
      btn.textContent = financeStatusLabels[statusKey];
      btn.addEventListener("click", () => {
        updateInvoiceStatus(inv, statusKey);
      });
      actions.append(btn);
    });

    row.append(main, actions);
    list.append(row);
  });
}

async function updateInvoiceStatus(invoice, newStatus) {
  try {
    await fetchJSON(`/invoices/${invoice.id}/`, {
      method: "PATCH",
      body: JSON.stringify({ status: newStatus }),
    });

    invoice.status = newStatus;
    renderFinance();
  } catch (error) {
    console.error(error);
    alert("Não foi possível atualizar o status financeiro.");
  }
}

// ==========================
// Lançamentos Financeiros
// ==========================

function formatDateBR(dateStr) {
  if (!dateStr) return "";
  const [year, month, day] = dateStr.split("-");
  return `${day}/${month}/${year}`;
}

function renderFinancialStats() {
  const pendingEl = document.getElementById("statFinancePending");
  const paidEl = document.getElementById("statFinancePaid");
  const overdueEl = document.getElementById("statFinanceOverdue");
  const countEl = document.getElementById("statFinanceCount");

  if (!pendingEl || !paidEl || !overdueEl || !countEl) return;

  const pending = state.financialEntries
    .filter((e) => e.status === "pending")
    .reduce((sum, e) => sum + Number(e.amount || 0), 0);

  const paid = state.financialEntries
    .filter((e) => e.status === "paid")
    .reduce((sum, e) => sum + Number(e.amount || 0), 0);

  const overdue = state.financialEntries
    .filter((e) => e.status === "overdue")
    .reduce((sum, e) => sum + Number(e.amount || 0), 0);

  pendingEl.textContent = formatBRL(pending);
  paidEl.textContent = formatBRL(paid);
  overdueEl.textContent = formatBRL(overdue);
  countEl.textContent = state.financialEntries.length;
}

function renderFinancialEntries() {
  const list = document.getElementById("financialEntriesList");
  const monthTitleEl = document.getElementById("financeMonthTitle");
  if (!list) return;

  list.innerHTML = "";

  if (monthTitleEl) {
    const label = monthName(state.financeViewMonth);
    monthTitleEl.textContent = label.charAt(0).toUpperCase() + label.slice(1);
  }

  // Filtro de status
  const filterSelect = document.getElementById("financeFilterStatus");
  const statusFilter = filterSelect ? filterSelect.value : "";

  let entries = state.financialEntries;
  if (statusFilter) {
    entries = entries.filter((e) => e.status === statusFilter);
  }

  if (entries.length === 0) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent = "Nenhum lançamento financeiro para este mês. Clique em '+ Novo Lançamento' para criar.";
    list.append(empty);
    return;
  }

  entries.forEach((entry) => {
    const row = document.createElement("div");
    row.className = `finance-row ${entry.status}`;

    const main = document.createElement("div");
    main.className = "finance-main";

    const nameEl = document.createElement("div");
    nameEl.className = "finance-name";
    nameEl.innerHTML = `<strong>${entry.studentName || "Aluno"}</strong> - ${entry.description}`;

    const infoEl = document.createElement("div");
    infoEl.className = "finance-info";

    const statusLabel = financialEntryStatusLabels[entry.status] || entry.status;
    const dueText = entry.dueDate
      ? `Venc: ${formatDateBR(entry.dueDate)}`
      : "Sem vencimento";
    const installmentText = entry.installments > 1
      ? `Parcela ${entry.currentInstallment}/${entry.installments}`
      : "À vista";

    infoEl.textContent = `${formatBRL(entry.amount)} • ${installmentText} • ${statusLabel} • ${dueText}`;

    main.append(nameEl, infoEl);

    const actions = document.createElement("div");
    actions.className = "finance-actions";

    // Botões de status
    ["paid", "pending", "overdue"].forEach((statusKey) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "tag";
      btn.textContent = financialEntryStatusLabels[statusKey];
      btn.addEventListener("click", () => updateFinancialEntryStatus(entry, statusKey));
      actions.append(btn);
    });

    // Botão editar
    const editBtn = document.createElement("button");
    editBtn.type = "button";
    editBtn.className = "tag";
    editBtn.textContent = "Editar";
    editBtn.addEventListener("click", () => openFinancialEntryForm(entry));
    actions.append(editBtn);

    // Botão excluir
    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.className = "tag";
    deleteBtn.style.background = "#fee";
    deleteBtn.style.color = "#c33";
    deleteBtn.textContent = "Excluir";
    deleteBtn.addEventListener("click", () => deleteFinancialEntry(entry));
    actions.append(deleteBtn);

    row.append(main, actions);
    list.append(row);
  });
}

async function updateFinancialEntryStatus(entry, newStatus) {
  try {
    const payload = { status: newStatus };
    if (newStatus === "paid") {
      payload.payment_date = toISO(new Date());
    }
    await fetchJSON(`/financial-entries/${entry.id}/`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
    entry.status = newStatus;
    if (newStatus === "paid") {
      entry.paymentDate = toISO(new Date());
    }
    await loadFinancialEntries();
    renderFinancialEntries();
    renderFinancialStats();
  } catch (error) {
    console.error(error);
    alert("Não foi possível atualizar o status.");
  }
}

async function deleteFinancialEntry(entry) {
  if (!confirm(`Tem certeza que deseja excluir o lançamento "${entry.description}"?`)) {
    return;
  }

  try {
    await fetchJSON(`/financial-entries/${entry.id}/`, {
      method: "DELETE",
    });
    alert("Lançamento excluído com sucesso!");
    await loadFinancialEntries();
    renderFinancialEntries();
    renderFinancialStats();
  } catch (error) {
    console.error(error);
    alert("Não foi possível excluir o lançamento.");
  }
}

function openFinancialEntryForm(entry = null) {
  const card = document.getElementById("financialEntryFormCard");
  const titleEl = document.getElementById("financialEntryFormTitle");
  const form = document.getElementById("financialEntryForm");

  if (!card || !form || !titleEl) {
    console.error("Elementos do formulário financeiro não encontrados");
    return;
  }

  // Popula select de alunos
  const feStudent = document.getElementById("feStudent");
  if (feStudent && feStudent.options.length <= 1) {
    feStudent.innerHTML = '<option value="">Selecione um aluno</option>';
    state.students.forEach((student) => {
      if (student.active !== false) {
        const opt = document.createElement("option");
        opt.value = student.id;
        opt.textContent = student.name;
        feStudent.append(opt);
      }
    });
  }

  if (entry) {
    // Modo edição
    editingFinancialEntryId = entry.id;
    titleEl.textContent = "Editar Lançamento";

    document.getElementById("feStudent").value = entry.studentId || "";
    document.getElementById("feDescription").value = entry.description || "";
    document.getElementById("feAmount").value = entry.amount || "";
    document.getElementById("feInstallments").value = entry.installments || 1;
    document.getElementById("feIssueDate").value = entry.issueDate || "";
    document.getElementById("feDueDate").value = entry.dueDate || "";
    document.getElementById("feStatus").value = entry.status || "pending";
    document.getElementById("fePaymentMethod").value = entry.paymentMethod || "pix";
    document.getElementById("feNotes").value = entry.notes || "";

    // Desabilita parcelas em modo edição (não pode alterar)
    document.getElementById("feInstallments").disabled = true;
  } else {
    // Modo criação
    editingFinancialEntryId = null;
    titleEl.textContent = "Cadastrar Recebimento";
    form.reset();

    // Data de lançamento = hoje
    const feIssueDate = document.getElementById("feIssueDate");
    if (feIssueDate) {
      feIssueDate.value = toISO(new Date());
    }

    // Data de vencimento = dia 5 do próximo mês
    const nextMonth = new Date();
    nextMonth.setMonth(nextMonth.getMonth() + 1);
    nextMonth.setDate(5);
    const feDueDate = document.getElementById("feDueDate");
    if (feDueDate) {
      feDueDate.value = toISO(nextMonth);
    }

    const feInstallments = document.getElementById("feInstallments");
    if (feInstallments) {
      feInstallments.value = 1;
      feInstallments.disabled = false;
    }
  }

  card.style.display = "flex";
  if (feStudent) feStudent.focus();
}

async function createInstallments(basePayload, totalInstallments) {
  // Cria a primeira parcela
  const firstPayload = { ...basePayload, current_installment: 1 };
  await fetchJSON("/financial-entries/", {
    method: "POST",
    body: JSON.stringify(firstPayload),
  });

  // Cria as parcelas restantes
  const baseDueDate = new Date(basePayload.due_date);
  const baseIssueDate = new Date(basePayload.issue_date);

  for (let i = 2; i <= totalInstallments; i++) {
    const installmentPayload = { ...basePayload };
    installmentPayload.current_installment = i;

    // Calcula data de vencimento (mesmo dia do mês seguinte)
    const dueDate = new Date(baseDueDate);
    dueDate.setMonth(dueDate.getMonth() + (i - 1));

    // Calcula data de lançamento (mesmo dia do mês seguinte)
    const issueDate = new Date(baseIssueDate);
    issueDate.setMonth(issueDate.getMonth() + (i - 1));

    installmentPayload.due_date = toISO(dueDate);
    installmentPayload.issue_date = toISO(issueDate);

    await fetchJSON("/financial-entries/", {
      method: "POST",
      body: JSON.stringify(installmentPayload),
    });
  }
}

// antes: usava prompt
// async function addTask() { ... }

function addTask() {
  // só abre o modal já preparado pra criação
  openTaskFormToCreate();
}



// ==========================
// Navegação e formulários
// ==========================

async function showView(viewId) {
  document.querySelectorAll(".view").forEach((view) => {
    view.classList.toggle("active", view.id === viewId);
  });
  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.view === viewId);
  });

  // Mostra/oculta menu de usuários baseado em is_admin
  const navUsers = document.getElementById("navUsers");
  if (navUsers && state.currentUser) {
    navUsers.style.display = state.currentUser.is_admin ? "flex" : "none";
  }

  // Se abrir a visualização de planejamento
  if (viewId === "view-planning") {
    try {
      await loadLessonPlans();
      renderPlanning();
      initPlanningUI();
    } catch (error) {
      console.error("Erro ao carregar planejamento:", error);
    }
  }
  
  // Se abrir a visualização de tarefas
  if (viewId === "view-tasks") {
    try {
      await loadTasks();
      renderTasks();
      renderTaskStats();
      initTasksUI();
    } catch (error) {
      console.error("Erro ao carregar tarefas:", error);
    }
  }
  
  // Se abrir a visualização financeira, garante que o mês está sincronizado
  if (viewId === "view-finance") {
    // Se financeViewMonth não foi inicializado ou está muito diferente, usa o mês atual
    const monthsDiff = Math.abs(
      (state.financeViewMonth.getFullYear() - state.today.getFullYear()) * 12 +
      (state.financeViewMonth.getMonth() - state.today.getMonth())
    );
    if (monthsDiff > 12) {
      state.financeViewMonth = new Date(state.today);
    }
    // Recarrega os dados do mês financeiro
    loadFinancialEntries().then(() => {
      renderFinancialEntries();
      renderFinancialStats();
    });
  }

  window.scrollTo({ top: 0, behavior: "smooth" });
}

function attachNavigation() {
  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.addEventListener("click", () => {
      showView(btn.dataset.view);
    });
  });
}

function attachForms() {
  // form de anotação do dia -> cria/edita aula via API
  document.getElementById("noteForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!state.selectedDate) {
      alert("Selecione um dia no calendário primeiro.");
      return;
    }

    const title = document.getElementById("noteTitle").value.trim();
    const status = document.getElementById("noteStatus").value;
    const info = document.getElementById("noteInfo").value.trim();
    const studentId = document.getElementById("noteStudent").value;
    const timeValue = document.getElementById("noteTime").value;

    if (!title) {
      alert("Informe a descrição da aula.");
      return;
    }

    if (!studentId) {
      alert("Selecione um aluno.");
      return;
    }

    const payload = {
      student: Number(studentId),
      date: state.selectedDate,
      time: timeValue || null,
      title,
      info,
      status,
    };

    try {
      if (editingLessonId) {
        // UPDATE
        await fetchJSON(`/lessons/${editingLessonId}/`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
      } else {
        // CREATE
        await fetchJSON("/lessons/", {
          method: "POST",
          body: JSON.stringify(payload),
        });
      }

      resetLessonFormMode();
      await loadLessonsForCurrentMonth();
      renderStats();
      renderCalendar();
      renderDayDetails();
    } catch (error) {
      console.error(error);
      alert("Não foi possível salvar a aula.");
    }
  });

  // cobrança
  document.getElementById("billingForm").addEventListener("input", renderBillingPreview);
  document.getElementById("billingStudent").addEventListener("change", populateBilling);
  document.getElementById("copyBilling").addEventListener("click", async () => {
    const preview = document.getElementById("billingPreview").textContent;
    if (!preview) return;
    try {
      await navigator.clipboard.writeText(preview);
      alert("Mensagem copiada!");
    } catch {
      alert("Não foi possível copiar automaticamente, selecione o texto manualmente.");
    }
  });

  // navegação entre meses
  document.getElementById("monthBack").addEventListener("click", () => {
    changeMonth(-1).catch((err) => console.error(err));
  });
  document.getElementById("monthForward").addEventListener("click", () => {
    changeMonth(1).catch((err) => console.error(err));
  });

  // botão atalho "Novo agendamento" na sidebar
  document.getElementById("createLessonBtn").addEventListener("click", () => {
    const todayKey = toISO(state.today);
    selectDay(todayKey);
    document.getElementById("noteTitle").focus();
  });

  // alunos
  document.getElementById("addStudent").addEventListener("click", () => {
    openStudentForm(null);
  });

  document.getElementById("copyBilling").addEventListener("click", async () => {
    const preview = document.getElementById("billingPreview").textContent;
    if (!preview) return;
    try {
      await navigator.clipboard.writeText(preview);
      alert("Mensagem copiada!");
    } catch {
      alert("Não foi possível copiar automaticamente, selecione o texto manualmente.");
    }
  });

  const openWaBtn = document.getElementById("openBillingWhatsApp");
  if (openWaBtn) {
    openWaBtn.addEventListener("click", openBillingWhatsApp);
  }

  // Botão de novo lançamento financeiro
  const newFinancialEntryBtn = document.getElementById("newFinancialEntryBtn");
  if (newFinancialEntryBtn) {
    newFinancialEntryBtn.addEventListener("click", () => {
      openFinancialEntryForm(null);
    });
  }

  // Botão cancelar formulário financeiro
  const cancelFinancialEntryForm = document.getElementById("cancelFinancialEntryForm");
  if (cancelFinancialEntryForm) {
    cancelFinancialEntryForm.addEventListener("click", () => {
      const card = document.getElementById("financialEntryFormCard");
      if (card) {
        card.style.display = "none";
      }
      editingFinancialEntryId = null;
      const form = document.getElementById("financialEntryForm");
      if (form) form.reset();
    });
  }

  // Filtro de status dos lançamentos financeiros
  const financeFilterStatus = document.getElementById("financeFilterStatus");
  if (financeFilterStatus) {
    financeFilterStatus.addEventListener("change", () => {
      renderFinancialEntries();
    });
  }

  // Navegação de meses na visualização financeira
  const financeMonthBack = document.getElementById("financeMonthBack");
  const financeMonthForward = document.getElementById("financeMonthForward");

  if (financeMonthBack) {
    financeMonthBack.addEventListener("click", async () => {
      const current = state.financeViewMonth;
      state.financeViewMonth = new Date(
        current.getFullYear(),
        current.getMonth() - 1,
        1
      );
      await loadFinancialEntries();
      renderFinancialEntries();
      renderFinancialStats();
    });
  }

  if (financeMonthForward) {
    financeMonthForward.addEventListener("click", async () => {
      const current = state.financeViewMonth;
      state.financeViewMonth = new Date(
        current.getFullYear(),
        current.getMonth() + 1,
        1
      );
      await loadFinancialEntries();
      renderFinancialEntries();
      renderFinancialStats();
    });
  }

  // Submit do formulário financeiro
  const financialEntryForm = document.getElementById("financialEntryForm");
  if (financialEntryForm) {
    financialEntryForm.addEventListener("submit", async (event) => {
      event.preventDefault();

      const studentId = document.getElementById("feStudent")?.value;
      const description = document.getElementById("feDescription")?.value.trim();
      const amount = document.getElementById("feAmount")?.value;
      const installments = document.getElementById("feInstallments")?.value || 1;
      const issueDate = document.getElementById("feIssueDate")?.value;
      const dueDate = document.getElementById("feDueDate")?.value;
      const status = document.getElementById("feStatus")?.value || "pending";
      const paymentMethod = document.getElementById("fePaymentMethod")?.value || "pix";
      const notes = document.getElementById("feNotes")?.value.trim() || "";

      if (!studentId || !description || !amount || !issueDate || !dueDate) {
        alert("Preencha todos os campos obrigatórios.");
        return;
      }

      const payload = {
        student: Number(studentId),
        description,
        amount: parseFloat(amount),
        installments: Number(installments),
        current_installment: 1,
        issue_date: issueDate,
        due_date: dueDate,
        status,
        payment_method: paymentMethod,
        notes,
      };

      // Se o status for "paid" e não tiver payment_date, define como hoje
      if (status === "paid" && !payload.payment_date) {
        payload.payment_date = toISO(new Date());
      }

      try {
        if (editingFinancialEntryId) {
          // Edição
          await fetchJSON(`/financial-entries/${editingFinancialEntryId}/`, {
            method: "PATCH",
            body: JSON.stringify(payload),
          });
          alert("Lançamento atualizado com sucesso!");
        } else {
          // Criação - verifica se precisa criar parcelas
          const installmentsNum = Number(installments);
          if (installmentsNum > 1) {
            // Cria todas as parcelas
            await createInstallments(payload, installmentsNum);
            alert(`${installmentsNum} parcelas criadas com sucesso!`);
          } else {
            // Cria apenas um lançamento
            await fetchJSON("/financial-entries/", {
              method: "POST",
              body: JSON.stringify(payload),
            });
            alert("Lançamento salvo com sucesso!");
          }
        }

        // Fecha o formulário
        const card = document.getElementById("financialEntryFormCard");
        if (card) {
          card.style.display = "none";
        }

        // Reseta o formulário
        financialEntryForm.reset();
        editingFinancialEntryId = null;

        // Recarrega e renderiza os lançamentos
        await loadFinancialEntries();
        renderFinancialEntries();
        renderFinancialStats();
      } catch (error) {
        console.error(error);
        alert("Não foi possível salvar o lançamento. Verifique o console para mais detalhes.");
      }
    });
  }

}

function parseISODateLocal(iso) {
  const [year, month, day] = iso.split("-").map(Number);
  // month - 1 porque no JS janeiro = 0
  return new Date(year, month - 1, day);
}



// ==========================
// Inicialização
// ==========================

async function init() {
  attachNavigation();
  attachForms();

  try {
    await loadInitialData();
  } catch (error) {
    console.error(error);
    alert("Não foi possível carregar os dados iniciais. Verifique a API.");
  }

  renderStudents();
  renderStats();
  renderCalendar();
  renderBillingPreview();
  renderFinance();
  renderFinanceTotal();
  renderFinancialEntries();
  renderFinancialStats();

  state.selectedDate = toISO(state.today);
  renderDayDetails();

  showView("view-calendar");
}

// ==========================
// Autenticação
// ==========================

async function checkAuth() {
  try {
    const csrf = getCookie("csrftoken");
    console.log("Fazendo requisição para /api/auth/current-user/");
    const response = await fetch("/api/auth/current-user/", {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrf || "",
      },
      credentials: "same-origin",
    });

    console.log("Resposta recebida:", response.status, response.statusText);

    // Se não for OK, verifica o conteúdo
    if (!response.ok) {
      let errorData;
      try {
        errorData = await response.json();
      } catch {
        errorData = { error: "Erro desconhecido" };
      }

      if (response.status === 401 || response.status === 403 || errorData.error) {
        console.log("Usuário não autenticado (status " + response.status + "), redirecionando para login...");
        window.location.href = "/login/";
        return false;
      }

      console.error("Erro na API:", response.status, errorData);
      if (response.status >= 500) {
        throw new Error(`Erro no servidor (${response.status})`);
      }
      // Se não for erro de autenticação, tenta continuar
    }

    const user = await response.json();
    console.log("Dados do usuário recebidos:", user);

    // Verifica se a resposta contém erro (quando não autenticado)
    if (user && user.error) {
      console.log("Erro de autenticação:", user.error);
      window.location.href = "/login/";
      return false;
    }

    if (user && user.id) {
      state.currentUser = user;
      console.log("Usuário autenticado:", user.username, "Admin:", user.is_admin);
      return true;
    } else {
      console.log("Resposta inválida do servidor:", user);
      window.location.href = "/login/";
      return false;
    }
  } catch (error) {
    console.error("Erro ao verificar autenticação:", error);
    window.location.href = "/login/";
    return false;
  }
}

async function handleLogout() {
  console.log("Iniciando logout...");
  try {
    const csrf = getCookie("csrftoken");
    const response = await fetch("/api/auth/logout/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrf || "",
      },
      credentials: "same-origin",
    });
    console.log("Logout realizado, redirecionando...");
    window.location.href = "/login/";
  } catch (error) {
    console.error("Erro ao fazer logout:", error);
    // Mesmo com erro, redireciona para login
    window.location.href = "/login/";
  }
}

// ==========================
// Gerenciamento de Usuários
// ==========================

async function loadUsers() {
  try {
    const users = await fetchJSON("/users/");
    state.users = users;
  } catch (error) {
    console.error("Erro ao carregar usuários:", error);
    state.users = [];
  }
}

function renderUsers() {
  const list = document.getElementById("usersList");
  if (!list) return;

  list.innerHTML = "";

  if (state.users.length === 0) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent = "Nenhum usuário cadastrado.";
    list.append(empty);
    return;
  }

  state.users.forEach((user) => {
    const row = document.createElement("div");
    row.className = "student-row";
    row.innerHTML = `
      <div class="student-main">
        <div class="student-name">
          <strong>${user.username}</strong>
          ${user.is_admin ? '<span class="tag" style="margin-left: 8px;">Admin</span>' : ''}
        </div>
        <div class="student-info">
          ${user.email || "Sem email"} • ${user.is_active ? "Ativo" : "Inativo"}
        </div>
      </div>
      <div class="student-actions">
        <button class="tag" onclick="openUserForm(${user.id})">Editar</button>
        <button class="tag" onclick="deleteUser(${user.id})" style="background: #fee; color: #c33;">Excluir</button>
      </div>
    `;
    list.append(row);
  });
}

function openUserForm(userId = null) {
  const card = document.getElementById("userFormCard");
  const titleEl = document.getElementById("userFormTitle");
  const form = document.getElementById("userForm");

  if (!card || !form || !titleEl) {
    console.error("Elementos do formulário de usuário não encontrados");
    return;
  }

  if (userId) {
    const user = state.users.find((u) => u.id === userId);
    if (!user) return;

    editingUserId = userId;
    titleEl.textContent = "Editar Usuário";

    document.getElementById("uUsername").value = user.username || "";
    document.getElementById("uEmail").value = user.email || "";
    document.getElementById("uFirstName").value = user.first_name || "";
    document.getElementById("uLastName").value = user.last_name || "";
    document.getElementById("uIsAdmin").checked = user.is_admin || false;
    document.getElementById("uIsActive").checked = user.is_active !== false;
    document.getElementById("uPassword").value = "";
    document.getElementById("uPassword").required = false;
  } else {
    editingUserId = null;
    titleEl.textContent = "Novo Usuário";
    form.reset();
    document.getElementById("uPassword").required = true;
  }

  card.style.display = "flex";
}

function closeUserForm() {
  const card = document.getElementById("userFormCard");
  if (card) {
    card.style.display = "none";
  }
  editingUserId = null;
  const form = document.getElementById("userForm");
  if (form) form.reset();
}

async function onUserFormSubmit(event) {
  event.preventDefault();

  const username = document.getElementById("uUsername")?.value.trim();
  const email = document.getElementById("uEmail")?.value.trim();
  const firstName = document.getElementById("uFirstName")?.value.trim();
  const lastName = document.getElementById("uLastName")?.value.trim();
  const password = document.getElementById("uPassword")?.value;
  const isAdmin = document.getElementById("uIsAdmin")?.checked || false;
  const isActive = document.getElementById("uIsActive")?.checked !== false;

  if (!username) {
    alert("Username é obrigatório.");
    return;
  }

  if (!editingUserId && !password) {
    alert("Senha é obrigatória para novos usuários.");
    return;
  }

  const payload = {
    username,
    email,
    first_name: firstName,
    last_name: lastName,
    is_admin: isAdmin,
    is_active: isActive,
  };

  if (password) {
    payload.password = password;
  }

  try {
    if (editingUserId) {
      await fetchJSON(`/users/${editingUserId}/`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      alert("Usuário atualizado com sucesso!");
    } else {
      await fetchJSON("/users/", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      alert("Usuário criado com sucesso!");
    }

    closeUserForm();
    await loadUsers();
    renderUsers();
  } catch (error) {
    console.error(error);
    alert("Não foi possível salvar o usuário. Verifique o console para mais detalhes.");
  }
}

async function deleteUser(userId) {
  if (!confirm("Tem certeza que deseja excluir este usuário?")) {
    return;
  }

  try {
    await fetchJSON(`/users/${userId}/`, {
      method: "DELETE",
    });
    alert("Usuário excluído com sucesso!");
    await loadUsers();
    renderUsers();
  } catch (error) {
    console.error(error);
    alert("Não foi possível excluir o usuário.");
  }
}

function initUsersUI() {
  const newUserBtn = document.getElementById("newUserBtn");
  if (newUserBtn) {
    newUserBtn.addEventListener("click", () => openUserForm(null));
  }

  const cancelUserForm = document.getElementById("cancelUserForm");
  if (cancelUserForm) {
    cancelUserForm.addEventListener("click", closeUserForm);
  }

  const userForm = document.getElementById("userForm");
  if (userForm) {
    userForm.addEventListener("submit", onUserFormSubmit);
  }

}

// Anexa o botão de logout para todos os usuários (não apenas admins)
function attachLogoutButton() {
  const logoutBtn = document.getElementById("logoutBtn");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", handleLogout);
    console.log("Botão de logout anexado");
  } else {
    console.warn("Botão de logout não encontrado no DOM");
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  // Verifica autenticação antes de inicializar
  console.log("Verificando autenticação...");
  const isAuthenticated = await checkAuth();
  if (!isAuthenticated) {
    console.log("Usuário não autenticado, redirecionando...");
    return; // Redireciona para login
  }

  console.log("Usuário autenticado, inicializando aplicação...");

  // Anexa botão de logout para todos os usuários
  attachLogoutButton();

  init().catch((err) => console.error(err));

  // Se for admin, inicializa UI de usuários
  if (state.currentUser && state.currentUser.is_admin) {
    initUsersUI();
    await loadUsers();
    renderUsers();
  }
});

function renderFinanceTotal() {
  const totalEl = document.getElementById("financeTotalAmount");
  if (!totalEl || !state.finances) return;

  const total = state.finances
    .filter((inv) => RECEIVABLE_STATUSES.includes(inv.status))
    .reduce((sum, inv) => sum + (Number(inv.amount) || 0), 0);

  totalEl.textContent = total.toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
  });
}


// ==========================
// Planejamento de Aulas
// ==========================

async function loadLessonPlans(studentId = null) {
  try {
    const url = studentId 
      ? `/lesson-plans/?student=${studentId}` 
      : "/lesson-plans/";
    const plans = await fetchJSON(url);
    state.lessonPlans = plans.map((p) => ({
      id: p.id,
      studentId: p.student,
      studentName: p.student_name,
      date: p.date,
      links: p.links || "",
      linksList: p.links_list || [],
      goals: p.goals || "",
      createdAt: p.created_at,
      updatedAt: p.updated_at,
    }));
  } catch (error) {
    console.error("Erro ao carregar planejamentos:", error);
    state.lessonPlans = [];
  }
}

// Função helper para normalizar URLs e verificar se são válidas
function normalizeUrl(url) {
  if (!url || typeof url !== 'string') return { url: '', isValid: false };
  const trimmed = url.trim();
  if (!trimmed) return { url: '', isValid: false };
  
  // Se já começa com http:// ou https://, retorna como está
  if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) {
    return { url: trimmed, isValid: true };
  }
  
  // Se começa com //, adiciona https:
  if (trimmed.startsWith('//')) {
    return { url: 'https:' + trimmed, isValid: true };
  }
  
  // Se parece ser um domínio (contém ponto e não tem espaços), adiciona https://
  if (trimmed.includes('.') && !trimmed.includes(' ')) {
    return { url: 'https://' + trimmed, isValid: true };
  }
  
  // Se contém espaços ou não parece URL, não é válido
  if (trimmed.includes(' ')) {
    return { url: '', isValid: false };
  }
  
  // Tenta adicionar https:// para outros casos
  return { url: 'https://' + trimmed, isValid: true };
}

function renderPlanning() {
  const container = document.getElementById("planningList");
  if (!container) return;

  const selectedStudentId = document.getElementById("planStudentFilter")?.value || "";
  const filteredPlans = selectedStudentId
    ? state.lessonPlans.filter((p) => p.studentId === parseInt(selectedStudentId))
    : state.lessonPlans;

  // Atualiza título
  const titleEl = document.getElementById("planningListTitle");
  const subtitleEl = document.getElementById("planningListSubtitle");
  if (titleEl && subtitleEl) {
    if (selectedStudentId) {
      const student = state.students.find((s) => s.id === parseInt(selectedStudentId));
      titleEl.textContent = student ? `Planejamentos - ${student.name}` : "Planejamentos";
      subtitleEl.textContent = `${filteredPlans.length} planejamento(s) encontrado(s)`;
    } else {
      titleEl.textContent = "Todos os Planejamentos";
      subtitleEl.textContent = `${filteredPlans.length} planejamento(s) no total`;
    }
  }

  if (filteredPlans.length === 0) {
    container.innerHTML = `
      <div style="text-align: center; padding: 48px; color: var(--text-muted);">
        <p style="font-size: 18px; margin-bottom: 8px;">Nenhum planejamento encontrado</p>
        <p style="font-size: 14px;">Clique em "+ Novo Planejamento" para começar</p>
      </div>
    `;
    return;
  }

  // Agrupa por data
  const plansByDate = {};
  filteredPlans.forEach((plan) => {
    const dateKey = plan.date;
    if (!plansByDate[dateKey]) {
      plansByDate[dateKey] = [];
    }
    plansByDate[dateKey].push(plan);
  });

  // Ordena datas (mais recente primeiro)
  const sortedDates = Object.keys(plansByDate).sort((a, b) => new Date(b) - new Date(a));

  container.innerHTML = sortedDates
    .map((dateKey) => {
      const plans = plansByDate[dateKey];
      const dateObj = new Date(dateKey);
      const dateFormatted = dateObj.toLocaleDateString("pt-BR", {
        weekday: "long",
        year: "numeric",
        month: "long",
        day: "numeric",
      });

      return `
        <div class="planning-date-group" style="margin-bottom: 32px;">
          <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px; padding-bottom: 12px; border-bottom: 2px solid var(--border);">
            <h4 style="margin: 0; font-size: 18px; font-weight: 600; color: var(--text-primary);">
              ${dateFormatted.charAt(0).toUpperCase() + dateFormatted.slice(1)}
            </h4>
            <span style="color: var(--text-muted); font-size: 14px;">${plans.length} aula(s)</span>
          </div>
          ${plans
            .map((plan) => {
              const linksHtml = plan.linksList.length > 0
                ? plan.linksList
                    .filter((link) => link && link.trim()) // Remove links vazios
                    .map((link) => {
                      const { url: normalizedUrl, isValid } = normalizeUrl(link);
                      const displayText = link.length > 60 ? link.substring(0, 60) + "..." : link;
                      
                      if (!isValid || !normalizedUrl) {
                        // Se não for uma URL válida, mostra como texto simples
                        return `
                        <div style="margin-bottom: 8px; padding: 8px; background: #fff3cd; border-radius: 6px; border-left: 3px solid #ffc107;">
                          <span style="color: #856404; font-size: 14px;">
                            <span>⚠️</span>
                            <span style="margin-left: 6px;">${displayText}</span>
                            <span style="margin-left: 8px; font-size: 12px; font-style: italic;">(URL inválida)</span>
                          </span>
                        </div>
                      `;
                      }
                      
                      return `
                      <div style="margin-bottom: 8px;">
                        <a href="${normalizedUrl}" target="_blank" rel="noopener noreferrer" 
                           style="color: var(--accent); text-decoration: none; word-break: break-all; display: inline-flex; align-items: center; gap: 6px;">
                          <span>🔗</span>
                          <span>${displayText}</span>
                        </a>
                      </div>
                    `;
                    })
                    .join("")
                : '<p style="color: var(--text-muted); font-size: 14px; font-style: italic;">Nenhum link adicionado</p>';

              return `
                <div class="planning-card" style="background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px; padding: 20px; margin-bottom: 16px;">
                  <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 16px;">
                    <div style="flex: 1;">
                      <h5 style="margin: 0 0 8px 0; font-size: 16px; font-weight: 600; color: var(--text-primary);">
                        ${plan.studentName}
                      </h5>
                    </div>
                    <div style="display: flex; gap: 8px;">
                      <button class="tag edit-plan-btn" data-plan-id="${plan.id}" style="background: var(--accent-light); color: var(--accent); padding: 6px 12px; font-size: 12px; border: none; border-radius: 6px; cursor: pointer;">
                        Editar
                      </button>
                      <button class="tag delete-plan-btn" data-plan-id="${plan.id}" style="background: #fee; color: #c33; padding: 6px 12px; font-size: 12px; border: none; border-radius: 6px; cursor: pointer;">
                        Excluir
                      </button>
                    </div>
                  </div>
                  
                  <div style="margin-bottom: 16px;">
                    <p style="margin: 0 0 8px 0; font-size: 13px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px;">
                      Links e Materiais
                    </p>
                    <div style="background: #f9fbff; border-radius: 8px; padding: 12px;">
                      ${linksHtml}
                    </div>
                  </div>
                  
                  ${plan.goals
                    ? `
                    <div>
                      <p style="margin: 0 0 8px 0; font-size: 13px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px;">
                        Objetivos (GOALS)
                      </p>
                      <p style="margin: 0; color: var(--text-primary); line-height: 1.6;">
                        ${plan.goals}
                      </p>
                    </div>
                  `
                    : '<p style="color: var(--text-muted); font-size: 14px; font-style: italic;">Nenhum objetivo definido</p>'}
                </div>
              `;
            })
            .join("")}
        </div>
      `;
    })
    .join("");

  // Anexa event listeners aos botões de editar e excluir
  container.querySelectorAll(".edit-plan-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const planId = parseInt(btn.dataset.planId);
      openPlanForm(planId);
    });
  });

  container.querySelectorAll(".delete-plan-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const planId = parseInt(btn.dataset.planId);
      deletePlan(planId);
    });
  });
}

let planningUIInitialized = false;

function initPlanningUI() {
  // Evita inicializar múltiplas vezes
  if (planningUIInitialized) return;
  planningUIInitialized = true;

  // Popula filtro de alunos
  const studentFilter = document.getElementById("planStudentFilter");
  if (studentFilter) {
    studentFilter.innerHTML = '<option value="">Todos os alunos</option>';
    if (state.students && state.students.length > 0) {
      state.students
        .filter((s) => s.active !== false)
        .forEach((student) => {
          const option = document.createElement("option");
          option.value = student.id;
          option.textContent = student.name;
          studentFilter.appendChild(option);
        });
    }

    studentFilter.addEventListener("change", async (e) => {
      const studentId = e.target.value;
      if (studentId) {
        await loadLessonPlans(studentId);
      } else {
        await loadLessonPlans();
      }
      renderPlanning();
    });
  }

  // Popula select do formulário
  const planStudentSelect = document.getElementById("planStudent");
  if (planStudentSelect) {
    planStudentSelect.innerHTML = '<option value="">Selecione um aluno</option>';
    if (state.students && state.students.length > 0) {
      state.students
        .filter((s) => s.active !== false)
        .forEach((student) => {
          const option = document.createElement("option");
          option.value = student.id;
          option.textContent = student.name;
          planStudentSelect.appendChild(option);
        });
    }
  }

  // Botão novo planejamento
  const newPlanBtn = document.getElementById("newPlanBtn");
  if (newPlanBtn) {
    newPlanBtn.addEventListener("click", () => openPlanForm(null));
  }

  // Botão cancelar formulário
  const cancelPlanBtn = document.getElementById("cancelPlanForm");
  if (cancelPlanBtn) {
    cancelPlanBtn.addEventListener("click", closePlanForm);
  }

  // Submit do formulário
  const planForm = document.getElementById("planForm");
  if (planForm) {
    planForm.addEventListener("submit", onPlanFormSubmit);
  }
}

function openPlanForm(planId = null) {
  editingPlanId = planId;
  const formCard = document.getElementById("planFormCard");
  const titleEl = document.getElementById("planFormTitle");
  const form = document.getElementById("planForm");

  if (!formCard || !form || !titleEl) return;

  if (planId) {
    const plan = state.lessonPlans.find((p) => p.id === planId);
    if (plan) {
      titleEl.textContent = "Editar Planejamento";
      form.planStudent.value = plan.studentId;
      form.planDate.value = plan.date;
      form.planLinks.value = plan.links;
      form.planGoals.value = plan.goals;
    }
  } else {
    titleEl.textContent = "Novo Planejamento";
    form.reset();
  }

  formCard.style.display = "flex";
  window.scrollTo({ top: formCard.offsetTop - 80, behavior: "smooth" });
}

function closePlanForm() {
  const formCard = document.getElementById("planFormCard");
  if (formCard) {
    formCard.style.display = "none";
  }
  editingPlanId = null;
}

async function onPlanFormSubmit(event) {
  event.preventDefault();
  const form = event.target;

  const payload = {
    student: parseInt(form.planStudent.value),
    date: form.planDate.value,
    links: form.planLinks.value.trim(),
    goals: form.planGoals.value.trim(),
  };

  if (!payload.student || !payload.date) {
    alert("Preencha o aluno e a data da aula.");
    return;
  }

  try {
    if (editingPlanId) {
      await fetchJSON(`/lesson-plans/${editingPlanId}/`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
    } else {
      await fetchJSON("/lesson-plans/", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    }

    await loadLessonPlans();
    renderPlanning();
    closePlanForm();
  } catch (error) {
    console.error(error);
    alert(error.message || "Não foi possível salvar o planejamento.");
  }
}

async function deletePlan(planId) {
  const plan = state.lessonPlans.find((p) => p.id === planId);
  if (!plan) return;

  const ok = confirm(
    `Tem certeza que deseja excluir o planejamento de ${plan.studentName} para ${new Date(plan.date).toLocaleDateString("pt-BR")}?`
  );
  if (!ok) return;

  try {
    await fetchJSON(`/lesson-plans/${planId}/`, {
      method: "DELETE",
    });

    await loadLessonPlans();
    renderPlanning();
  } catch (error) {
    console.error(error);
    alert("Não foi possível excluir o planejamento.");
  }
}

