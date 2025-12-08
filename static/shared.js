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
function showToast(message, type = "info", time = 1500) {
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

/* ---------- Button loading helpers ---------- */
function setButtonLoading(button, loading = true) {
  if (!button) return;
  if (loading) {
    button.classList.add('loading');
    button.disabled = true;
    if (!button.dataset.originalText) {
      button.dataset.originalText = button.textContent;
    }
  } else {
    button.classList.remove('loading');
    button.disabled = false;
    if (button.dataset.originalText) {
      button.textContent = button.dataset.originalText;
    }
  }
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
  if (el) {
    el.classList.add("show");
    el.style.display = "flex";
    // Focus trap for accessibility
    const firstInput = el.querySelector('input, button, textarea, select');
    if (firstInput) setTimeout(() => firstInput.focus(), 100);
  }
}

function closeModal(modalId) {
  const el = document.getElementById(modalId + "-backdrop");
  if (el) {
    el.classList.remove("show");
    el.style.display = "none";
    // Reset all buttons in modal to remove loading state
    const buttons = el.querySelectorAll('.btn.loading');
    buttons.forEach(btn => {
      setButtonLoading(btn, false);
    });
  }
}

function setModalField(modalId, selector, value) {
  const root = document.getElementById(modalId + "-backdrop");
  if (!root) return;
  const el = root.querySelector(selector);
  if (el) el.value = value;
}

// Close modal when clicking backdrop
document.addEventListener('click', (e) => {
  if (e.target.classList.contains('modal-backdrop')) {
    e.target.classList.remove("show");
    e.target.style.display = "none";
  }
});

// Close modal with Escape key
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    const openModal = document.querySelector('.modal-backdrop.show');
    if (openModal) {
      openModal.classList.remove("show");
      openModal.style.display = "none";
    }
  }
});

// Improved prompt replacement - returns Promise
function showPrompt(title, message, placeholder = '', defaultValue = '') {
  return new Promise((resolve) => {
    const modalId = 'prompt-modal-' + Date.now();
    const backdrop = document.createElement('div');
    backdrop.id = modalId + "-backdrop";
    backdrop.className = "modal-backdrop show";
    backdrop.style.display = "flex";
    backdrop.innerHTML = `
      <div class="modal">
        <h3>${title}</h3>
        <p>${message}</p>
        <div class="modal-body">
          <div class="modal-input-group">
            <label>${placeholder || 'Enter value'}</label>
            <input type="text" id="${modalId}-input" value="${defaultValue}" autofocus>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn secondary" id="${modalId}-cancel">Cancel</button>
          <button class="btn" id="${modalId}-confirm">Confirm</button>
        </div>
      </div>
    `;
    
    document.body.appendChild(backdrop);
    
    const input = document.getElementById(`${modalId}-input`);
    const confirmBtn = document.getElementById(`${modalId}-confirm`);
    const cancelBtn = document.getElementById(`${modalId}-cancel`);
    
    const cleanup = () => {
      backdrop.remove();
    };
    
    const confirm = () => {
      const val = input.value.trim();
      cleanup();
      resolve(val || null);
    };
    
    confirmBtn.onclick = confirm;
    cancelBtn.onclick = () => { cleanup(); resolve(null); };
    
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') confirm();
      if (e.key === 'Escape') { cleanup(); resolve(null); }
    });
    
    setTimeout(() => input.focus(), 100);
  });
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
