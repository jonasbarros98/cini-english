// ==========================
// Configuração e estado
// ==========================

const API_BASE_URL = "/api";

const state = {
  today: new Date(),
  currentMonth: new Date(),
  financeViewMonth: new Date(), // Mês atual da visualização financeira (pode ser diferente do calendário)
  selectedDate: null,
  notes: {},     // { 'YYYY-MM-DD': [ { id, status, title, info, studentId, studentName, time } ] }
  students: [],  // vindo da API
  tasks: [],     // vindo da API
  finances: [],   // lista de cobranças do mês
  financialEntries: [], // lançamentos financeiros a receber
  currentUser: null,
  users: [],
  lessonPlans: [],
  calendarView: "month",       // 'month' | 'week'
  currentWeekStart: null,      // Date (domingo da semana exibida); definido ao mudar para semana
};

let editingLessonId = null;
let editingTaskId = null;
let editingFinancialEntryId = null;
let editingUserId = null;


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
    email: s.email || "",
    status: s.status || "active",
    plan: s.plan_name,
    planStartDate: s.plan_start_date || null,
    progress: {
      done: s.lessons_done,
      total: s.lessons_total,
    },
    defaultDueDay: s.default_due_day || null,
    preferredPaymentMethod: s.preferred_payment_method || "",
    pix: s.pix_key || "",
    active: s.status === "active", // Mantém compatibilidade com código antigo
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
    const key = lesson.date;
    if (!state.notes[key]) state.notes[key] = [];
    state.notes[key].push({
      id: lesson.id,
      status: lesson.status,
      title: lesson.title,
      info: lesson.info,
      studentId: lesson.student,
      studentName: lesson.student_name,
      time: lesson.time,
      realized: lesson.realized || false,
    });
  });
  // Atualizar sidebar após carregar aulas
  updateSidebarStats();
}

function toDateKey(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function getWeekStart(d) {
  const x = new Date(d);
  x.setHours(0, 0, 0, 0);
  const day = x.getDay();
  const diff = x.getDate() - day;
  x.setDate(diff);
  return x;
}

async function loadLessonsForWeek(weekStart) {
  const sun = new Date(weekStart);
  sun.setHours(0, 0, 0, 0);
  const sat = new Date(sun);
  sat.setDate(sat.getDate() + 6);
  const startStr = toDateKey(sun);
  const endStr = toDateKey(sat);
  const lessons = await fetchJSON(`/lessons/?start=${startStr}&end=${endStr}`);

  state.notes = {};
  lessons.forEach((lesson) => {
    const key = lesson.date;
    if (!state.notes[key]) state.notes[key] = [];
    state.notes[key].push({
      id: lesson.id,
      status: lesson.status,
      title: lesson.title,
      info: lesson.info,
      studentId: lesson.student,
      studentName: lesson.student_name,
      time: lesson.time,
      realized: lesson.realized || false,
    });
  });
  // Atualizar sidebar após carregar aulas
  updateSidebarStats();
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
      userId: e.user,
      userDisplayName: e.user_display_name || e.user_username || "",
      beneficiaryUserId: e.beneficiary_user,
      beneficiaryUsername: e.beneficiary_username,
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
  // Atualizar sidebar após carregar dados iniciais
  updateSidebarStats();
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

  // NÃO atualizar sidebar aqui - usar updateSidebarStats() que busca de /api/dashboard/summary/
  // A sidebar deve sempre mostrar os dados do dashboard, não do mês atual do calendário
}

// ==========================
// Atualizar Visão Rápida (Sidebar) - Baseado no Calendário
// ==========================

function updateSidebarStats() {
  // Contar do calendário (state.notes)
  let confirmed = 0;
  let pending = 0;
  let realized = 0;
  
  // Data atual para filtrar pendências do mês
  const now = new Date();
  const currentMonth = now.getMonth();
  const currentYear = now.getFullYear();
  
  // Iterar sobre todas as datas e suas notas
  Object.keys(state.notes).forEach((dateKey) => {
    // Verificar se a data está no mês atual
    const [year, month, day] = dateKey.split('-').map(Number);
    const isCurrentMonth = year === currentYear && (month - 1) === currentMonth;
    
    const noteList = state.notes[dateKey];
    noteList.forEach((note) => {
      const isRealized = note.realized === true || note.realized === "true";
      
      // Aulas confirmadas: status === "confirmed" e não realizadas
      if (note.status === "confirmed" && !isRealized) {
        confirmed += 1;
      }
      // Pendências: status === "pending" e não realizadas, do mês atual
      if (note.status === "pending" && !isRealized && isCurrentMonth) {
        pending += 1;
      }
      // Realizadas: realized === true
      if (isRealized) {
        realized += 1;
      }
    });
  });
  
  // Atualizar elementos da sidebar
  const sidebarConfirmed = document.getElementById('sidebarConfirmed');
  const sidebarPending = document.getElementById('sidebarPending');
  const sidebarStudents = document.getElementById('sidebarStudents');
  const sidebarRealized = document.getElementById('sidebarRealized');
  
  if (sidebarConfirmed) sidebarConfirmed.textContent = confirmed;
  if (sidebarPending) sidebarPending.textContent = pending;
  if (sidebarRealized) sidebarRealized.textContent = realized;
  
  // Buscar alunos ativos do dashboard (mantém como está)
  fetch('/api/dashboard/summary/', {
    credentials: 'same-origin',
  })
    .then(response => {
      if (!response.ok) return;
      return response.json();
    })
    .then(data => {
      if (data && data.kpis) {
        if (sidebarStudents) sidebarStudents.textContent = data.kpis.active_students || 0;
        // Atualizar também com dados do calendário do backend (para sincronização)
        if (sidebarConfirmed) sidebarConfirmed.textContent = data.kpis.calendar_confirmed || confirmed;
        if (sidebarPending) sidebarPending.textContent = data.kpis.calendar_pending_month || pending;
        if (sidebarRealized) sidebarRealized.textContent = data.kpis.calendar_realized || realized;
      }
    })
    .catch(error => {
      console.error('Erro ao buscar alunos ativos:', error);
    });
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
  updateCalendarNavTitle();
}

function getWeekStartForState() {
  if (state.currentWeekStart) return new Date(state.currentWeekStart);
  return getWeekStart(new Date());
}

async function changeWeek(delta) {
  const start = getWeekStartForState();
  start.setDate(start.getDate() + 7 * delta);
  state.currentWeekStart = start;
  await loadLessonsForWeek(state.currentWeekStart);
  renderCalendar();
  renderDayDetails();
  renderStats();
  updateCalendarNavTitle();
}

async function goToToday() {
  const today = new Date();
  state.currentMonth = new Date(today.getFullYear(), today.getMonth(), 1);
  state.currentWeekStart = getWeekStart(today);
  if (state.calendarView === "month") {
    await Promise.all([
      loadLessonsForCurrentMonth(),
      loadFinancesForCurrentMonth(),
      loadFinancialEntries(),
    ]);
  } else {
    await loadLessonsForWeek(state.currentWeekStart);
  }
  state.selectedDate = toDateKey(today);
  renderCalendar();
  renderDayDetails();
  renderStats();
  renderFinance();
  renderFinanceTotal();
  renderFinancialEntries();
  renderFinancialStats();
  updateCalendarNavTitle();
}

function updateCalendarNavTitle() {
  const el = document.getElementById("calendarNavTitle");
  const hint = document.getElementById("calendarHint");
  if (!el) return;
  if (state.calendarView === "month") {
    const label = monthName(state.currentMonth);
    el.textContent = label.charAt(0).toUpperCase() + label.slice(1);
    if (hint) hint.textContent = "Clique em um dia para ver e editar os agendamentos.";
  } else {
    const start = getWeekStartForState();
    const end = new Date(start);
    end.setDate(end.getDate() + 6);
    const fmt = (d) => d.toLocaleDateString("pt-BR", { day: "numeric", month: "short" });
    el.textContent = `${fmt(start)} – ${fmt(end)} ${end.getFullYear()}`;
    if (hint) hint.textContent = "Clique em um horário ou evento para ver detalhes.";
  }
}


function renderCalendar() {
  const monthWrap = document.getElementById("calendarMonthWrap");
  const weekWrap = document.getElementById("calendarWeekWrap");
  const monthTitleEl = document.getElementById("monthTitle");

  if (state.calendarView === "week") {
    if (monthWrap) monthWrap.style.display = "none";
    if (weekWrap) weekWrap.style.display = "block";
    updateCalendarNavTitle();
    if (monthTitleEl) {
      const start = getWeekStartForState();
      const end = new Date(start);
      end.setDate(end.getDate() + 6);
      const fmt = (d) => d.toLocaleDateString("pt-BR", { day: "numeric", month: "long" });
      monthTitleEl.textContent = `${fmt(start)} – ${fmt(end)} ${end.getFullYear()}`;
    }
    renderCalendarWeek();
    return;
  }

  if (monthWrap) monthWrap.style.display = "block";
  if (weekWrap) weekWrap.style.display = "none";
  updateCalendarNavTitle();

  const grid = document.getElementById("calendarGrid");
  if (!grid) return;
  grid.innerHTML = "";

  const year = state.currentMonth.getFullYear();
  const month = state.currentMonth.getMonth();
  const label = monthName(state.currentMonth);

  if (monthTitleEl) monthTitleEl.textContent = label.charAt(0).toUpperCase() + label.slice(1);

  const today = new Date();
  const firstOfMonth = new Date(year, month, 1);
  const firstWeekday = firstOfMonth.getDay();
  const gridStart = new Date(firstOfMonth);
  gridStart.setDate(gridStart.getDate() - firstWeekday);

  const MONTH_MAX_ROWS = 6;
  const cellsTotal = 7 * MONTH_MAX_ROWS;

  for (let i = 0; i < cellsTotal; i++) {
    const d = new Date(gridStart);
    d.setDate(d.getDate() + i);
    const day = d.getDate();
    // chave de data SEM usar Date/toISOString => sem “dia anterior”
    const key = toDateKey(d);
    const isThisMonth = d.getMonth() === month && d.getFullYear() === year;
    const isToday =
      d.getDate() === today.getDate() &&
      d.getMonth() === today.getMonth() &&
      d.getFullYear() === today.getFullYear();
    const isPast = d < today && !isToday;

    const notes = state.notes[key] || [];
    const visibleNotes = notes.slice(0, 4);
    const moreCount = notes.length > 4 ? notes.length - 4 : 0;
    const dayEl = document.createElement("button");
    dayEl.type = "button";
    dayEl.className = "day month-day";
    if (!isThisMonth) dayEl.classList.add("other-month");
    if (state.selectedDate === key) dayEl.classList.add("selected");
    if (isToday) dayEl.classList.add("today");
    if (isPast) dayEl.classList.add("past");

    const dateWrap = document.createElement("div");
    dateWrap.className = "day-date-wrap";
    const dateEl = document.createElement("span");
    dateEl.className = "day-date";
    dateEl.textContent = String(d.getDate());
    dateWrap.append(dateEl);

    const eventsEl = document.createElement("div");
    eventsEl.className = "day-events";

    visibleNotes.forEach((note) => {
      const row = document.createElement("div");
      let className = `day-event ${note.status || "pending"}`;
      // Adiciona classe "realized" se a aula foi realizada
      if (note.realized === true || note.realized === "true") {
        className += " realized";
      }
      row.className = className;
      const timeStr = note.time ? note.time.slice(0, 5) : "";
      row.innerHTML = `
        <span class="day-event-dot"></span>
        <span class="day-event-time">${timeStr}</span>
        <span class="day-event-title">${(note.title || "Aula").replace(/</g, "&lt;")}</span>
      `;
      eventsEl.append(row);
    });

    if (moreCount > 0) {
      const more = document.createElement("div");
      more.className = "day-event-more";
      more.textContent = `+${moreCount} mais`;
      eventsEl.append(more);
    }

    dayEl.append(dateWrap, eventsEl);
    dayEl.addEventListener("click", () => {
      if (!isThisMonth) {
        state.currentMonth = new Date(d.getFullYear(), d.getMonth(), 1);
        loadLessonsForCurrentMonth().then(() => {
          state.selectedDate = key;
          renderCalendar();
          renderDayDetails();
          updateCalendarNavTitle();
        });
      } else {
        selectDay(key);
      }
    });
    grid.append(dayEl);
  }
}

const HOUR_START = 6;
const HOUR_END = 23;
const WEEKDAY_NAMES = ["DOM", "SEG", "TER", "QUA", "QUI", "SEX", "SÁB"];

function renderCalendarWeek() {
  const headerEl = document.getElementById("calendarWeekHeader");
  const timesEl = document.getElementById("calendarWeekTimes");
  const gridEl = document.getElementById("calendarWeekGrid");
  if (!headerEl || !timesEl || !gridEl) return;

  const start = getWeekStartForState();
  headerEl.innerHTML = "";
  timesEl.innerHTML = "";
  gridEl.innerHTML = "";

  // Cabeçalho: coluna vazia (hora) + 7 dias
  const emptyHead = document.createElement("div");
  emptyHead.className = "week-head-empty";
  headerEl.append(emptyHead);

  for (let i = 0; i < 7; i++) {
    const d = new Date(start);
    d.setDate(d.getDate() + i);
    const key = toDateKey(d);
    const today = new Date();
    const isToday =
      d.getDate() === today.getDate() &&
      d.getMonth() === today.getMonth() &&
      d.getFullYear() === today.getFullYear();

    const col = document.createElement("div");
    col.className = "week-head-day";
    if (isToday) col.classList.add("today");
    col.innerHTML = `
      <span class="week-head-name">${WEEKDAY_NAMES[i]}</span>
      <span class="week-head-date">${d.getDate()}</span>
    `;
    col.addEventListener("click", () => {
      state.selectedDate = key;
      renderDayDetails();
      document.querySelectorAll(".week-head-day").forEach((el) => el.classList.remove("selected"));
      if (col) col.classList.add("selected");
    });
    if (state.selectedDate === key) col.classList.add("selected");
    headerEl.append(col);
  }

  // Coluna de horas
  for (let h = HOUR_START; h < HOUR_END; h++) {
    const row = document.createElement("div");
    row.className = "week-time-row";
    row.textContent = `${String(h).padStart(2, "0")}:00`;
    timesEl.append(row);
  }

  const rows = HOUR_END - HOUR_START;
  for (let r = 0; r < rows; r++) {
    const slotHour = HOUR_START + r;
    for (let c = 0; c < 7; c++) {
      const cell = document.createElement("div");
      cell.className = "week-slot";
      const d = new Date(start);
      d.setDate(d.getDate() + c);
      const key = toDateKey(d);
      const cellNotes = (state.notes[key] || []).filter((n) => {
        if (!n.time) return false;
        const [hh] = n.time.split(":");
        return parseInt(hh, 10) === slotHour;
      });

      cell.addEventListener("click", () => {
        state.selectedDate = key;
        renderDayDetails();
        document.querySelectorAll(".week-head-day").forEach((el) => el.classList.remove("selected"));
        const headDay = headerEl.children[c + 1];
        if (headDay) headDay.classList.add("selected");
      });

      cellNotes.forEach((note) => {
        const ev = document.createElement("div");
        let className = `week-event ${note.status || "pending"}`;
        // Adiciona classe "realized" se a aula foi realizada
        if (note.realized === true || note.realized === "true") {
          className += " realized";
        }
        ev.className = className;
        ev.innerHTML = `
          <span class="week-event-time">${(note.time || "").slice(0, 5)}</span>
          <span class="week-event-title">${note.title || "Aula"}</span>
        `;
        ev.addEventListener("click", (e) => {
          e.stopPropagation();
          state.selectedDate = key;
          renderDayDetails();
          document.querySelectorAll(".week-head-day").forEach((el) => el.classList.remove("selected"));
          const dayCol = headerEl.querySelectorAll(".week-head-day")[c];
          if (dayCol) dayCol.classList.add("selected");
          startEditLesson(note);
        });
        cell.append(ev);
      });
      gridEl.append(cell);
    }
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
  document.getElementById("noteStatus").value = note.status || "pending";
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
  // Garantir que o status padrão seja "pending" após reset
  const statusSelect = document.getElementById("noteStatus");
  if (statusSelect) {
    statusSelect.value = "pending";
  }
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
    // Se a aula foi realizada, mostra "Realizado" no badge
    if (note.realized === true || note.realized === "true") {
      badge.className = "pill status realized";
      badge.textContent = "Realizado";
    } else {
      badge.className = `pill status ${note.status}`;
      badge.textContent = lessonStatusLabels[note.status] || "Status";
    }

    header.append(title, badge);

    const info = document.createElement("p");
    info.className = "muted";
    info.textContent = note.info || "Sem observações.";

    const actions = document.createElement("div");
    actions.className = "note-actions";

    const isRealized = note.realized === true || note.realized === "true";

    // STATUS BUTTONS
    ["confirmed", "pending", "canceled"].forEach((status) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "tag";
      button.textContent = lessonStatusLabels[status];
      if (isRealized) {
        button.disabled = true;
        button.classList.add("disabled");
        button.title = "Aula realizada - não é possível alterar o status";
      } else {
        button.addEventListener("click", () => {
          updateLessonStatus(note, status);
        });
      }
      actions.append(button);
    });

    // REALIZED BUTTON
    const realizedBtn = document.createElement("button");
    realizedBtn.type = "button";
    if (isRealized) {
      realizedBtn.className = "tag realized";
      realizedBtn.textContent = "✓ Realizado";
      realizedBtn.title = "Clique para marcar como não realizado";
    } else {
      realizedBtn.className = "tag";
      realizedBtn.textContent = "Realizado";
      realizedBtn.title = "Clique para marcar como realizado";
    }
    realizedBtn.addEventListener("click", () => {
      toggleLessonRealized(note);
    });
    actions.append(realizedBtn);

    // EDIT BUTTON
    const editBtn = document.createElement("button");
    editBtn.type = "button";
    editBtn.className = "tag";
    editBtn.textContent = "Editar";
    if (isRealized) {
      editBtn.disabled = true;
      editBtn.classList.add("disabled");
      editBtn.title = "Aula realizada - não é possível editar";
    } else {
      editBtn.addEventListener("click", () => startEditLesson(note));
    }
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

    if (state.calendarView === "week") {
      await loadLessonsForWeek(getWeekStartForState());
    } else {
      await loadLessonsForCurrentMonth();
    }
    renderStats();
    renderCalendar();
    renderDayDetails();
    updateSidebarStats(); // Atualizar sidebar após deletar aula
  } catch (error) {
    console.error(error);
    alert("Não foi possível excluir a aula.");
  }
}


async function toggleLessonRealized(note) {
  try {
    const newRealized = !(note.realized || false);
    
    // Feedback visual imediato (otimista)
    const response = await fetchJSON(`/lessons/${note.id}/`, {
      method: "PATCH",
      body: JSON.stringify({ realized: newRealized }),
    });
    
    // Atualizar no state com os dados retornados do servidor
    const notes = state.notes[state.selectedDate] || [];
    const noteIndex = notes.findIndex((n) => n.id === note.id);
    if (noteIndex !== -1) {
      notes[noteIndex].realized = response.realized || newRealized;
    }
    
    // Recarregar dados para garantir sincronização completa
    if (state.calendarView === "week") {
      await loadLessonsForWeek(getWeekStartForState());
    } else {
      await loadLessonsForCurrentMonth();
    }
    renderStats();
    renderCalendar();
    renderDayDetails();
    updateSidebarStats(); // Atualizar sidebar após marcar como realizado
    
    // Log para debug (pode remover em produção)
    console.log(`Aula ${note.id} marcada como ${newRealized ? 'realizada' : 'não realizada'} - Salvo no banco de dados`);
  } catch (error) {
    console.error("Erro ao atualizar status de realizado:", error);
    alert("Erro ao atualizar status de realizado. Tente novamente.");
  }
}

async function updateLessonStatus(note, newStatus) {
  try {
    await fetchJSON(`/lessons/${note.id}/`, {
      method: "PATCH",
      body: JSON.stringify({ status: newStatus }),
    });
    note.status = newStatus;
    if (state.calendarView === "week") {
      await loadLessonsForWeek(getWeekStartForState());
    } else {
      await loadLessonsForCurrentMonth();
    }
    renderStats();
    renderCalendar();
    renderDayDetails();
    updateSidebarStats(); // Atualizar sidebar após mudar status
  } catch (error) {
    console.error(error);
    alert("Não foi possível atualizar o status da aula.");
  }
}


// ==========================
// Alunos (lista + tela de cadastro/edição)
// ==========================

// getFilteredStudents() removido - agora em /alunos/

// renderStudents() removido - agora em /alunos/
// Mantendo apenas funções auxiliares usadas em outras partes


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

// Funções de formulário de alunos removidas - agora em /alunos/
// Mantendo apenas funções auxiliares usadas em outras partes

// Função removida - não usada mais
function _removed_ensureStudentFormCard() {
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
      <!-- IDENTIDADE -->
      <div style="margin-bottom: 24px;">
        <h4 style="margin-bottom: 16px; color: var(--text); font-size: 16px; font-weight: 600;">Identidade</h4>
        <div class="form-row">
          <label for="studentName">Nome completo <span style="color: #c33;">*</span></label>
          <input id="studentName" name="studentName" type="text" required />
        </div>
        <div class="form-row">
          <label for="studentGuardians">Responsável</label>
          <input id="studentGuardians" name="studentGuardians" type="text" placeholder="Pai/mãe ou 'Responsável próprio'" />
        </div>
        <div class="form-row">
          <label for="studentPhone">Telefone</label>
          <input id="studentPhone" name="studentPhone" type="text" />
        </div>
        <div class="form-row">
          <label for="studentAddress">Endereço</label>
          <input id="studentAddress" name="studentAddress" type="text" placeholder="Endereço / cidade" />
        </div>
        <div class="form-row">
          <label for="studentEmail">E-mail</label>
          <input id="studentEmail" name="studentEmail" type="email" />
        </div>
      </div>

      <!-- PLANO -->
      <div style="margin-bottom: 24px; padding-top: 24px; border-top: 1px solid var(--border);">
        <h4 style="margin-bottom: 16px; color: var(--text); font-size: 16px; font-weight: 600;">Plano</h4>
        <div class="form-row">
          <label for="studentStatus">Status do aluno <span style="color: #c33;">*</span></label>
          <select id="studentStatus" name="studentStatus" required>
            <option value="active">Ativo</option>
            <option value="paused">Pausado</option>
            <option value="ended">Encerrado</option>
          </select>
        </div>
        <div class="form-row">
          <label for="studentPlan">Plano atual</label>
          <input id="studentPlan" name="studentPlan" type="text" placeholder="Ex.: Intensivo - 8 aulas" />
        </div>
        <div class="form-row">
          <label for="studentPlanStartDate">Data de início</label>
          <input id="studentPlanStartDate" name="studentPlanStartDate" type="date" />
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
        <div class="form-row grid-two">
          <div>
            <label for="studentDefaultDueDay">Dia de vencimento padrão</label>
            <input id="studentDefaultDueDay" name="studentDefaultDueDay" type="number" min="1" max="28" placeholder="1 a 28" />
          </div>
          <div>
            <label for="studentPreferredPaymentMethod">Forma de pagamento preferida</label>
            <select id="studentPreferredPaymentMethod" name="studentPreferredPaymentMethod">
              <option value="">Selecione...</option>
              <option value="pix">PIX</option>
              <option value="card">Cartão</option>
              <option value="cash">Dinheiro</option>
              <option value="transfer">Transferência</option>
            </select>
          </div>
        </div>
      </div>

      <!-- FINANCEIRO -->
      <div style="margin-bottom: 24px; padding-top: 24px; border-top: 1px solid var(--border);">
        <h4 style="margin-bottom: 16px; color: var(--text); font-size: 16px; font-weight: 600;">Financeiro</h4>
        <div class="form-row">
          <label for="studentPix">Chave Pix</label>
          <input id="studentPix" name="studentPix" type="text" />
        </div>
        <div class="form-row">
          <label for="studentContractPdf">Contrato PDF</label>
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
    form.studentEmail.value = student.email || "";
    form.studentStatus.value = student.status || "active";
    form.studentPlan.value = student.plan || "";
    form.studentPlanStartDate.value = student.planStartDate ? student.planStartDate.split("T")[0] : "";
    form.studentLessonsTotal.value = student.progress.total || 0;
    form.studentLessonsDone.value = student.progress.done || 0;
    form.studentDefaultDueDay.value = student.defaultDueDay || "";
    form.studentPreferredPaymentMethod.value = student.preferredPaymentMethod || "";
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
    form.studentStatus.value = "active"; // Valor padrão
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
      body: JSON.stringify({ status: "ended" }),
    });

    await loadStudents();
    populateNoteStudentSelect();
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
    formData.append("email", form.studentEmail.value.trim());
    formData.append("status", form.studentStatus.value || "active");
    formData.append("plan_name", form.studentPlan.value.trim());
    if (form.studentPlanStartDate.value) {
      formData.append("plan_start_date", form.studentPlanStartDate.value);
    }
    formData.append("lessons_total", Number(form.studentLessonsTotal.value || 0));
    formData.append("lessons_done", Number(form.studentLessonsDone.value || 0));
    if (form.studentDefaultDueDay.value) {
      formData.append("default_due_day", Number(form.studentDefaultDueDay.value));
    }
    if (form.studentPreferredPaymentMethod.value) {
      formData.append("preferred_payment_method", form.studentPreferredPaymentMethod.value);
    }
    formData.append("pix_key", form.studentPix.value.trim());

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
      email: form.studentEmail.value.trim(),
      status: form.studentStatus.value || "active",
      plan_name: form.studentPlan.value.trim(),
      plan_start_date: form.studentPlanStartDate.value || null,
      lessons_total: Number(form.studentLessonsTotal.value || 0),
      lessons_done: Number(form.studentLessonsDone.value || 0),
      default_due_day: form.studentDefaultDueDay.value ? Number(form.studentDefaultDueDay.value) : null,
      preferred_payment_method: form.studentPreferredPaymentMethod.value || "",
      pix_key: form.studentPix.value.trim(),
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
    populateNoteStudentSelect();
    // Redireciona para /alunos/ se estiver na página de alunos
    if (window.location.pathname.includes('/alunos/')) {
      window.location.reload();
    }
  } catch (error) {
    console.error(error);
    alert("Aluno salvo, mas houve erro ao atualizar a tela. Recarregue a página.");
  }
}

// ==========================
// Cobrança - Nova Implementação
// ==========================

let currentBillingData = null;
let currentMessageTemplate = null;

// Carrega lançamentos financeiros pendentes/vencidos para o seletor
// Popula o filtro de alunos na tela de cobrança
function populateBillingStudentFilter() {
  const select = document.getElementById("billingStudentFilter");
  if (!select) return;

  // Limpa o select mantendo a opção "Todos os alunos"
  select.innerHTML = '<option value="">Todos os alunos</option>';

  // Popula com os alunos disponíveis
  if (state.students && state.students.length > 0) {
    // Ordena alunos por nome
    const sortedStudents = [...state.students].sort((a, b) => 
      a.name.localeCompare(b.name)
    );

    sortedStudents.forEach(student => {
      const option = document.createElement("option");
      option.value = student.id;
      option.textContent = student.name;
      select.appendChild(option);
    });
  }
}

async function loadBillingEntries() {
  const select = document.getElementById("billingEntrySelect");
  if (!select) return;

  // Obtém os valores dos filtros
  const studentFilter = document.getElementById("billingStudentFilter")?.value || "";
  const monthFilter = document.getElementById("billingMonthFilter")?.value || "";

  try {
    // Monta a URL com os filtros (sem status, pois vamos buscar pendentes e vencidos)
    const params = new URLSearchParams();
    if (studentFilter) {
      params.append("student", studentFilter);
    }
    if (monthFilter) {
      // Converte formato YYYY-MM para o formato esperado pelo backend
      params.append("month", monthFilter);
    }

    // Faz duas requisições: uma para pendentes e outra para vencidos
    const paramsPending = new URLSearchParams(params);
    paramsPending.append("status", "pending");
    
    const paramsOverdue = new URLSearchParams(params);
    paramsOverdue.append("status", "overdue");

    const [entriesPending, entriesOverdue] = await Promise.all([
      fetchJSON(`/financial-entries/?${paramsPending.toString()}`),
      fetchJSON(`/financial-entries/?${paramsOverdue.toString()}`)
    ]);
    
    // Combina os resultados e remove duplicatas
    const allEntries = [...entriesPending, ...entriesOverdue];
    const uniqueEntries = Array.from(
      new Map(allEntries.map(entry => [entry.id, entry])).values()
    );
    
    // Ordena por data de vencimento (mais próximos primeiro)
    const filteredEntries = uniqueEntries.sort((a, b) => {
      if (!a.due_date && !b.due_date) return 0;
      if (!a.due_date) return 1;
      if (!b.due_date) return -1;
      return new Date(a.due_date) - new Date(b.due_date);
    });
    
    select.innerHTML = '<option value="">Selecione um lançamento financeiro...</option>';
    
    if (filteredEntries.length === 0) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = "Nenhum lançamento encontrado com os filtros selecionados";
      option.disabled = true;
      select.appendChild(option);
      return;
    }
    
    filteredEntries.forEach(entry => {
      const option = document.createElement("option");
      option.value = entry.id;
      const dueDate = entry.due_date ? formatDateBR(entry.due_date) : "Sem vencimento";
      const status = entry.status === "overdue" ? "🔴 Vencido" : entry.status === "pending" ? "🟡 Pendente" : "";
      option.textContent = `${entry.student_name} - ${formatBRL(entry.amount)} - Venc: ${dueDate} ${status}`;
      select.appendChild(option);
    });
  } catch (error) {
    console.error("Erro ao carregar lançamentos financeiros:", error);
    select.innerHTML = '<option value="">Erro ao carregar lançamentos...</option>';
  }
}

// Carrega dados de cobrança baseado no lançamento selecionado
async function loadBillingData(entryId) {
  if (!entryId) {
    document.getElementById("billingContent").style.display = "none";
    return;
  }

  try {
    const data = await fetchJSON(`/financial-entries/${entryId}/billing_data/`);
    currentBillingData = data;
    
    renderBillingHeader(data);
    renderBillingSummary(data);
    renderBillingOrigin(data);
    renderBillingHistory(data);
    
    // Seleciona modelo padrão baseado no status
    if (data.status.text === "Vencido") {
      selectBillingTemplate("overdue");
    } else if (data.status.text === "Vence hoje") {
      selectBillingTemplate("due_today");
    } else {
      selectBillingTemplate("friendly");
    }
    
    document.getElementById("billingContent").style.display = "block";
  } catch (error) {
    console.error("Erro ao carregar dados de cobrança:", error);
    alert("Não foi possível carregar os dados de cobrança.");
  }
}

// Renderiza cabeçalho contextual
function renderBillingHeader(data) {
  const studentNameEl = document.getElementById("billingStudentName");
  const contextInfoEl = document.getElementById("billingContextInfo");
  const metaChips = document.getElementById("billingMetaChips");
  const metaStatusText = document.getElementById("metaStatusText");
  const metaDueText = document.getElementById("metaDueText");
  const metaInstallmentText = document.getElementById("metaInstallmentText");
  const metaDot = metaChips ? metaChips.querySelector(".meta-dot") : null;
  
  if (studentNameEl) {
    studentNameEl.textContent = `Cobrança • ${data.student.name}`;
  }
  
  if (contextInfoEl) {
    const planText = data.student.plan_name || "Plano não informado";
    contextInfoEl.textContent = planText;
  }

  // Preenche meta chips no header
  if (metaChips) {
    metaChips.setAttribute("aria-hidden", "false");
  }
  
  if (metaStatusText) {
    metaStatusText.textContent = data.status.text;
  }

  if (metaDueText) {
    const dueDate = data.entry.due_date ? formatDateBR(data.entry.due_date) : "—";
    metaDueText.textContent = dueDate;
  }

  if (metaInstallmentText) {
    const installmentText = data.entry.installments > 1 
      ? `${data.entry.current_installment}/${data.entry.installments}`
      : "À vista";
    metaInstallmentText.textContent = installmentText;
  }

  // Atualiza cor do dot baseado no status
  if (metaDot) {
    metaDot.className = "meta-dot";
    if (data.status.color === "🟢") {
      metaDot.classList.add("ok");
    } else if (data.status.color === "🔴") {
      metaDot.classList.add("bad");
    }
  }
}

// Renderiza card principal de resumo financeiro
function renderBillingSummary(data) {
  // Preenche apenas os spans específicos, não injeta HTML
  const amountValue = document.getElementById("billingAmountValue");
  const dueValue = document.getElementById("billingDueValue");
  const progressValue = document.getElementById("billingProgressValue");
  const installmentValue = document.getElementById("billingInstallmentValue");
  const statusText = document.getElementById("billingStatusText");
  const statusPill = document.getElementById("billingStatusPill");
  const statusDot = document.getElementById("billingStatusDot");

  if (amountValue) {
    amountValue.textContent = formatBRL(data.entry.amount).replace("R$ ", "");
  }

  if (dueValue) {
    dueValue.textContent = data.entry.due_date ? formatDateBR(data.entry.due_date) : "—";
  }

  if (progressValue) {
    progressValue.textContent = `${data.student.lessons_done}/${data.student.lessons_total}`;
  }

  if (installmentValue) {
    const installmentText = data.entry.installments > 1 
      ? `${data.entry.current_installment}/${data.entry.installments}`
      : "À vista";
    installmentValue.textContent = installmentText;
  }

  if (statusText) {
    statusText.textContent = data.status.text;
  }

  // Atualiza classes e cor do status
  if (statusPill) {
    statusPill.className = "billing-status";
    if (data.status.color === "🟢") {
      statusPill.classList.add("ok");
    } else if (data.status.color === "🔴") {
      statusPill.classList.add("bad");
    }
  }
}

// Renderiza card de origem da cobrança
function renderBillingOrigin(data) {
  const originReference = document.getElementById("originReference");
  const originDesc = document.getElementById("originDesc");
  const originCreatedAt = document.getElementById("originCreatedAt");
  const originPaymentMethod = document.getElementById("originPaymentMethod");

  if (originReference) {
    // Período de referência = data de vencimento
    originReference.textContent = data.entry.due_date ? formatDateBR(data.entry.due_date) : "—";
  }

  if (originDesc) {
    originDesc.textContent = data.entry.description || "Mensalidade";
  }

  if (originCreatedAt) {
    const entryDate = data.entry.issue_date ? formatDateBR(data.entry.issue_date) : "—";
    originCreatedAt.textContent = entryDate;
  }

  if (originPaymentMethod) {
    const paymentMethodLabels = {
      "pix": "PIX",
      "card": "Cartão",
      "cash": "Dinheiro",
      "transfer": "Transferência",
      "other": "Outro",
    };
    const method = paymentMethodLabels[data.entry.payment_method] || data.entry.payment_method || "—";
    originPaymentMethod.textContent = method;
  }
}

// Gera mensagem baseada no template selecionado
function generateBillingMessage(template, data) {
  const studentName = data.student.name.split(" ")[0]; // Primeiro nome
  const amount = formatBRL(data.entry.amount);
  const dueDate = data.entry.due_date ? formatDateBR(data.entry.due_date) : "data não informada";
  const pixKey = data.student.pix_key || "Informar no contato";
  const progress = `${data.student.lessons_done}/${data.student.lessons_total}`;
  const planName = data.student.plan_name || "seu plano";
  
  // Formata informação da parcela
  const installmentText = data.entry.installments > 1 
    ? `Parcela: ${data.entry.current_installment}/${data.entry.installments}`
    : "Parcela: À vista";

  const templates = {
    friendly: `Olá ${studentName}! 😊

Este é um lembrete referente ao seu ${planName}, com vencimento em ${dueDate}.

Valor: ${amount}
${installmentText}
Progresso: ${progress} aulas
Chave Pix: ${pixKey}

Qualquer dúvida, fico à disposição!`,

    due_today: `Olá ${studentName}! 🟡

Lembrando que o vencimento do seu ${planName} é hoje (${dueDate}).

Valor: ${amount}
${installmentText}
Progresso: ${progress} aulas
Chave Pix: ${pixKey}

Fico aguardando o pagamento. Obrigada!`,

    overdue: `Olá ${studentName}! 🔴

Lembro que o pagamento referente ao seu ${planName} está em atraso.

Valor: ${amount}
${installmentText}
Vencimento: ${dueDate}
Progresso: ${progress} aulas
Chave Pix: ${pixKey}

Por favor, regularize o quanto antes. Qualquer dúvida, estou à disposição!`,

    thank_you: `Olá ${studentName}! 🙏

Agradeço pelo pagamento referente ao seu ${planName}.

Valor: ${amount}
${installmentText}
Progresso: ${progress} aulas

Fico feliz em ter você como aluno(a)! Qualquer dúvida, estou à disposição.`
  };

  return templates[template] || templates.friendly;
}

// Seleciona template de mensagem
function selectBillingTemplate(template) {
  currentMessageTemplate = template;
  
  // Atualiza botões usando a classe "active"
  document.querySelectorAll(".billing-template-btn").forEach(btn => {
    if (btn.dataset.template === template) {
      btn.classList.add("active");
    } else {
      btn.classList.remove("active");
    }
  });
  
  // Gera mensagem
  if (currentBillingData) {
    const message = generateBillingMessage(template, currentBillingData);
    const messageEl = document.getElementById("billingMessage");
    if (messageEl) {
      messageEl.value = message;
    }
  }
}

// Abre WhatsApp
function openBillingWhatsApp() {
  if (!currentBillingData || !currentBillingData.student.phone) {
    alert("Telefone do aluno não cadastrado.");
    return;
  }

  const messageEl = document.getElementById("billingMessage");
  const message = messageEl ? messageEl.value.trim() : "";

  if (!message) {
    alert("A mensagem está vazia.");
    return;
  }

  let phoneDigits = currentBillingData.student.phone.replace(/\D/g, "");
  if (phoneDigits.length <= 11) {
    phoneDigits = "55" + phoneDigits;
  }

  const url = `https://wa.me/${phoneDigits}?text=${encodeURIComponent(message)}`;
  window.open(url, "_blank");
}

// Copia mensagem
async function copyBillingMessage() {
  const messageEl = document.getElementById("billingMessage");
  const message = messageEl ? messageEl.value.trim() : "";

  if (!message) {
    alert("A mensagem está vazia.");
    return;
  }

  try {
    await navigator.clipboard.writeText(message);
    alert("Mensagem copiada para a área de transferência!");
  } catch (error) {
    alert("Não foi possível copiar automaticamente. Selecione o texto manualmente.");
  }
}

// Marca como enviada
async function markBillingAsSent() {
  if (!currentBillingData || !currentMessageTemplate) {
    alert("Selecione um template de mensagem primeiro.");
    return;
  }

  const messageEl = document.getElementById("billingMessage");
  const message = messageEl ? messageEl.value.trim() : "";

  if (!message) {
    alert("A mensagem está vazia.");
    return;
  }

  try {
    await fetchJSON("/billing-logs/", {
      method: "POST",
      body: JSON.stringify({
        financial_entry: currentBillingData.entry.id,
        message_type: currentMessageTemplate,
        send_method: "whatsapp",
        message_content: message,
      }),
    });

    alert("Cobrança registrada com sucesso!");
    
    // Recarrega histórico
    if (currentBillingData) {
      await loadBillingData(currentBillingData.entry.id);
    }
  } catch (error) {
    console.error("Erro ao registrar cobrança:", error);
    alert("Não foi possível registrar a cobrança.");
  }
}

// Renderiza histórico de cobranças
function renderBillingHistory(data) {
  const historyList = document.getElementById("billingHistoryList");
  if (!historyList) return;

  if (!data.billing_logs || data.billing_logs.length === 0) {
    historyList.innerHTML = '<p class="muted" style="text-align: center; padding: 24px;">Nenhuma cobrança registrada ainda.</p>';
    return;
  }

  // Formata data e hora para o formato brasileiro
  function formatDateTime(datetimeString) {
    const date = new Date(datetimeString);
    const day = String(date.getDate()).padStart(2, "0");
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const year = date.getFullYear();
    const hours = String(date.getHours()).padStart(2, "0");
    const minutes = String(date.getMinutes()).padStart(2, "0");
    return `${day}/${month}/${year} ${hours}:${minutes}`;
  }

  historyList.innerHTML = data.billing_logs.map(log => `
    <div class="history-item">
      <div>
        <strong>${log.send_method_display} • ${log.message_type_display}</strong>
        <span>${formatDateTime(log.sent_at)} • por ${log.user_username}</span>
      </div>
      <span class="history-tag">Enviado</span>
    </div>
  `).join("");
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
    const isPartnerTeacher = state.currentUser && state.currentUser.user_profile === "prof_parceiro";
    empty.textContent = isPartnerTeacher 
      ? "Nenhum lançamento financeiro para este mês."
      : "Nenhum lançamento financeiro para este mês. Clique em '+ Novo Lançamento' para criar.";
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
    let nameHtml = `<strong>${entry.studentName || "Aluno"}</strong> - ${entry.description}`;
    if (entry.userDisplayName) {
      nameHtml += `<div class="finance-teacher" style="font-size:11px;color:var(--muted);margin-top:2px;">👤 ${entry.userDisplayName}</div>`;
    }
    nameEl.innerHTML = nameHtml;

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

    // Verifica se é Prof. Parceiro (não pode editar/criar)
    const isPartnerTeacher = state.currentUser && state.currentUser.user_profile === "prof_parceiro";

    if (!isPartnerTeacher) {
      // Botões de status (apenas para não Prof. Parceiro)
      ["paid", "pending", "overdue"].forEach((statusKey) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "tag";
        btn.textContent = financialEntryStatusLabels[statusKey];
        btn.addEventListener("click", () => updateFinancialEntryStatus(entry, statusKey));
        actions.append(btn);
      });

      // Botão Cobrar (apenas para lançamentos pendentes ou vencidos)
      if (entry.status === "pending" || entry.status === "overdue") {
        const chargeBtn = document.createElement("button");
        chargeBtn.type = "button";
        chargeBtn.className = "tag";
        chargeBtn.style.background = "var(--accent, #2f7cff)";
        chargeBtn.style.color = "#fff";
        chargeBtn.textContent = "💬 Cobrar";
        chargeBtn.addEventListener("click", () => openBillingForEntry(entry));
        actions.append(chargeBtn);
      }

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
    } else {
      // Prof. Parceiro só pode visualizar
      const viewOnly = document.createElement("span");
      viewOnly.className = "muted";
      viewOnly.textContent = "Somente leitura";
      viewOnly.style.fontSize = "12px";
      actions.append(viewOnly);
    }

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
    const feUser = document.getElementById("feUser");
    if (feUser && entry.userId) feUser.value = String(entry.userId);
    document.getElementById("feDescription").value = entry.description || "";
    document.getElementById("feAmount").value = entry.amount || "";
    document.getElementById("feInstallments").value = entry.installments || 1;
    // Data do Registro: sempre atual (não editável)
    const feIssueDate = document.getElementById("feIssueDate");
    if (feIssueDate) {
      feIssueDate.value = toISO(new Date());
      feIssueDate.readOnly = true;
    }
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

    // Data do Registro = sempre hoje (não editável)
    const feIssueDate = document.getElementById("feIssueDate");
    if (feIssueDate) {
      feIssueDate.value = toISO(new Date());
      feIssueDate.readOnly = true;
    }

    // Data de vencimento = dia 5 do próximo mês
    const nextMonth = new Date();
    nextMonth.setMonth(nextMonth.getMonth() + 1);
    nextMonth.setDate(5);
    const feDueDate = document.getElementById("feDueDate");
    if (feDueDate) {
      feDueDate.value = toISO(nextMonth);
    }

    const feUser = document.getElementById("feUser");
    if (feUser && state.currentUser) feUser.value = String(state.currentUser.id);

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
  // Função helper para criar data local a partir de string YYYY-MM-DD
  function parseDateLocal(dateString) {
    const [year, month, day] = dateString.split("-").map(Number);
    return new Date(year, month - 1, day); // month - 1 porque janeiro = 0
  }

  // Função helper para formatar data como YYYY-MM-DD
  function formatDateLocal(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  }

  // Data do registro: sempre a data atual (hoje)
  const today = new Date();
  const todayStr = formatDateLocal(today);

  // Data base de vencimento (vencimento da 1ª parcela)
  const baseDueDate = parseDateLocal(basePayload.due_date);

  // Cria todas as parcelas (1, 2, 3, ...)
  for (let i = 1; i <= totalInstallments; i++) {
    const installmentPayload = { ...basePayload };
    installmentPayload.current_installment = i;

    // Data de vencimento: adiciona (i - 1) meses à data base da 1ª parcela
    // Exemplo: 1ª parcela vence 05/02/2026, 2ª vence 05/03/2026, 3ª vence 05/04/2026
    const dueDate = new Date(baseDueDate);
    dueDate.setMonth(dueDate.getMonth() + (i - 1));

    // Data do registro: sempre a data atual (não muda entre parcelas)
    installmentPayload.issue_date = todayStr;
    installmentPayload.due_date = formatDateLocal(dueDate);

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

  // Esconde menu de Tarefas e Cobrança para Prof. Parceiro
  const isPartnerTeacher = state.currentUser && state.currentUser.user_profile === "prof_parceiro";
  const navTasks = document.querySelector('[data-view="view-tasks"]');
  if (navTasks) navTasks.style.display = isPartnerTeacher ? "none" : "";
  const navBilling = document.querySelector('[data-view="view-billing"]');
  if (navBilling) navBilling.style.display = isPartnerTeacher ? "none" : "flex";

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
  
  // Visualização de alunos removida - agora em /alunos/
  
  // Se abrir a visualização de cobrança
  if (viewId === "view-billing") {
    try {
      // Popula o filtro de alunos
      populateBillingStudentFilter();
      // Carrega os lançamentos com os filtros aplicados
      await loadBillingEntries();
    } catch (error) {
      console.error("Erro ao carregar dados de cobrança:", error);
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

  // Sempre atualizar sidebar ao mudar de view
  updateSidebarStats();

  window.scrollTo({ top: 0, behavior: "smooth" });
}

// Abre a tela de cobrança com um lançamento específico pré-selecionado
async function openBillingForEntry(entry) {
  // Primeiro, muda para a view de cobrança
  await showView("view-billing");
  
  // Aguarda um pouco para garantir que os elementos estão renderizados
  await new Promise(resolve => setTimeout(resolve, 100));
  
  // Configura os filtros baseado no lançamento
  const billingStudentFilter = document.getElementById("billingStudentFilter");
  const billingMonthFilter = document.getElementById("billingMonthFilter");
  const billingEntrySelect = document.getElementById("billingEntrySelect");
  
  if (!billingEntrySelect) {
    console.error("Elemento billingEntrySelect não encontrado");
    return;
  }
  
  // Configura o filtro de aluno
  if (billingStudentFilter && entry.studentId) {
    billingStudentFilter.value = entry.studentId;
  }
  
  // Configura o filtro de mês baseado na data de vencimento
  if (billingMonthFilter && entry.dueDate) {
    const dueDate = new Date(entry.dueDate);
    const year = dueDate.getFullYear();
    const month = String(dueDate.getMonth() + 1).padStart(2, "0");
    billingMonthFilter.value = `${year}-${month}`;
  }
  
  // Carrega os lançamentos com os filtros aplicados
  await loadBillingEntries();
  
  // Seleciona o lançamento no dropdown
  if (billingEntrySelect) {
    billingEntrySelect.value = entry.id;
    
    // Dispara o evento change para carregar os dados
    const changeEvent = new Event("change", { bubbles: true });
    billingEntrySelect.dispatchEvent(changeEvent);
    
    // Também chama diretamente a função de carregamento caso o evento não funcione
    setTimeout(async () => {
      await loadBillingData(entry.id);
    }, 200);
  }
  
  // Scroll para o topo
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

    // Buscar o valor atual de realized se estiver editando
    let currentRealized = false;
    if (editingLessonId) {
      const notes = state.notes[state.selectedDate] || [];
      const currentNote = notes.find((n) => n.id === editingLessonId);
      if (currentNote) {
        currentRealized = currentNote.realized || false;
      }
    }

    const payload = {
      student: Number(studentId),
      date: state.selectedDate,
      time: timeValue || null,
      title,
      info,
      status,
      realized: editingLessonId ? currentRealized : false, // Mantém o valor atual ao editar, inicia como false ao criar
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
      if (state.calendarView === "week") {
        await loadLessonsForWeek(getWeekStartForState());
      } else {
        await loadLessonsForCurrentMonth();
      }
      renderStats();
      renderCalendar();
      renderDayDetails();
      updateSidebarStats(); // Atualizar sidebar após criar/editar aula
    } catch (error) {
      console.error(error);
      alert("Não foi possível salvar a aula.");
    }
  });

  // cobrança - nova implementação
  const billingEntrySelect = document.getElementById("billingEntrySelect");
  if (billingEntrySelect) {
    billingEntrySelect.addEventListener("change", async (e) => {
      const entryId = e.target.value;
      if (entryId) {
        await loadBillingData(entryId);
      } else {
        document.getElementById("billingContent").style.display = "none";
      }
    });
  }

  // Filtros de cobrança
  const billingStudentFilter = document.getElementById("billingStudentFilter");
  if (billingStudentFilter) {
    // Popula o select de alunos
    populateBillingStudentFilter();
    
    // Listener para recarregar quando o filtro mudar
    billingStudentFilter.addEventListener("change", async () => {
      await loadBillingEntries();
      // Limpa a seleção atual se existir
      if (billingEntrySelect) {
        billingEntrySelect.value = "";
        document.getElementById("billingContent").style.display = "none";
      }
    });
  }

  const billingMonthFilter = document.getElementById("billingMonthFilter");
  if (billingMonthFilter) {
    // Define o mês atual como padrão (se ainda não estiver definido)
    if (!billingMonthFilter.value) {
      const today = new Date();
      const year = today.getFullYear();
      const month = String(today.getMonth() + 1).padStart(2, "0");
      billingMonthFilter.value = `${year}-${month}`;
    }
    
    // Listener para recarregar quando o filtro mudar
    billingMonthFilter.addEventListener("change", async () => {
      await loadBillingEntries();
      // Limpa a seleção atual se existir
      if (billingEntrySelect) {
        billingEntrySelect.value = "";
        document.getElementById("billingContent").style.display = "none";
      }
    });
  }

  // Botões de template
  document.querySelectorAll(".billing-template-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      selectBillingTemplate(btn.dataset.template);
    });
  });

  // Ações de cobrança
  const billingOpenWhatsApp = document.getElementById("billingOpenWhatsApp");
  if (billingOpenWhatsApp) {
    billingOpenWhatsApp.addEventListener("click", openBillingWhatsApp);
  }

  const billingCopyMessage = document.getElementById("billingCopyMessage");
  if (billingCopyMessage) {
    billingCopyMessage.addEventListener("click", copyBillingMessage);
  }

  const billingMarkSent = document.getElementById("billingMarkSent");
  if (billingMarkSent) {
    billingMarkSent.addEventListener("click", markBillingAsSent);
  }

  // Toggle histórico
  const billingHistoryToggle = document.getElementById("billingHistoryToggle");
  if (billingHistoryToggle) {
    billingHistoryToggle.addEventListener("click", () => {
      const historyContent = document.getElementById("billingHistoryContent");
      const isVisible = historyContent.style.display !== "none";
      historyContent.style.display = isVisible ? "none" : "block";
      billingHistoryToggle.textContent = isVisible ? "🕒 Mostrar histórico" : "🕒 Ocultar histórico";
    });
  }

  // Botão reset template
  const billingResetTemplate = document.getElementById("billingResetTemplate");
  if (billingResetTemplate) {
    billingResetTemplate.addEventListener("click", () => {
      if (currentMessageTemplate && currentBillingData) {
        const message = generateBillingMessage(currentMessageTemplate, currentBillingData);
        const messageEl = document.getElementById("billingMessage");
        if (messageEl) {
          messageEl.value = message;
        }
      }
    });
  }

  // Calendário: Hoje, anterior, próximo
  const calendarTodayBtn = document.getElementById("calendarToday");
  if (calendarTodayBtn) {
    calendarTodayBtn.addEventListener("click", () => goToToday().catch((err) => console.error(err)));
  }
  const calendarPrevBtn = document.getElementById("calendarPrev");
  if (calendarPrevBtn) {
    calendarPrevBtn.addEventListener("click", () => {
      if (state.calendarView === "week") {
        changeWeek(-1).catch((err) => console.error(err));
      } else {
        changeMonth(-1).catch((err) => console.error(err));
      }
    });
  }
  const calendarNextBtn = document.getElementById("calendarNext");
  if (calendarNextBtn) {
    calendarNextBtn.addEventListener("click", () => {
      if (state.calendarView === "week") {
        changeWeek(1).catch((err) => console.error(err));
      } else {
        changeMonth(1).catch((err) => console.error(err));
      }
    });
  }

  // Calendário: toggle Mensal / Semanal
  const viewMonthBtn = document.getElementById("viewMonthBtn");
  const viewWeekBtn = document.getElementById("viewWeekBtn");
  if (viewMonthBtn) {
    viewMonthBtn.addEventListener("click", async () => {
      if (state.calendarView === "month") return;
      state.calendarView = "month";
      viewMonthBtn.classList.add("active");
      if (viewWeekBtn) viewWeekBtn.classList.remove("active");
      await Promise.all([
        loadLessonsForCurrentMonth(),
        loadFinancesForCurrentMonth(),
        loadFinancialEntries(),
      ]);
      renderCalendar();
      renderDayDetails();
      renderStats();
      updateCalendarNavTitle();
    });
  }
  if (viewWeekBtn) {
    viewWeekBtn.addEventListener("click", async () => {
      if (state.calendarView === "week") return;
      state.calendarView = "week";
      viewWeekBtn.classList.add("active");
      if (viewMonthBtn) viewMonthBtn.classList.remove("active");
      if (!state.currentWeekStart) state.currentWeekStart = getWeekStart(new Date());
      await loadLessonsForWeek(state.currentWeekStart);
      renderCalendar();
      renderDayDetails();
      renderStats();
      updateCalendarNavTitle();
    });
  }

  // botão atalho "Novo agendamento" na sidebar
  document.getElementById("createLessonBtn").addEventListener("click", () => {
    const todayKey = toISO(state.today);
    selectDay(todayKey);
    document.getElementById("noteTitle").focus();
  });

  // alunos
  // Event listener de addStudent removido - agora em /alunos/
  const addStudentBtn = document.getElementById("addStudent");
  if (addStudentBtn) {
    // Botão não existe mais no index.html, mas mantendo compatibilidade
    addStudentBtn.addEventListener("click", () => {
      window.location.href = "/alunos/";
    });
  }


  // Botão de novo lançamento financeiro
  const newFinancialEntryBtn = document.getElementById("newFinancialEntryBtn");
  if (newFinancialEntryBtn) {
    // Esconde/desabilita para Prof. Parceiro
    if (state.currentUser && state.currentUser.user_profile === "prof_parceiro") {
      newFinancialEntryBtn.style.display = "none";
    } else {
      newFinancialEntryBtn.addEventListener("click", () => {
        openFinancialEntryForm(null);
      });
    }
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
      // Data do Registro: sempre a data atual (automática)
      const issueDate = toISO(new Date());
      const dueDate = document.getElementById("feDueDate")?.value;
      const status = document.getElementById("feStatus")?.value || "pending";
      const paymentMethod = document.getElementById("fePaymentMethod")?.value || "pix";
      const notes = document.getElementById("feNotes")?.value.trim() || "";

      if (!studentId || !description || !amount || !dueDate) {
        alert("Preencha todos os campos obrigatórios.");
        return;
      }

      const userId = document.getElementById("feUser")?.value;
      
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
      
      // Professor responsável: define quem é responsável e quem recebe (um único campo)
      if (userId) payload.user = Number(userId);

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

  // renderStudents() removido - agora em /alunos/
  // Mas ainda precisamos popular selects que dependem de alunos
  populateNoteStudentSelect();
  populateBillingStudentFilter();
  
  renderStats();
  renderCalendar();
  renderFinance();
  renderFinanceTotal();
  renderFinancialEntries();
  renderFinancialStats();

  state.selectedDate = toISO(state.today);
  renderDayDetails();

  // Verificar se estamos na rota do dashboard
  if (window.location.pathname === '/dashboard/') {
    // Não fazer nada, deixar o dashboard_home.html gerenciar
    return;
  }

  // Verificar se há parâmetro de view na URL
  const urlParams = new URLSearchParams(window.location.search);
  const viewParam = urlParams.get('view');
  
  if (viewParam) {
    // Se houver parâmetro, mostrar a view especificada
    showView(viewParam);
  } else {
    // Caso contrário, mostrar calendário por padrão
    showView("view-calendar");
  }
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
    const profileLabel = user.user_profile === "prof_parceiro" ? "Prof. Parceiro" : "Professor";
    const row = document.createElement("div");
    row.className = "student-row";
    row.innerHTML = `
      <div class="student-main">
        <div class="student-name">
          <strong>${user.username}</strong>
          ${user.is_admin ? '<span class="tag" style="margin-left: 8px;">Admin</span>' : ''}
          <span class="tag" style="margin-left: 8px; background: #e0e7ff; color: #4338ca;">${profileLabel}</span>
          <span class="tag" style="margin-left: 8px; background: #f3f4f6; color: #6b7280; font-size: 11px;">ID: ${user.id}</span>
        </div>
        <div class="student-info">
          <div style="margin-bottom: 4px;"><strong>Código:</strong> ${user.id}</div>${user.email || "Sem email"} • ${user.is_active ? "Ativo" : "Inativo"}
          ${user.partner_teachers && user.partner_teachers.length > 0 ? 
            ` • ${user.partner_teachers.length} parceiro(s)` : ''}
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

async function loadPartnerTeachers() {
  // Carrega apenas professores parceiros para o select
  try {
    const users = await fetchJSON("/users/");
    return users.filter(u => u.user_profile === "prof_parceiro");
  } catch (error) {
    console.error("Erro ao carregar professores parceiros:", error);
    return [];
  }
}

function updatePartnerTeachersSelect() {
  const profileSelect = document.getElementById("uUserProfile");
  const partnerTeachersRow = document.getElementById("partnerTeachersRow");
  const partnerTeachersSelect = document.getElementById("uPartnerTeachers");

  if (!profileSelect || !partnerTeachersRow || !partnerTeachersSelect) return;

  // Mostra o campo apenas se o perfil for "Professor"
  if (profileSelect.value === "professor") {
    partnerTeachersRow.style.display = "flex";
    // Carrega e popula professores parceiros
    loadPartnerTeachers().then(partners => {
      // Remove todas as opções exceto "Nenhum selecionado"
      partnerTeachersSelect.innerHTML = '<option value="">Nenhum selecionado</option>';
      partners.forEach(partner => {
        const option = document.createElement("option");
        option.value = partner.id;
        option.textContent = `${partner.username}${partner.email ? ` (${partner.email})` : ''}`;
        partnerTeachersSelect.appendChild(option);
      });
    });
  } else {
    partnerTeachersRow.style.display = "none";
    partnerTeachersSelect.value = "";
  }
}

async function openUserForm(userId = null) {
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

    // Mostrar e preencher campo de ID
    const userIdRow = document.getElementById("userIdRow");
    const userIdInput = document.getElementById("uUserId");
    if (userIdRow && userIdInput) {
      userIdRow.style.display = "block";
      userIdInput.value = user.id || "";
    }

    document.getElementById("uUsername").value = user.username || "";
    document.getElementById("uEmail").value = user.email || "";
    document.getElementById("uFirstName").value = user.first_name || "";
    document.getElementById("uLastName").value = user.last_name || "";
    document.getElementById("uUserProfile").value = user.user_profile || "professor";
    document.getElementById("uIsAdmin").checked = user.is_admin || false;
    document.getElementById("uIsActive").checked = user.is_active !== false;
    document.getElementById("uPassword").value = "";
    document.getElementById("uPassword").required = false;
    // Oculta campo de confirmação de senha ao editar
    const passwordConfirmRow = document.getElementById("passwordConfirmRow");
    if (passwordConfirmRow) {
      passwordConfirmRow.style.display = "none";
      document.getElementById("uPasswordConfirm").value = "";
      document.getElementById("uPasswordConfirm").required = false;
    }

    // Atualiza select de professores parceiros
    await updatePartnerTeachersSelect();
    
    // Seleciona professores parceiros vinculados
    const partnerTeachersSelect = document.getElementById("uPartnerTeachers");
    if (partnerTeachersSelect && user.partner_teachers) {
      // Limpa seleção anterior
      Array.from(partnerTeachersSelect.options).forEach(opt => opt.selected = false);
      // Seleciona os parceiros vinculados
      user.partner_teachers.forEach(partner => {
        const option = Array.from(partnerTeachersSelect.options).find(
          opt => parseInt(opt.value) === partner.id
        );
        if (option) option.selected = true;
      });
    }
  } else {
    editingUserId = null;
    titleEl.textContent = "Novo Usuário";
    form.reset();
    
    // Ocultar campo de ID para novo usuário
    const userIdRow = document.getElementById("userIdRow");
    if (userIdRow) {
      userIdRow.style.display = "none";
    }
    
    document.getElementById("uPassword").required = true;
    document.getElementById("uUserProfile").value = "professor";
    // Mostra campo de confirmação de senha para novos usuários
    const passwordConfirmRow = document.getElementById("passwordConfirmRow");
    if (passwordConfirmRow) {
      passwordConfirmRow.style.display = "flex";
      document.getElementById("uPasswordConfirm").required = true;
    }
    await updatePartnerTeachersSelect();
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
  
  // Oculta campo de ID ao fechar
  const userIdRow = document.getElementById("userIdRow");
  if (userIdRow) {
    userIdRow.style.display = "none";
  }
  
  // Oculta o campo de professores parceiros ao fechar
  const partnerTeachersRow = document.getElementById("partnerTeachersRow");
  if (partnerTeachersRow) {
    partnerTeachersRow.style.display = "none";
  }
  
  // Oculta campo de confirmação de senha e limpa erros
  const passwordConfirmRow = document.getElementById("passwordConfirmRow");
  if (passwordConfirmRow) {
    passwordConfirmRow.style.display = "none";
  }
  const passwordMatchError = document.getElementById("passwordMatchError");
  if (passwordMatchError) {
    passwordMatchError.style.display = "none";
  }
  const passwordConfirmInput = document.getElementById("uPasswordConfirm");
  if (passwordConfirmInput) {
    passwordConfirmInput.value = "";
    passwordConfirmInput.style.borderColor = "";
  }
}

async function onUserFormSubmit(event) {
  event.preventDefault();

  const username = document.getElementById("uUsername")?.value.trim();
  const email = document.getElementById("uEmail")?.value.trim();
  const firstName = document.getElementById("uFirstName")?.value.trim();
  const lastName = document.getElementById("uLastName")?.value.trim();
  const password = document.getElementById("uPassword")?.value;
  const passwordConfirm = document.getElementById("uPasswordConfirm")?.value;
  const userProfile = document.getElementById("uUserProfile")?.value;
  const isAdmin = document.getElementById("uIsAdmin")?.checked || false;
  const isActive = document.getElementById("uIsActive")?.checked !== false;

  if (!username) {
    alert("Username é obrigatório.");
    return;
  }

  if (!userProfile) {
    alert("Perfil de usuário é obrigatório.");
    return;
  }

  if (!editingUserId && !password) {
    alert("Senha é obrigatória para novos usuários.");
    return;
  }

  // Validar confirmação de senha para novos usuários
  if (!editingUserId && password && password !== passwordConfirm) {
    const passwordMatchError = document.getElementById("passwordMatchError");
    const passwordConfirmInput = document.getElementById("uPasswordConfirm");
    if (passwordMatchError) {
      passwordMatchError.style.display = "block";
    }
    if (passwordConfirmInput) {
      passwordConfirmInput.style.borderColor = "#dc2626";
    }
    alert("As senhas não coincidem. Por favor, verifique e tente novamente.");
    return;
  }

  // Coleta IDs dos professores parceiros selecionados
  const partnerTeachersSelect = document.getElementById("uPartnerTeachers");
  const partnerTeachersIds = [];
  if (partnerTeachersSelect && userProfile === "professor") {
    Array.from(partnerTeachersSelect.selectedOptions).forEach(option => {
      if (option.value) {
        partnerTeachersIds.push(parseInt(option.value));
      }
    });
  }

  const payload = {
    username,
    email,
    first_name: firstName,
    last_name: lastName,
    user_profile_write: userProfile,
    is_admin: isAdmin,
    is_active: isActive,
  };

  if (password) {
    payload.password = password;
    // Para novos usuários, enviar também a confirmação de senha
    if (!editingUserId && passwordConfirm) {
      payload.password_confirm = passwordConfirm;
    }
  }

  // Adiciona professores parceiros apenas se for perfil Professor
  if (userProfile === "professor" && partnerTeachersIds.length > 0) {
    payload.partner_teachers_ids = partnerTeachersIds;
  } else if (userProfile === "professor") {
    payload.partner_teachers_ids = [];
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
    const errorMsg = error.message || "Erro desconhecido";
    alert(`Não foi possível salvar o usuário: ${errorMsg}`);
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

  // Listener para mudança de perfil - mostra/oculta campo de professores parceiros
  const userProfileSelect = document.getElementById("uUserProfile");
  if (userProfileSelect) {
    userProfileSelect.addEventListener("change", updatePartnerTeachersSelect);
  }

  // Validação em tempo real da confirmação de senha
  const passwordInput = document.getElementById("uPassword");
  const passwordConfirmInput = document.getElementById("uPasswordConfirm");
  const passwordMatchError = document.getElementById("passwordMatchError");
  
  function validatePasswordMatch() {
    if (!passwordInput || !passwordConfirmInput || !passwordMatchError) return;
    
    const password = passwordInput.value;
    const passwordConfirm = passwordConfirmInput.value;
    
    // Só valida se ambos os campos tiverem valor e não estiver editando
    if (!editingUserId && password && passwordConfirm) {
      if (password !== passwordConfirm) {
        passwordMatchError.style.display = "block";
        passwordConfirmInput.style.borderColor = "#dc2626";
        return false;
      } else {
        passwordMatchError.style.display = "none";
        passwordConfirmInput.style.borderColor = "#10b981";
        return true;
      }
    } else {
      passwordMatchError.style.display = "none";
      passwordConfirmInput.style.borderColor = "";
      return true;
    }
  }
  
  if (passwordInput && passwordConfirmInput) {
    passwordInput.addEventListener("input", validatePasswordMatch);
    passwordConfirmInput.addEventListener("input", validatePasswordMatch);
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

  // Colapso do grupo Conta na sidebar (com pequeno delay para garantir DOM)
  setTimeout(initContaGroupCollapse, 100);

  // Atualizar sidebar ao carregar a página
  updateSidebarStats();

  // Se for admin, inicializa UI de usuários
  if (state.currentUser && state.currentUser.is_admin) {
    initUsersUI();
    await loadUsers();
    renderUsers();
  }
});

function initContaGroupCollapse() {
  const STORAGE_KEY = "educaflowone_sidebar_conta_expanded";
  const group = document.getElementById("navGroupConta");
  const btn = document.getElementById("navGroupContaBtn");
  if (!group || !btn) {
    console.warn("initContaGroupCollapse: elementos não encontrados");
    return;
  }

  function setExpanded(expanded) {
    if (expanded) {
      group.classList.remove("nav-group--collapsed");
      group.classList.add("nav-group--expanded");
      btn.setAttribute("aria-expanded", "true");
      try { localStorage.setItem(STORAGE_KEY, "1"); } catch (_) {}
    } else {
      group.classList.add("nav-group--collapsed");
      group.classList.remove("nav-group--expanded");
      btn.setAttribute("aria-expanded", "false");
      try { localStorage.setItem(STORAGE_KEY, "0"); } catch (_) {}
    }
  }

  btn.addEventListener("click", function(e) {
    e.preventDefault();
    e.stopPropagation();
    const isExpanded = group.classList.contains("nav-group--expanded");
    setExpanded(!isExpanded);
  });

  try {
    if (localStorage.getItem(STORAGE_KEY) === "1") setExpanded(true);
  } catch (_) {}
}

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


// initStudentFilter() removido - agora em /alunos/

