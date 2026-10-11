/**
 * SmartAttend - Common UI & Component Logic
 * Topbar, Notifications dropdown, Sidebar mobile drawer, and shared widgets
 */

document.addEventListener('DOMContentLoaded', () => {
  initNotifications();
  initSidebarToggle();
});

// Notifications Dropdown System
let notificationsLoaded = false;

async function initNotifications() {
  const bellBtn = document.getElementById('notif-bell-btn');
  const dropdown = document.getElementById('notif-dropdown');
  const badge = document.getElementById('notif-badge');

  if (!bellBtn || !dropdown) return;

  // Fetch initial unread count
  try {
    const data = await API.get('/api/notifications');
    updateNotifBadge(data.unread_count);
  } catch (e) {
    console.warn('Could not fetch notifications:', e);
  }

  bellBtn.addEventListener('click', async (e) => {
    e.stopPropagation();
    dropdown.classList.toggle('hidden');
    if (!dropdown.classList.contains('hidden')) {
      await loadNotificationsList();
    }
  });

  document.addEventListener('click', (e) => {
    if (!dropdown.contains(e.target) && !bellBtn.contains(e.target)) {
      dropdown.classList.add('hidden');
    }
  });
}

function updateNotifBadge(count) {
  const badge = document.getElementById('notif-badge');
  if (!badge) return;
  if (count > 0) {
    badge.textContent = count > 9 ? '9+' : count;
    badge.classList.remove('hidden');
  } else {
    badge.classList.add('hidden');
  }
}

async function loadNotificationsList() {
  const listContainer = document.getElementById('notif-list');
  if (!listContainer) return;

  listContainer.innerHTML = '<div class="p-4 text-center text-xs text-slate-400">Loading notifications...</div>';

  try {
    const data = await API.get('/api/notifications');
    updateNotifBadge(data.unread_count);

    if (!data.notifications || data.notifications.length === 0) {
      listContainer.innerHTML = `
        <div class="p-6 text-center">
          <div class="w-10 h-10 mx-auto mb-2 text-slate-300">
            <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"></path></svg>
          </div>
          <p class="text-xs text-slate-500 font-medium">No notifications yet</p>
        </div>
      `;
      return;
    }

    listContainer.innerHTML = data.notifications.map(n => {
      let iconColor = 'text-blue-500 bg-blue-50';
      if (n.type === 'WARNING' || n.type === 'ALERT') iconColor = 'text-amber-500 bg-amber-50';
      if (n.type === 'PERMISSION') iconColor = 'text-indigo-500 bg-indigo-50';

      const unreadIndicator = n.read_status === 0 ? '<span class="w-2 h-2 rounded-full bg-blue-600 shrink-0"></span>' : '';

      return `
        <div class="p-3 border-b border-slate-100 hover:bg-slate-50 transition flex items-start gap-3 cursor-pointer ${n.read_status === 0 ? 'bg-blue-50/40' : ''}" onclick="markNotifRead(${n.id})">
          <div class="w-8 h-8 rounded-lg ${iconColor} flex items-center justify-center shrink-0 text-sm font-semibold">
            ${n.type === 'PERMISSION' ? '📋' : n.type === 'WARNING' ? '⚠' : 'ℹ'}
          </div>
          <div class="flex-1 min-w-0">
            <div class="flex items-center justify-between gap-1">
              <h4 class="text-xs font-semibold text-slate-900 truncate">${n.title}</h4>
              ${unreadIndicator}
            </div>
            <p class="text-xs text-slate-600 mt-0.5 line-clamp-2">${n.message}</p>
            <span class="text-[10px] text-slate-400 mt-1 block">${n.created_at || 'Just now'}</span>
          </div>
        </div>
      `;
    }).join('');

  } catch (err) {
    listContainer.innerHTML = '<div class="p-4 text-center text-xs text-rose-500">Failed to load notifications.</div>';
  }
}

async function markNotifRead(id) {
  try {
    await API.post(`/api/notifications/${id}/read`, {});
    const data = await API.get('/api/notifications');
    updateNotifBadge(data.unread_count);
    await loadNotificationsList();
  } catch (e) {
    console.error(e);
  }
}

async function markAllNotifsRead() {
  try {
    await API.post('/api/notifications/read-all', {});
    updateNotifBadge(0);
    await loadNotificationsList();
    showToast('All notifications marked as read', 'info');
  } catch (e) {
    showToast('Failed to mark notifications', 'error');
  }
}

// Mobile Sidebar Toggle
function initSidebarToggle() {
  const toggleBtn = document.getElementById('sidebar-mobile-toggle');
  const sidebar = document.getElementById('app-sidebar');
  const backdrop = document.getElementById('sidebar-backdrop');

  if (!toggleBtn || !sidebar) return;

  toggleBtn.addEventListener('click', () => {
    sidebar.classList.toggle('-translate-x-full');
    if (backdrop) backdrop.classList.toggle('hidden');
  });

  if (backdrop) {
    backdrop.addEventListener('click', () => {
      sidebar.classList.add('-translate-x-full');
      backdrop.classList.add('hidden');
    });
  }
}

// Render dynamic status pill
function renderStatusPill(statusObj) {
  if (!statusObj) return '';
  const isSafe = statusObj.is_safe;
  const level = statusObj.level;

  let bg = 'bg-slate-100 text-slate-700 border-slate-200';
  let dot = 'bg-slate-400';

  if (level === 'good') {
    bg = 'bg-emerald-50 text-emerald-700 border-emerald-200';
    dot = 'bg-emerald-500';
  } else if (level === 'warning') {
    bg = 'bg-amber-50 text-amber-700 border-amber-200';
    dot = 'bg-amber-500';
  } else if (level === 'danger') {
    bg = 'bg-orange-50 text-orange-700 border-orange-200';
    dot = 'bg-orange-500';
  } else if (level === 'critical') {
    bg = 'bg-rose-50 text-rose-700 border-rose-200';
    dot = 'bg-rose-500';
  }

  return `
    <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border ${bg}">
      <span class="w-1.5 h-1.5 rounded-full ${dot}"></span>
      ${statusObj.label}
    </span>
  `;
}
