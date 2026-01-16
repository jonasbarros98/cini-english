// ==========================
// Configuração e estado
// ==========================

const API_BASE_URL = "/api";

const state = {
  today: new Date(),
  currentMonth: new Date(),
  selectedDate: null,
  notes: {},     // { 'YYYY-MM-DD': [ { id, status, title, info, studentId, studentName } ] }
  students: [],  // vindo da API
  tasks: [],     // vindo da API
  finances: [],   // <--- NOVO: lista de cobranças do mês
};

let editingLessonId = null;
let editingTaskId = null;


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
  const tasks = await fetchJSON("/tasks/");
  state.tasks = tasks.map((t) => ({
    id: t.id,
    title: t.title,
    status: t.status,               // 'todo', 'doing', 'done'
    date: t.date || null,           // "2026-01-05"
    dueDate: t.due_date || null,    // "2026-01-10"
    notes: t.notes || "",
  }));
}

function resetTaskForm(task = null) {
  const titleInput = document.getElementById("taskTitle");
  const dateInput = document.getElementById("taskDate");
  const dueInput = document.getElementById("taskDue");
  const statusSelect = document.getElementById("taskStatus");
  const notesInput = document.getElementById("taskNotes");

  if (!titleInput || !dateInput || !dueInput || !statusSelect || !notesInput) {
    return;
  }

  if (task) {
    titleInput.value = task.title || "";
    dateInput.value = task.date || "";
    dueInput.value = task.dueDate || "";
    statusSelect.value = task.status || "todo";
    notesInput.value = task.notes || "";
  } else {
    titleInput.value = "";
    dateInput.value = "";
    dueInput.value = "";
    statusSelect.value = "todo";
    notesInput.value = "";
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


async function loadInitialData() {
  await Promise.all([loadStudents(), loadTasks(), loadLessonsForCurrentMonth(), loadFinancesForCurrentMonth()]);
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
    loadFinancesForCurrentMonth(),   // <--- NOVO
  ]);

  renderCalendar();
  renderDayDetails();
  renderStats();
  renderFinance();                    // <--- NOVO
  renderFinanceTotal();
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
      <div class="form-row" style="display:flex; gap:8px; flex-wrap:wrap;">
        <button type="submit" class="primary">Salvar aluno</button>
        <button type="button" class="primary ghost" id="cancelStudentForm">Cancelar</button>
      </div>
    </form>
 `;

  const form = card.querySelector("#studentForm");
  const cancelBtn = card.querySelector("#cancelStudentForm");

  form.addEventListener("submit", onStudentFormSubmit);
  cancelBtn.addEventListener("click", () => hideStudentForm());

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
  } else {
    titleEl.textContent = "Novo aluno";
    form.reset();
    form.studentLessonsTotal.value = "";
    form.studentLessonsDone.value = "";
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

  const payload = {
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

  if (!payload.name) {
    alert("Informe o nome do aluno.");
    return;
  }

  // 1) API: PATCH / POST
  try {
    if (editingStudentId) {
      await fetchJSON(`/students/${editingStudentId}/`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
    } else {
      await fetchJSON("/students/", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    }
  } catch (error) {
    console.error(error);
    alert(error.message || "Não foi possível salvar o aluno na API.");
    return; // não tenta atualizar tela se a API falhou
  }

  // 2) Atualizar tela (se der erro aqui, a gente avisa diferente)
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

function renderTasks() {
  const list = document.getElementById("taskList");
  if (!list) return;

  list.innerHTML = "";

  state.tasks.forEach((task) => {
    const card = document.createElement("div");
    card.className = "task-card";

    // header: título + status
    const header = document.createElement("div");
    header.className = "task-header";

    const titleEl = document.createElement("strong");
    titleEl.textContent = task.title;

    const statusBadge = document.createElement("span");
    statusBadge.className = `pill task-status-badge ${task.status}`;
    let statusLabel = "A fazer";
    if (task.status === "doing") statusLabel = "Fazendo";
    if (task.status === "done") statusLabel = "Concluída";
    statusBadge.textContent = statusLabel;

    header.append(titleEl, statusBadge);

    // linha de datas
    const datesRow = document.createElement("p");
    datesRow.className = "muted task-dates";

    const parts = [];
    if (task.date) {
      parts.push(`Data: ${task.date}`);
    }
    if (task.dueDate) {
      parts.push(`Vencimento: ${task.dueDate}`);
    }
    datesRow.textContent = parts.join("  •  ");

    // notas
    const notesEl = document.createElement("p");
    notesEl.className = "muted";
    notesEl.textContent = task.notes || "";

    // ações
    const actions = document.createElement("div");
    actions.className = "task-actions";

    // botão editar
    const editBtn = document.createElement("button");
    editBtn.type = "button";
    editBtn.className = "tag";
    editBtn.textContent = "Editar";
    editBtn.addEventListener("click", () => {
      editingTaskId = task.id;
      resetTaskForm(task);
      const formCard = document.getElementById("taskFormCard");
      if (formCard) formCard.classList.remove("hidden");
    });

    // botão excluir
    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.className = "tag danger";
    deleteBtn.textContent = "Excluir";
    deleteBtn.addEventListener("click", async () => {
      if (!confirm("Tem certeza que deseja excluir esta tarefa?")) return;
      try {
        await fetchJSON(`/tasks/${task.id}/`, {
          method: "DELETE",
        });
        await loadTasks();
        renderTasks();
      } catch (error) {
        console.error(error);
        alert("Não foi possível excluir a tarefa.");
      }
    });

    // botões de status rápido
    ["todo", "doing", "done"].forEach((st) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "tag";
      let label = "A fazer";
      if (st === "doing") label = "Fazendo";
      if (st === "done") label = "Concluída";
      btn.textContent = label;

      btn.addEventListener("click", async () => {
        try {
          await fetchJSON(`/tasks/${task.id}/`, {
            method: "PATCH",
            body: JSON.stringify({ status: st }),
          });
          task.status = st;
          renderTasks();
        } catch (error) {
          console.error(error);
          alert("Não foi possível atualizar o status.");
        }
      });

      actions.append(btn);
    });

    actions.append(editBtn, deleteBtn);

    card.append(header, datesRow, notesEl, actions);
    list.append(card);
  });
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

// antes: usava prompt
// async function addTask() { ... }

function addTask() {
  // só abre o modal já preparado pra criação
  openTaskFormToCreate();
}



// ==========================
// Navegação e formulários
// ==========================

function showView(viewId) {
  document.querySelectorAll(".view").forEach((view) => {
    view.classList.toggle("active", view.id === viewId);
  });
  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.view === viewId);
  });
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
  renderTasks();
  renderBillingPreview();
  renderFinance();  // <--- NOVO
  renderFinanceTotal();   // 👈 AQUI

  state.selectedDate = toISO(state.today);
  renderDayDetails();


  initTasksUI();
  showView("view-calendar");
}

document.addEventListener("DOMContentLoaded", () => {
  init().catch((err) => console.error(err));
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

function initTasksUI() {
  const formCard = document.getElementById("taskFormCard");
  const newBtn = document.getElementById("newTaskBtn");
  const saveBtn = document.getElementById("saveTaskBtn");
  const cancelBtn = document.getElementById("cancelTaskBtn");

  // Se não tiver esses elementos na tela, não faz nada
  if (!formCard || !newBtn) {
    console.warn("UI de tarefas não encontrada no DOM.");
    return;
  }

  const titleInput = document.getElementById("taskTitle");
  const dateInput = document.getElementById("taskDate");
  const dueInput = document.getElementById("taskDue");
  const statusInput = document.getElementById("taskStatus");
  const notesInput = document.getElementById("taskNotes");

  function resetForm() {
    if (titleInput) titleInput.value = "";
    if (dateInput) dateInput.value = "";
    if (dueInput) dueInput.value = "";
    if (statusInput) statusInput.value = "todo";
    if (notesInput) notesInput.value = "";
  }

  // Abrir formulário
  newBtn.onclick = () => {
    resetForm();
    formCard.classList.remove("hidden");
    if (titleInput) titleInput.focus();
  };

  // Cancelar (fechar formulário)
  if (cancelBtn) {
    cancelBtn.onclick = () => {
      formCard.classList.add("hidden");
    };
  }

  // Salvar tarefa
  if (saveBtn) {
    saveBtn.onclick = async () => {
      if (!titleInput) return;

      const payload = {
        title: titleInput.value.trim(),
        date: dateInput ? dateInput.value || null : null,
        due: dueInput ? dueInput.value || null : null,
        status: statusInput ? statusInput.value : "todo",
        notes: notesInput ? notesInput.value.trim() : "",
      };

      if (!payload.title) {
        alert("Informe um título para a tarefa.");
        return;
      }

      try {
        const resp = await fetch("/api/tasks/", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        if (!resp.ok) {
          console.error("Erro na resposta da API de tarefas:", resp.status);
          throw new Error("Erro ao salvar tarefa");
        }

        const newTask = await resp.json();

        // Garante que state.tasks existe
        if (!Array.isArray(state.tasks)) {
          state.tasks = [];
        }

        state.tasks.push(newTask);
        renderTasks();
        formCard.classList.add("hidden");
      } catch (err) {
        console.error(err);
        alert("Não foi possível salvar a tarefa. Verifique a API e tente novamente.");
      }
    };
  }
}

