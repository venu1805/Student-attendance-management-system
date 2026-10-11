/**
 * SmartAttend - Head of Department (HOD) Portal Script
 * Department oversight, escalated permission approvals, and defaulter tracking
 */

let hodDashboardData = null;
let activeHodReviewRequest = null;

document.addEventListener('DOMContentLoaded', async () => {
  await loadHodDashboard();
  setupHodTabs();
});

// 1. Load HOD Dashboard
async function loadHodDashboard() {
  try {
    const data = await API.get('/api/hod/dashboard');
    hodDashboardData = data;

    const user = API.getUser() || {};
    const deptNameEl = document.getElementById('hod-dept-name');
    if (deptNameEl) deptNameEl.textContent = `Department of ${data.department.name} (${data.department.code})`;

    const branchLabel = document.getElementById('hod-kpi-branch-label');
    if (branchLabel) branchLabel.textContent = `Enrolled in ${data.department.code}`;

    const headerName = document.getElementById('hod-header-name');
    const headerTitle = document.getElementById('hod-header-title');
    const avatarInitials = document.getElementById('hod-avatar-initials');

    if (headerName && user.name) headerName.textContent = user.name;
    if (headerTitle) headerTitle.textContent = `Professor & Head, ${data.department.code}`;
    if (avatarInitials && user.name) {
      avatarInitials.textContent = user.name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();
    }

    document.getElementById('hod-kpi-faculty').textContent = data.faculty_count;
    document.getElementById('hod-kpi-students').textContent = data.student_count;
    document.getElementById('hod-kpi-avg-att').textContent = `${data.average_attendance}%`;
    document.getElementById('hod-kpi-low-att').textContent = data.low_attendance_count;
    document.getElementById('hod-kpi-escalated').textContent = data.escalated_permissions_count;

    await loadHodEscalatedPermissions();
    await loadHodLowAttendance();

  } catch (err) {
    showToast('Failed to load HOD dashboard: ' + err.message, 'error');
  }
}

// 2. Load Escalated Permission Requests
async function loadHodEscalatedPermissions() {
  const tbody = document.getElementById('hod-permissions-table-body');
  if (!tbody) return;

  try {
    const data = await API.get('/api/hod/permissions');
    const requests = data.requests || [];

    if (requests.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" class="p-8 text-center text-xs text-slate-400">No escalated permission requests currently awaiting your decision.</td></tr>`;
      return;
    }

    tbody.innerHTML = requests.map(pr => `
      <tr class="border-b border-slate-100 text-xs hover:bg-slate-50 transition">
        <td class="px-4 py-3.5 font-bold font-mono-code text-blue-700">${pr.request_code}</td>
        <td class="px-4 py-3.5">
          <div class="font-bold text-slate-800">${pr.student_name}</div>
          <div class="text-[11px] text-slate-500 font-mono-code">${pr.usn}</div>
        </td>
        <td class="px-4 py-3.5 font-semibold text-slate-700">${pr.subject_code}</td>
        <td class="px-4 py-3.5 text-slate-600">${formatDate(pr.date)} (Hr ${pr.hour})</td>
        <td class="px-4 py-3.5 font-medium text-slate-800">${pr.reason}</td>
        <td class="px-4 py-3.5 text-purple-700 font-medium italic">
          "${pr.faculty_comment || 'Escalated for policy decision'}"
        </td>
        <td class="px-4 py-3.5 text-right">
          <button onclick='openHodReviewModal(${JSON.stringify(pr)})' class="px-3.5 py-1.5 bg-purple-600 hover:bg-purple-700 text-white font-bold rounded-lg text-xs shadow-sm transition">
            Review & Decide
          </button>
        </td>
      </tr>
    `).join('');

  } catch (err) {
    console.error('Failed to load escalated permissions:', err);
  }
}

// 3. Open HOD Review Modal
function openHodReviewModal(pr) {
  activeHodReviewRequest = pr;
  const title = document.getElementById('hod-review-title');
  const details = document.getElementById('hod-review-details');
  const remarks = document.getElementById('hod-review-remarks');

  if (title) title.textContent = `HOD Review: ${pr.request_code} — ${pr.student_name}`;
  if (remarks) remarks.value = '';

  let docBtn = '<span class="text-xs text-slate-400 italic">No document attached</span>';
  if (pr.document_filename) {
    docBtn = `
      <a href="/api/files/${pr.document_filename}" target="_blank" class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-50 border border-blue-200 text-blue-700 text-xs font-semibold hover:bg-blue-100 transition">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path></svg>
        Verify Uploaded Document (${pr.document_original_name || 'Document'})
      </a>
    `;
  }

  if (details) {
    details.innerHTML = `
      <div class="grid grid-cols-2 gap-3 p-3 bg-slate-50 rounded-xl border border-slate-100 text-xs">
        <div><span class="text-slate-500">Student:</span> <strong class="text-slate-800">${pr.student_name} (${pr.usn})</strong></div>
        <div><span class="text-slate-500">Subject:</span> <strong class="text-slate-800">${pr.subject_code} — ${pr.subject_name}</strong></div>
        <div><span class="text-slate-500">Class Session:</span> <strong class="text-slate-800">${formatDate(pr.date)}, Hour ${pr.hour}</strong></div>
        <div><span class="text-slate-500">Escalated By:</span> <strong class="text-slate-800">${pr.faculty_name}</strong></div>
      </div>
      <div>
        <span class="font-bold text-xs text-slate-700 block mb-1">Reason: ${pr.reason}</span>
        <div class="p-3 bg-white border border-slate-200 rounded-xl text-xs text-slate-800 leading-relaxed">${pr.description}</div>
      </div>
      <div class="p-3 rounded-xl border border-purple-200 bg-purple-50 text-xs text-purple-900">
        <span class="font-bold block mb-1">Faculty Escalation Note:</span>
        "${pr.faculty_comment || 'Escalated to HOD for discretionary authorization.'}"
      </div>
      <div>
        <span class="font-bold text-xs text-slate-700 block mb-1">Supporting Document:</span>
        ${docBtn}
      </div>
    `;
  }

  openModal('hod-review-modal');
}

// 4. Submit HOD Decision
async function submitHodDecision(action) {
  if (!activeHodReviewRequest) return;
  const remarks = document.getElementById('hod-review-remarks')?.value.trim();

  if (!remarks) {
    showToast('Please enter official HOD review remarks before submitting.', 'warning');
    return;
  }

  try {
    const res = await API.post(`/api/hod/permissions/${activeHodReviewRequest.id}/review`, {
      action: action,
      remarks: remarks
    });

    showToast(res.message || 'HOD decision recorded successfully!', 'success');
    closeModal('hod-review-modal');
    await loadHodDashboard();

  } catch (err) {
    showToast(err.message || 'Failed to submit HOD decision', 'error');
  }
}

// 5. Load Department Low Attendance List
async function loadHodLowAttendance() {
  const tbody = document.getElementById('hod-low-table-body');
  if (!tbody) return;

  try {
    const data = await API.get('/api/hod/low-attendance');
    const students = data.low_attendance_students || [];

    if (students.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" class="p-8 text-center text-xs text-emerald-600 font-medium">All department students meet the 75% minimum attendance requirement.</td></tr>`;
      return;
    }

    tbody.innerHTML = students.map(st => `
      <tr class="border-b border-slate-100 text-xs hover:bg-slate-50 transition">
        <td class="px-4 py-3.5 font-bold font-mono-code text-rose-700">${st.usn}</td>
        <td class="px-4 py-3.5">
          <div class="font-bold text-slate-800">${st.student_name}</div>
          <div class="text-[11px] text-slate-400">${st.student_email}</div>
        </td>
        <td class="px-4 py-3.5 text-slate-600">Sem ${st.semester} - ${st.section}</td>
        <td class="px-4 py-3.5 text-center text-slate-700">${st.attended} / ${st.conducted}</td>
        <td class="px-4 py-3.5 text-center font-bold text-rose-600">${st.percentage}%</td>
        <td class="px-4 py-3.5 text-center">
          <span class="px-2 py-0.5 rounded font-bold bg-rose-100 text-rose-800 text-[11px]">
            Attend ${st.required_classes} classes
          </span>
        </td>
        <td class="px-4 py-3.5 text-right">
          <button onclick="sendWarningNotice(${st.student_id}, '${st.student_name}')" class="px-3 py-1.5 bg-rose-50 hover:bg-rose-100 border border-rose-200 text-rose-700 font-bold rounded-lg text-xs transition">
            Send Warning Notice
          </button>
        </td>
      </tr>
    `).join('');

  } catch (err) {
    console.error('Failed to load department low attendance:', err);
  }
}

async function sendWarningNotice(studentId, name) {
  if (!confirm(`Send official attendance shortage warning to ${name}?`)) return;

  try {
    const res = await API.post('/api/hod/send-warning', {
      student_id: studentId,
      message: 'Official HOD Notice: Your attendance is critically below the 75% requirement. Report to the HOD office immediately with your parents/guardian to explain the absence.'
    });

    showToast(res.message || 'Warning notice sent to student!', 'success');

  } catch (err) {
    showToast('Failed to send notice: ' + err.message, 'error');
  }
}

// 6. Setup HOD Tabs
function setupHodTabs() {
  const tabs = document.querySelectorAll('[data-hod-tab-target]');
  tabs.forEach(t => {
    t.addEventListener('click', (e) => {
      e.preventDefault();
      const targetId = t.getAttribute('data-hod-tab-target');

      tabs.forEach(link => link.classList.remove('active'));
      t.classList.add('active');

      const views = document.querySelectorAll('.hod-tab-view');
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
