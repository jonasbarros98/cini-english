/**
 * Calendar Integration - Integração do novo calendário com backend
 * Substitui os mocks do calendar_new.html por chamadas reais à API
 */

(function() {
  'use strict';

  // Aguardar DOM estar pronto
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  function init() {
    // Verificar se estamos na página do calendário
    if (!document.getElementById('monthView') && !document.getElementById('weekView')) {
      return; // Não é a página do calendário
    }

    // Substituir mocks por integração real
    replaceMockData();
    wireRealAPI();
  }

  // ==========
  // Utils
  // ==========
  function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(";").shift();
    return null;
  }

  function escapeHtml(str) {
    return String(str)
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", "&#039;");
  }

  // ==========
  // API Calls
  // ==========
  async function fetchJSON(url, options = {}) {
    const csrf = getCookie('csrftoken');
    const headers = {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrf,
      ...options.headers
    };

    const response = await fetch(url, {
      ...options,
      headers,
      credentials: 'same-origin'
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: 'Erro desconhecido' }));
      throw new Error(error.error || `HTTP ${response.status}`);
    }

    return response.json();
  }

  // ==========
  // Cache simples por range
  // ==========
  const cache = {
    events: new Map(), // key: "start-end", value: {data, timestamp}
    dayNotes: new Map(), // key: "YYYY-MM-DD", value: {data, timestamp}
    TTL: 5 * 60 * 1000 // 5 minutos
  };

  function getCacheKey(start, end) {
    return `${start}-${end}`;
  }

  function getCachedEvents(start, end) {
    const key = getCacheKey(start, end);
    const cached = cache.events.get(key);
    if (cached && (Date.now() - cached.timestamp) < cache.TTL) {
      return cached.data;
    }
    return null;
  }

  function setCachedEvents(start, end, data) {
    const key = getCacheKey(start, end);
    cache.events.set(key, { data, timestamp: Date.now() });
  }

  function getCachedDayNote(date) {
    const cached = cache.dayNotes.get(date);
    if (cached && (Date.now() - cached.timestamp) < cache.TTL) {
      return cached.data;
    }
    return null;
  }

  function setCachedDayNote(date, data) {
    cache.dayNotes.set(date, { data, timestamp: Date.now() });
  }

  function clearCache() {
    cache.events.clear();
    cache.dayNotes.clear();
  }

  // ==========
  // Load Events
  // ==========
  async function loadEvents(start, end) {
    try {
      // Verificar cache
      const cached = getCachedEvents(start, end);
      if (cached) {
        return cached;
      }

      const url = `/api/calendar/events/?start=${start}&end=${end}`;
      const events = await fetchJSON(url);
      
      // Cachear
      setCachedEvents(start, end, events);
      
      return events;
    } catch (error) {
      console.error('Erro ao carregar eventos:', error);
      showToast(`Erro ao carregar eventos: ${error.message}`, true);
      return [];
    }
  }

  // ==========
  // Load Day Note
  // ==========
  async function loadDayNote(date) {
    try {
      // Verificar cache
      const cached = getCachedDayNote(date);
      if (cached !== null) {
        return cached;
      }

      const url = `/api/calendar/day-note/?date=${date}`;
      const data = await fetchJSON(url);
      
      // Cachear
      setCachedDayNote(date, data);
      
      return data;
    } catch (error) {
      console.error('Erro ao carregar nota do dia:', error);
      return { date, text: '' };
    }
  }

  // ==========
  // Save Day Note
  // ==========
  async function saveDayNote(date, text) {
    try {
      const url = `/api/calendar/day-note/update/`;
      const data = await fetchJSON(url, {
        method: 'PUT',
        body: JSON.stringify({ date, text })
      });
      
      // Atualizar cache
      setCachedDayNote(date, data);
      
      return data;
    } catch (error) {
      console.error('Erro ao salvar nota:', error);
      throw error;
    }
  }

  // ==========
  // Update Event Status
  // ==========
  async function updateEventStatus(eventId, newStatus) {
    try {
      const url = `/api/calendar/events/${eventId}/status/`;
      const event = await fetchJSON(url, {
        method: 'PATCH',
        body: JSON.stringify({ status: newStatus })
      });
      
      // Invalidar cache de eventos
      clearCache();
      
      return event;
    } catch (error) {
      console.error('Erro ao atualizar status:', error);
      throw error;
    }
  }

  // ==========
  // Create Event
  // ==========
  async function createEvent(eventData) {
    try {
      const url = `/api/calendar/events/create/`;
      const event = await fetchJSON(url, {
        method: 'POST',
        body: JSON.stringify(eventData)
      });
      
      // Invalidar cache
      clearCache();
      
      return event;
    } catch (error) {
      console.error('Erro ao criar evento:', error);
      throw error;
    }
  }

  // ==========
  // Delete Event
  // ==========
  async function deleteEvent(eventId) {
    try {
      const url = `/api/lessons/${eventId}/`;
      await fetchJSON(url, {
        method: 'DELETE'
      });
      
      // Invalidar cache
      clearCache();
      
      return true;
    } catch (error) {
      console.error('Erro ao excluir evento:', error);
      throw error;
    }
  }

  // ==========
  // Replace Mock Data
  // ==========
  function replaceMockData() {
    // Substituir variável global `lessons` se existir
    if (typeof window !== 'undefined' && window.lessons) {
      window.lessons = []; // Será preenchido via API
    }
    
    // Substituir variável global `dayNotes` se existir
    if (typeof window !== 'undefined' && window.dayNotes) {
      window.dayNotes = {}; // Será preenchido via API
    }
  }

  // ==========
  // Wire Real API
  // ==========
  function wireRealAPI() {
    // Interceptar funções que usam dados mockados
    // Isso será feito no template adaptado
    
    // Expor funções globais para o template usar
    if (typeof window !== 'undefined') {
      window.calendarAPI = {
        loadEvents,
        loadDayNote,
        saveDayNote,
        updateEventStatus,
        createEvent,
        deleteEvent,
        clearCache
      };
    }
  }

  // ==========
  // Toast Helper
  // ==========
  function showToast(msg, isError = false) {
    const toast = document.getElementById('toast');
    if (!toast) return;
    
    toast.textContent = msg;
    if (isError) {
      toast.style.background = 'rgba(239, 68, 68, 0.92)';
    } else {
      toast.style.background = 'rgba(15, 23, 42, 0.92)';
    }
    
    toast.classList.add('show');
    clearTimeout(showToast._t);
    showToast._t = setTimeout(() => {
      toast.classList.remove('show');
    }, 2200);
  }

  // Expor showToast globalmente
  if (typeof window !== 'undefined') {
    window.showToast = showToast;
  }

})();
