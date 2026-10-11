/**
 * SmartAttend - Client API & Utility Framework
 */

const API = {
  getToken() {
    return localStorage.getItem('smartattend_token') || '';
  },

  setToken(token) {
    if (token) {
      localStorage.setItem('smartattend_token', token);
    } else {
      localStorage.removeItem('smartattend_token');
    }
  },

  getUser() {
    const userStr = localStorage.getItem('smartattend_user');
    return userStr ? JSON.parse(userStr) : null;
  },

  setUser(user) {
    if (user) {
      localStorage.setItem('smartattend_user', JSON.stringify(user));
    } else {
      localStorage.removeItem('smartattend_user');
    }
  },

  clearAuth() {
    localStorage.removeItem('smartattend_token');
    localStorage.removeItem('smartattend_user');
  },

  async request(endpoint, options = {}) {
    const url = endpoint.startsWith('http') ? endpoint : endpoint;
    const headers = options.headers || {};
    const token = this.getToken();

    if (token && !headers['Authorization']) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    if (!(options.body instanceof FormData) && !headers['Content-Type']) {
      headers['Content-Type'] = 'application/json';
    }

    options.headers = headers;

    try {
      const response = await fetch(url, options);

      if (response.status === 401) {
        this.clearAuth();
        if (window.location.pathname !== '/') {
          window.location.href = '/?msg=session_expired';
        }
        throw new Error('Authentication required or session expired.');
      }

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        const errorMsg = data.error || data.message || `Request failed with status ${response.status}`;
        throw new Error(errorMsg);
      }

      return data;
    } catch (err) {
      console.error(`API Error on ${endpoint}:`, err);
      throw err;
    }
  },

  get(endpoint) {
    return this.request(endpoint, { method: 'GET' });
  },

  post(endpoint, body) {
    const isFormData = body instanceof FormData;
    return this.request(endpoint, {
      method: 'POST',
      body: isFormData ? body : JSON.stringify(body)
    });
  },

  put(endpoint, body) {
    const isFormData = body instanceof FormData;
    return this.request(endpoint, {
      method: 'PUT',
      body: isFormData ? body : JSON.stringify(body)
    });
  },

  delete(endpoint) {
    return this.request(endpoint, { method: 'DELETE' });
  }
};

// UI Utilities: Toast Alerts
function showToast(message, type = 'info', duration = 4000) {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = 'toast-msg erp-card border shadow-lg';

  let borderColor = '#3b82f6';
  let iconHtml = `
    <svg class="w-5 h-5 text-blue-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
    </svg>`;

  if (type === 'success') {
    borderColor = '#10b981';
    iconHtml = `
      <svg class="w-5 h-5 text-emerald-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
      </svg>`;
  } else if (type === 'error' || type === 'critical') {
    borderColor = '#ef4444';
    iconHtml = `
      <svg class="w-5 h-5 text-rose-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
      </svg>`;
  } else if (type === 'warning') {
    borderColor = '#f59e0b';
    iconHtml = `
      <svg class="w-5 h-5 text-amber-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
      </svg>`;
  }

  toast.style.borderLeftColor = borderColor;
  toast.innerHTML = `
    ${iconHtml}
    <div class="flex-1 text-sm font-medium text-slate-800">${message}</div>
    <button onclick="this.parentElement.remove()" class="text-slate-400 hover:text-slate-600 ml-2">
      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
      </svg>
    </button>
  `;

  container.appendChild(toast);

  setTimeout(() => {
    if (toast.parentElement) {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(100%)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }
  }, duration);
}

// Modal Controllers
function openModal(modalId) {
  const el = document.getElementById(modalId);
  if (el) {
    el.classList.remove('hidden');
    el.classList.add('flex');
    document.body.style.overflow = 'hidden';
  }
}

function closeModal(modalId) {
  const el = document.getElementById(modalId);
  if (el) {
    el.classList.add('hidden');
    el.classList.remove('flex');
    document.body.style.overflow = '';
  }
}

// Global Auth / Logout handler
async function handleLogout() {
  try {
    await API.post('/api/auth/logout', {});
  } catch (e) {
    // Continue cleanup even if server error
  }
  API.clearAuth();
  window.location.href = '/?msg=logged_out';
}

// Format Date Utility
function formatDate(dateStr) {
  if (!dateStr) return '-';
  const parts = dateStr.split('-');
  if (parts.length === 3) {
    const d = new Date(parts[0], parts[1] - 1, parts[2]);
    return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
  }
  return dateStr;
}
