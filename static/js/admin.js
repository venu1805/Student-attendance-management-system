/**
 * SmartAttend - ERP Admin Portal Script
 * User management, academic configuration, security audit logs, and reports engine
 */

let adminDashboardData = null;

document.addEventListener('DOMContentLoaded', async () => {
  await loadAdminDashboard();
  setupAdminTabs();
  setupAddUserForm();
  setupSettingsForm();
});

// 1. Load Admin Dashboard
async function loadAdminDashboard() {
  try {
    const data = await API.get('/api/admin/dashboard');
    adminDashboardData = data;

    document.getElementById('adm-kpi-students').textContent = data.total_students;
    document.getElementById('adm-kpi-faculty').textContent = data.total_faculty;
    document.getElementById('adm-kpi-departments').textContent = data.total_departments;
    document.getElementById('adm-kpi-subjects').textContent = data.total_subjects;
    document.getElementById('adm-kpi-attendance').textContent = data.total_attendance_records;
    document.getElementById('adm-kpi-pending').textContent = data.pending_permissions;

    renderDepartmentComparison(data.department_stats);
    await loadAdminUsers();
    await loadAdminAuditLogs();
    await loadAdminSettings();

  } catch (err) {
    showToast('Failed to load admin dashboard: ' + err.message, 'error');
  }
}

// 2. Department Comparison Cards
function renderDepartmentComparison(depts) {
  const container = document.getElementById('dept-comparison-container');
  if (!container || !depts) return;

  container.innerHTML = depts.map(d => `
    <div class="p-4 rounded-xl border border-slate-200 bg-white">
      <div class="flex items-center justify-between">
        <h4 class="font-bold text-slate-800 text-sm">${d.name} (${d.code})</h4>
        <span class="text-xs font-bold ${d.percentage >= 75 ? 'text-emerald-600' : 'text-rose-600'}">${d.percentage}%</span>
      </div>
      <div class="w-full bg-slate-100 rounded-full h-2 mt-2.5 overflow-hidden">
        <div class="h-full ${d.percentage >= 75 ? 'bg-emerald-500' : 'bg-rose-500'}" style="width: ${d.percentage}%"></div>
      </div>
      <div class="flex justify-between text-[11px] text-slate-400 mt-2">
        <span>Attended: ${d.attended}</span>
        <span>Conducted: ${d.conducted}</span>
      </div>
    </div>
  `).join('');
}

// 3. User Management
async function loadAdminUsers() {
  const tbody = document.getElementById('admin-users-table-body');
  const roleFilter = document.getElementById('user-role-filter')?.value || '';
  const search = document.getElementById('user-search-input')?.value.trim() || '';

  if (!tbody) return;

  try {
    let url = '/api/admin/users?';
    if (roleFilter) url += `role=${roleFilter}&`;
    if (search) url += `search=${encodeURIComponent(search)}`;

    const data = await API.get(url);
    const users = data.users || [];

    if (users.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" class="p-8 text-center text-xs text-slate-400">No users found matching query.</td></tr>`;
      return;
    }

    tbody.innerHTML = users.map(u => {
      let roleBadge = '';
      if (u.role === 'ADMIN') roleBadge = '<span class="px-2 py-0.5 rounded text-[11px] font-bold bg-rose-100 text-rose-800">Admin</span>';
      else if (u.role === 'HOD') roleBadge = '<span class="px-2 py-0.5 rounded text-[11px] font-bold bg-purple-100 text-purple-800">HOD</span>';
      else if (u.role === 'FACULTY') roleBadge = '<span class="px-2 py-0.5 rounded text-[11px] font-bold bg-blue-100 text-blue-800">Faculty</span>';
      else roleBadge = '<span class="px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-100 text-emerald-800">Student</span>';

      const isActive = u.status === 'ACTIVE';

      return `
        <tr class="border-b border-slate-100 text-xs hover:bg-slate-50 transition">
          <td class="px-4 py-3 font-semibold text-slate-800">${u.name}</td>
          <td class="px-4 py-3 text-slate-600 font-mono-code">${u.email}</td>
          <td class="px-4 py-3 text-center">${roleBadge}</td>
          <td class="px-4 py-3 text-center">
            <span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${isActive ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-slate-100 text-slate-500'}">
              ${u.status}
            </span>
          </td>
          <td class="px-4 py-3 text-slate-400">${formatDate(u.created_at ? u.created_at.split(' ')[0] : '')}</td>
          <td class="px-4 py-3 text-right">
            <button onclick="toggleUserStatus(${u.id}, '${isActive ? 'DISABLED' : 'ACTIVE'}')" class="px-2.5 py-1 text-xs font-semibold rounded-lg ${isActive ? 'text-rose-600 hover:bg-rose-50 border border-rose-200' : 'text-emerald-600 hover:bg-emerald-50 border border-emerald-200'} transition">
              ${isActive ? 'Disable' : 'Enable'}
            </button>
          </td>
        </tr>
      `;
    }).join('');

  } catch (err) {
    console.error('Failed to load admin users:', err);
  }
}

async function toggleUserStatus(userId, newStatus) {
  try {
    const res = await API.post(`/api/admin/users/${userId}/status`, { status: newStatus });
    showToast(res.message || 'Status updated', 'success');
    await loadAdminUsers();
  } catch (err) {
    showToast(err.message || 'Update failed', 'error');
  }
}

function setupAddUserForm() {
  const form = document.getElementById('add-user-form');
  const roleSelect = document.getElementById('new-user-role');
  const studentFields = document.getElementById('new-student-fields');

  if (roleSelect && studentFields) {
    roleSelect.addEventListener('change', () => {
      if (roleSelect.value === 'STUDENT') {
        studentFields.classList.remove('hidden');
      } else {
        studentFields.classList.add('hidden');
      }
    });
  }

  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const payload = {
        name: document.getElementById('new-user-name').value.trim(),
        email: document.getElementById('new-user-email').value.trim(),
        password: document.getElementById('new-user-password').value || 'password123',
        role: document.getElementById('new-user-role').value,
        department_id: parseInt(document.getElementById('new-user-dept').value || 1),
        usn: document.getElementById('new-student-usn')?.value.trim() || undefined,
        semester: parseInt(document.getElementById('new-student-sem')?.value || 5),
        section: document.getElementById('new-student-sec')?.value || 'A'
      };

      try {
        const res = await API.post('/api/admin/users', payload);
        showToast(res.message || 'User created successfully!', 'success');
        closeModal('add-user-modal');
        form.reset();
        await loadAdminUsers();
        await loadAdminDashboard();
      } catch (err) {
        showToast(err.message || 'Failed to create user', 'error');
      }
    });
  }
}

// 4. Academic Settings
async function loadAdminSettings() {
  try {
    const data = await API.get('/api/admin/settings');
    const minInput = document.getElementById('setting-min-attendance');
    const yearInput = document.getElementById('setting-academic-year');
    const semInput = document.getElementById('setting-semester');

    if (minInput) minInput.value = data.minimum_attendance_percentage;
    if (yearInput) yearInput.value = data.academic_year;
    if (semInput) semInput.value = data.current_semester;

  } catch (err) {
    console.error('Failed to load settings:', err);
  }
}

function setupSettingsForm() {
  const form = document.getElementById('academic-settings-form');
  if (!form) return;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const payload = {
      minimum_attendance_percentage: parseFloat(document.getElementById('setting-min-attendance').value),
      academic_year: document.getElementById('setting-academic-year').value.trim(),
      current_semester: parseInt(document.getElementById('setting-semester').value)
    };

    try {
      const res = await API.put('/api/admin/settings', payload);
      showToast(res.message || 'Settings updated successfully!', 'success');
      await loadAdminDashboard();
    } catch (err) {
      showToast(err.message || 'Failed to update settings', 'error');
    }
  });
}

// 5. Security Audit Logs
async function loadAdminAuditLogs() {
  const tbody = document.getElementById('admin-audit-table-body');
  if (!tbody) return;

  try {
    const data = await API.get('/api/admin/audit-logs');
    const logs = data.audit_logs || [];

    if (logs.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" class="p-8 text-center text-xs text-slate-400">No audit log records found.</td></tr>`;
      return;
    }

    tbody.innerHTML = logs.map(l => `
      <tr class="border-b border-slate-100 text-xs hover:bg-slate-50">
        <td class="px-4 py-3 font-mono-code text-slate-500">${l.created_at}</td>
        <td class="px-4 py-3 font-semibold text-slate-800">${l.user_name || 'System'}</td>
        <td class="px-4 py-3 font-bold font-mono-code text-blue-700">${l.action}</td>
        <td class="px-4 py-3 text-slate-600">${l.entity_type} ${l.entity_id ? `(${l.entity_id})` : ''}</td>
        <td class="px-4 py-3 text-slate-700 max-w-xs truncate" title="${l.details}">${l.details}</td>
        <td class="px-4 py-3 text-slate-400 font-mono-code">${l.ip_address}</td>
      </tr>
    `).join('');

  } catch (err) {
    console.error('Failed to load audit logs:', err);
  }
}

// 6. Reports & Export Engine
async function generateAndExportReport(format = 'csv') {
  const reportType = document.getElementById('report-type-select')?.value || 'student_attendance';
  const reportBtn = document.getElementById('btn-export-csv');

  try {
    if (reportBtn) reportBtn.disabled = true;
    const res = await API.get(`/api/admin/reports/${reportType}`);
    const records = res.records || [];

    if (records.length === 0) {
      showToast('No records found for the selected report.', 'warning');
      return;
    }

    if (format === 'csv') {
      exportToCsv(res.title || 'report', records);
      showToast('CSV downloaded successfully!', 'success');
    } else if (format === 'print') {
      printReportView(res.title, records);
    }

  } catch (err) {
    showToast('Failed to generate report: ' + err.message, 'error');
  } finally {
    if (reportBtn) reportBtn.disabled = false;
  }
}

function exportToCsv(filename, data) {
  if (!data || data.length === 0) return;
  const headers = Object.keys(data[0]);
  const rows = data.map(row => headers.map(h => `"${String(row[h] || '').replace(/"/g, '""')}"`).join(','));
  const csvContent = [headers.join(','), ...rows].join('\n');

  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.setAttribute('href', url);
  link.setAttribute('download', `${filename.toLowerCase().replace(/[^a-z0-9]/g, '_')}_${new Date().toISOString().slice(0,10)}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

function printReportView(title, data) {
  if (!data || data.length === 0) return;
  const headers = Object.keys(data[0]);

  const printWindow = window.open('', '_blank');
  printWindow.document.write(`
    <!DOCTYPE html>
    <html>
    <head>
      <title>${title} - SmartAttend ERP</title>
      <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; padding: 2rem; color: #1e293b; }
        .header { text-align: center; border-bottom: 2px solid #e2e8f0; padding-bottom: 1rem; margin-bottom: 1.5rem; }
        .header h1 { margin: 0; font-size: 1.5rem; color: #1e3a8a; }
        .header p { margin: 0.25rem 0 0; color: #64748b; font-size: 0.875rem; }
        table { width: 100%; border-collapse: collapse; margin-top: 1rem; font-size: 0.75rem; }
        th, td { border: 1px solid #cbd5e1; padding: 0.5rem; text-align: left; }
        th { background: #f1f5f9; font-weight: bold; text-transform: uppercase; }
        tr:nth-child(even) { background: #f8fafc; }
        .footer { margin-top: 2rem; text-align: right; font-size: 0.75rem; color: #94a3b8; }
      </style>
    </head>
    <body>
      <div class="header">
        <h1>SMARTATTEND COLLEGE ERP</h1>
        <p>${title}</p>
        <p>Generated on: ${new Date().toLocaleString()} | Academic Year: 2026-2027</p>
      </div>
      <table>
        <thead>
          <tr>${headers.map(h => `<th>${h.replace(/_/g, ' ')}</th>`).join('')}</tr>
        </thead>
        <tbody>
          ${data.map(row => `<tr>${headers.map(h => `<td>${row[h]}</td>`).join('')}</tr>`).join('')}
        </tbody>
      </table>
      <div class="footer">
        <p>Confidential • For Institutional Use Only • SmartAttend Student Attendance Management System</p>
      </div>
      <script>
        window.onload = function() { window.print(); }
      </script>
    </body>
    </html>
  `);
  printWindow.document.close();
}

// 7. Admin Tab Navigation
function setupAdminTabs() {
  const tabs = document.querySelectorAll('[data-adm-tab-target]');
  tabs.forEach(t => {
    t.addEventListener('click', (e) => {
      e.preventDefault();
      const targetId = t.getAttribute('data-adm-tab-target');

      tabs.forEach(link => link.classList.remove('active'));
      t.classList.add('active');

      const views = document.querySelectorAll('.adm-tab-view');
      views.forEach(v => v.classList.add('hidden'));

      const targetView = document.getElementById(targetId);
      if (targetView) targetView.classList.remove('hidden');

      const sidebar = document.getElementById('app-sidebar');
      const backdrop = document.getElementById('sidebar-backdrop');
      if (sidebar && backdrop) {
        sidebar.classList.add('-translate-x-full');
        backdrop.classList.add('hidden');
      }
    });
  });
}
