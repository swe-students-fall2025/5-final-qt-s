/* static/shared.js
   - helper wrappers for API calls with Authorization header
   - modal helpers
   - toast notifications
   - spinner overlay
   - FullCalendar helper
*/

/* ---------- Config ---------- */
const API_ROOT = "/api"; // all API calls prefix

/* ---------- Auth helpers ---------- */
function getToken() {
  return sessionStorage.getItem("token");
}
function setToken(token) {
  sessionStorage.setItem("token", token);
}
function clearAuth() {
  sessionStorage.removeItem("token");
  sessionStorage.removeItem("user_id");
  sessionStorage.removeItem("group_name");
}

/* ---------- Group helpers ---------- */
function getGroupName() {
  return sessionStorage.getItem("group_name");
}
function setGroupName(name) {
  sessionStorage.setItem("group_name", name);
}

/* ---------- UI: Toasts ---------- */
function showToast(message, type = "info", time = 3000) {
  const el = document.getElementById("global-toast");
  if (!el) return;
  el.innerText = message;
  el.className = "toast " + (type === "success" ? "success" : (type === "error" ? "error" : ""));
  el.style.display = "block";
  setTimeout(()=> el.style.display = "none", time);
}

/* ---------- UI: Spinner ---------- */
function showSpinner() {
  const s = document.getElementById("global-spinner");
  if (s) s.style.display = "flex";
}
function hideSpinner() {
  const s = document.getElementById("global-spinner");
  if (s) s.style.display = "none";
}

/* ---------- API wrappers ---------- */
async function apiFetch(path, opts = {}) {
  showSpinner();
  const headers = opts.headers || {};
  if (!headers["Content-Type"] && !(opts.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  const token = getToken();
  if (token) headers["Authorization"] = "Bearer " + token;
  opts.headers = headers;
  try {
    const res = await fetch(API_ROOT + path, opts);
    const text = await res.text();
    hideSpinner();
    if (!text) return null;
    let data;
    try { data = JSON.parse(text); } catch(e) { data = text; }
    if (!res.ok) {
      const err = data.error || data.message || res.statusText;
      throw new Error(err);
    }
    return data;
  } catch (err) {
    hideSpinner();
    throw err;
  }
}
async function apiGet(path) { return apiFetch(path, { method: "GET" }); }
async function apiPost(path, body) { return apiFetch(path, { method: "POST", body: JSON.stringify(body) }); }
async function apiPatch(path, body) { return apiFetch(path, { method: "PATCH", body: JSON.stringify(body) }); }
async function apiDelete(path) { return apiFetch(path, { method: "DELETE" }); }

/* ---------- Modal helpers ---------- */
function openModal(modalId) {
  const el = document.getElementById(modalId + "-backdrop");
  if (el) el.style.display = "flex";
}
function closeModal(modalId) {
  const el = document.getElementById(modalId + "-backdrop");
  if (el) el.style.display = "none";
}
function setModalField(modalId, selector, value) {
  const root = document.getElementById(modalId + "-backdrop");
  if (!root) return;
  const el = root.querySelector(selector);
  if (el) el.value = value;
}

/* ---------- FullCalendar helper (simple) ---------- */
function initFullCalendar(domElId, fetchEventsCallback) {
  if (!window.FullCalendar) {
    console.warn("FullCalendar not loaded");
    return;
  }
  const calendarEl = document.getElementById(domElId);
  if (!calendarEl) return;
  const calendar = new FullCalendar.Calendar(calendarEl, {
    initialView: 'dayGridMonth',
    headerToolbar: {
      left: 'prev,next today',
      center: 'title',
      right: 'dayGridMonth,timeGridWeek,listWeek'
    },
    events: function(info, successCallback, failureCallback) {
      fetchEventsCallback(info.startStr, info.endStr)
        .then(events => successCallback(events))
        .catch(err => failureCallback(err));
    },
    eventClick: function(info) {
      const ev = info.event.extendedProps;
      const eventClick = new CustomEvent('calendarEventClick', { detail: ev });
      window.dispatchEvent(eventClick);
    }
  });
  calendar.render();
  return calendar;
}
