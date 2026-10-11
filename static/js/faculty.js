/**
 * SmartAttend - Faculty Portal Script
 * Subject management, attendance marking roster, and permission request review
 */

let facultyDashboardData = null;
let currentRoster = [];
let allBranches = [];
let allClasses = [];
let allFacultyStudents = [];
let currentClassRoster = [];
let lastCreatedCredentials = null;

document.addEventListener('DOMContentLoaded', async () => {
  await loadFacultyMasterData();
  await loadFacultyDashboard();
  await loadFacultyStudentsRoster();
  setupFacultyTabs();
  setupAttendanceMarkingListeners();
  setupStudentManagementListeners();
});

// 1. Load Faculty Dashboard
async function loadFacultyDashboard() {
  try {
    const data = await API.get('/api/faculty/dashboard');
    facultyDashboardData = data;

    document.getElementById('fac-kpi-subjects').textContent = data.assigned_subjects_count;
    document.getElementById('fac-kpi-students').textContent = data.total_students;
    document.getElementById('fac-kpi-pending').textContent = data.pending_requests_count;
    document.getElementById('fac-kpi-low').textContent = data.low_attendance_students_count;

    populateSubjectDropdowns(data.subjects);
    renderFacultyAllocatedSubjects(data.subjects);
    await loadFacultyPermissions();
    await loadFacultyLowAttendance();
    await loadFacultyAttendanceHistory();

  } catch (err) {
    showToast('Failed to load faculty dashboard: ' + err.message, 'error');
  }
}

// 2. Populate Assigned Subjects
function populateSubjectDropdowns(subjects) {
  const select = document.getElementById('att-subject-select');
  if (!select) return;

  select.innerHTML = `
    <option value="" disabled selected>-- Select an Assigned Subject --</option>
    ${subjects.map(s => `<option value="${s.id}">${s.subject_code} — ${s.subject_name} (${s.enrolled_count} Students)</option>`).join('')}
  `;

  // Set default date to today
  const dateInput = document.getElementById('att-date-input');
  if (dateInput && !dateInput.value) {
    dateInput.value = new Date().toISOString().split('T')[0];
  }
}

// 3. Setup Attendance Marking Listeners
function setupAttendanceMarkingListeners() {
  const loadBtn = document.getElementById('att-load-roster-btn');
  const subjectSelect = document.getElementById('att-subject-select');
  const dateInput = document.getElementById('att-date-input');
  const hourSelect = document.getElementById('att-hour-select');

  if (loadBtn) {
    loadBtn.addEventListener('click', loadClassRoster);
  }

  // Quick action buttons
  document.getElementById('roster-all-present')?.addEventListener('click', () => setAllAttendance('PRESENT'));
  document.getElementById('roster-all-absent')?.addEventListener('click', () => setAllAttendance('ABSENT'));

  // Save button
  document.getElementById('save-attendance-btn')?.addEventListener('click', saveAttendanceSession);
}

// 4. Load Class Roster for Attendance Marking
async function loadClassRoster() {
  const subjectId = document.getElementById('att-subject-select')?.value;
  const dateVal = document.getElementById('att-date-input')?.value;
  const hourVal = document.getElementById('att-hour-select')?.value;

  if (!subjectId || !dateVal || !hourVal) {
    showToast('Please select Subject, Date, and Class Hour.', 'warning');
    return;
  }

  const rosterContainer = document.getElementById('class-roster-section');
  const tbody = document.getElementById('roster-table-body');
  const banner = document.getElementById('roster-mode-banner');

  if (rosterContainer) rosterContainer.classList.remove('hidden');
  if (tbody) tbody.innerHTML = `<tr><td colspan="4" class="p-8 text-center text-xs text-slate-400">Loading student roster...</td></tr>`;

  try {
    const data = await API.get(`/api/faculty/subjects/${subjectId}/students?date=${dateVal}&hour=${hourVal}`);
    currentRoster = data.students || [];

    if (banner) {
      if (data.already_marked) {
        banner.className = 'p-3 rounded-xl border border-amber-200 bg-amber-50 text-amber-900 text-xs flex items-center justify-between mb-4';
        banner.innerHTML = `
          <div class="flex items-center gap-2">
            <span class="font-bold">ℹ Attendance Already Marked:</span>
            <span>You are editing an existing attendance session for ${formatDate(dateVal)} (Hour ${hourVal}).</span>
          </div>
          <span class="font-bold bg-amber-200 px-2 py-0.5 rounded text-[11px]">EDIT MODE</span>
        `;
      } else {
        banner.className = 'p-3 rounded-xl border border-blue-200 bg-blue-50 text-blue-900 text-xs flex items-center justify-between mb-4';
        banner.innerHTML = `
          <div class="flex items-center gap-2">
            <span class="font-bold">✓ New Session:</span>
            <span>Recording fresh attendance for ${formatDate(dateVal)} (Hour ${hourVal}). All students default to Present.</span>
          </div>
          <span class="font-bold bg-blue-200 px-2 py-0.5 rounded text-[11px]">NEW SESSION</span>
        `;
      }
    }

    renderRosterTable(currentRoster, data.already_marked);

  } catch (err) {
    showToast('Failed to load roster: ' + err.message, 'error');
  }
}

function renderRosterTable(students, alreadyMarked) {
  const tbody = document.getElementById('roster-table-body');
  if (!tbody) return;

  if (students.length === 0) {
    tbody.innerHTML = `<tr><td colspan="4" class="p-8 text-center text-xs text-slate-400">No students enrolled in this subject.</td></tr>`;
    return;
  }

  tbody.innerHTML = students.map((s, idx) => {
    // Default to present if not marked
    const status = s.current_status || 'PRESENT';
    const isPresent = status === 'PRESENT';
    const isAbsent = status === 'ABSENT';
    const isPermission = status === 'APPROVED_PERMISSION';

    return `
      <tr class="border-b border-slate-100 text-sm hover:bg-slate-50 transition" data-student-id="${s.student_id}">
        <td class="px-5 py-3.5 text-xs text-slate-400 font-mono-code">${idx + 1}</td>
        <td class="px-5 py-3.5 font-bold font-mono-code text-blue-700">${s.usn}</td>
        <td class="px-5 py-3.5 font-semibold text-slate-800">
          <div class="flex items-center gap-2">
            <div class="w-7 h-7 rounded-full bg-slate-200 text-slate-600 flex items-center justify-center font-bold text-xs">
              ${s.student_name[0]}
            </div>
            ${s.student_name}
            ${isPermission ? '<span class="ml-2 px-2 py-0.5 rounded text-[10px] font-bold bg-purple-100 text-purple-800">Excused Leave</span>' : ''}
          </div>
        </td>
        <td class="px-5 py-3.5 text-right">
          <div class="inline-flex rounded-lg border border-slate-200 p-0.5 bg-slate-100">
            <button type="button" onclick="setRowStatus(${s.student_id}, 'PRESENT')" id="btn-p-${s.student_id}" class="px-3 py-1 text-xs font-bold rounded-md transition ${isPresent ? 'bg-emerald-600 text-white shadow-sm' : 'text-slate-600 hover:text-slate-900'}">
              Present
            </button>
            <button type="button" onclick="setRowStatus(${s.student_id}, 'ABSENT')" id="btn-a-${s.student_id}" class="px-3 py-1 text-xs font-bold rounded-md transition ${isAbsent ? 'bg-rose-600 text-white shadow-sm' : 'text-slate-600 hover:text-slate-900'}">
              Absent
            </button>
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

function setRowStatus(studentId, newStatus) {
  const btnP = document.getElementById(`btn-p-${studentId}`);
  const btnA = document.getElementById(`btn-a-${studentId}`);

  if (newStatus === 'PRESENT') {
    btnP.className = 'px-3 py-1 text-xs font-bold rounded-md transition bg-emerald-600 text-white shadow-sm';
    btnA.className = 'px-3 py-1 text-xs font-bold rounded-md transition text-slate-600 hover:text-slate-900';
  } else {
    btnP.className = 'px-3 py-1 text-xs font-bold rounded-md transition text-slate-600 hover:text-slate-900';
    btnA.className = 'px-3 py-1 text-xs font-bold rounded-md transition bg-rose-600 text-white shadow-sm';
  }

  const s = currentRoster.find(item => item.student_id === studentId);
  if (s) s.current_status = newStatus;
}

function setAllAttendance(status) {
  currentRoster.forEach(s => {
    s.current_status = status;
    setRowStatus(s.student_id, status);
  });
  showToast(`Marked all as ${status}`, 'info', 2000);
}

// 5. Save Attendance Session
async function saveAttendanceSession() {
  const subjectId = document.getElementById('att-subject-select')?.value;
  const dateVal = document.getElementById('att-date-input')?.value;
  const hourVal = parseInt(document.getElementById('att-hour-select')?.value || 1);
  const saveBtn = document.getElementById('save-attendance-btn');

  if (!subjectId || !dateVal || currentRoster.length === 0) {
    showToast('No roster loaded to save.', 'warning');
    return;
  }

  if (saveBtn) {
    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving Attendance...';
  }

  const records = currentRoster.map(s => ({
    student_id: s.student_id,
    status: s.current_status || 'PRESENT'
  }));

  try {
    const res = await API.post('/api/faculty/attendance', {
      subject_id: parseInt(subjectId),
      date: dateVal,
      hour: hourVal,
      records: records
    });

    showToast(res.message || 'Attendance saved successfully!', 'success');
    await loadFacultyDashboard();

  } catch (err) {
    showToast('Error saving attendance: ' + err.message, 'error');
  } finally {
    if (saveBtn) {
      saveBtn.disabled = false;
      saveBtn.textContent = 'Save Attendance';
    }
  }
}

// 6. Faculty Permission Management
async function loadFacultyPermissions() {
  const tbody = document.getElementById('faculty-permissions-table-body');
  if (!tbody) return;

  try {
    const data = await API.get('/api/faculty/permissions');
    const requests = data.requests || [];

    if (requests.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" class="p-8 text-center text-xs text-slate-400">No permission requests submitted for your subjects.</td></tr>`;
      return;
    }

    tbody.innerHTML = requests.map(pr => {
      let statusBadge = '';
      if (pr.status === 'APPROVED') statusBadge = '<span class="px-2 py-0.5 rounded text-xs font-semibold bg-emerald-100 text-emerald-800">Approved</span>';
      else if (pr.status === 'PENDING') statusBadge = '<span class="px-2 py-0.5 rounded text-xs font-semibold bg-amber-100 text-amber-800">Pending</span>';
      else if (pr.status === 'ESCALATED_HOD') statusBadge = '<span class="px-2 py-0.5 rounded text-xs font-semibold bg-purple-100 text-purple-800">Escalated to HOD</span>';
      else if (pr.status === 'REJECTED') statusBadge = '<span class="px-2 py-0.5 rounded text-xs font-semibold bg-rose-100 text-rose-800">Rejected</span>';

      const isPending = pr.status === 'PENDING' || pr.status === 'UNDER_REVIEW';

      return `
        <tr class="border-b border-slate-100 text-xs hover:bg-slate-50 transition">
          <td class="px-4 py-3.5 font-bold font-mono-code text-blue-700">${pr.request_code}</td>
          <td class="px-4 py-3.5">
            <div class="font-bold text-slate-800">${pr.student_name}</div>
            <div class="text-[11px] text-slate-500 font-mono-code">${pr.usn}</div>
          </td>
          <td class="px-4 py-3.5 font-semibold text-slate-700">${pr.subject_code}</td>
          <td class="px-4 py-3.5 text-slate-600">${formatDate(pr.date)} (Hr ${pr.hour})</td>
          <td class="px-4 py-3.5 font-medium text-slate-800">${pr.reason}</td>
          <td class="px-4 py-3.5 text-center">${statusBadge}</td>
          <td class="px-4 py-3.5 text-right">
            <button onclick='openFacultyReviewModal(${JSON.stringify(pr)})' class="px-3 py-1.5 ${isPending ? 'bg-blue-600 hover:bg-blue-700 text-white' : 'bg-slate-100 hover:bg-slate-200 text-slate-700'} font-semibold rounded-lg text-xs transition">
              ${isPending ? 'Review & Decide' : 'View'}
            </button>
          </td>
        </tr>
      `;
    }).join('');

  } catch (err) {
    console.error('Failed to load faculty permissions:', err);
  }
}

// 7. Review Permission Modal & Workflow Actions
let activeReviewRequest = null;

function openFacultyReviewModal(pr) {
  activeReviewRequest = pr;
  const modal = document.getElementById('faculty-review-modal');
  const title = document.getElementById('fac-review-title');
  const detailsBox = document.getElementById('fac-review-details');
  const commentInput = document.getElementById('fac-review-comment');
  const actionButtons = document.getElementById('fac-review-actions');

  if (title) title.textContent = `Review Request: ${pr.request_code}`;
  if (commentInput) commentInput.value = pr.faculty_comment || '';

  let docBtn = '<span class="text-xs text-slate-400 italic">No document attached</span>';
  if (pr.document_filename) {
    docBtn = `
      <a href="/api/files/${pr.document_filename}" target="_blank" class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-50 border border-blue-200 text-blue-700 text-xs font-semibold hover:bg-blue-100 transition">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path></svg>
        Open Document (${pr.document_original_name || 'Document'})
      </a>
    `;
  }

  if (detailsBox) {
    detailsBox.innerHTML = `
      <div class="grid grid-cols-2 gap-3 p-3 bg-slate-50 rounded-xl border border-slate-100 text-xs">
        <div><span class="text-slate-500">Student:</span> <strong class="text-slate-800">${pr.student_name} (${pr.usn})</strong></div>
        <div><span class="text-slate-500">Subject:</span> <strong class="text-slate-800">${pr.subject_code} — ${pr.subject_name}</strong></div>
        <div><span class="text-slate-500">Date & Hour:</span> <strong class="text-slate-800">${formatDate(pr.date)}, Hour ${pr.hour}</strong></div>
        <div><span class="text-slate-500">Status:</span> <strong class="text-blue-700">${pr.status}</strong></div>
      </div>
      <div>
        <span class="font-bold text-xs text-slate-700 block mb-1">Reason: ${pr.reason}</span>
        <div class="p-3 bg-white border border-slate-200 rounded-xl text-xs text-slate-800 leading-relaxed">${pr.description}</div>
      </div>
      <div>
        <span class="font-bold text-xs text-slate-700 block mb-1">Supporting Document:</span>
        ${docBtn}
      </div>
    `;
  }

  const isPending = pr.status === 'PENDING' || pr.status === 'UNDER_REVIEW';
  if (actionButtons) {
    if (isPending) {
      actionButtons.innerHTML = `
        <button onclick="submitFacultyDecision('APPROVE')" class="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded-lg shadow-sm transition">
          ✓ Approve Request
        </button>
        <button onclick="submitFacultyDecision('ESCALATE')" class="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white text-xs font-bold rounded-lg shadow-sm transition">
          ⬆ Escalate to HOD
        </button>
        <button onclick="submitFacultyDecision('REJECT')" class="px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold rounded-lg shadow-sm transition">
          ✗ Reject
        </button>
      `;
    } else {
      actionButtons.innerHTML = `
        <span class="text-xs text-slate-500 italic mr-auto">This request has already been finalized (${pr.status}).</span>
        <button onclick="closeModal('faculty-review-modal')" class="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold rounded-lg transition">
          Close
        </button>
      `;
    }
  }

  openModal('faculty-review-modal');
}

async function submitFacultyDecision(action) {
  if (!activeReviewRequest) return;
  const comment = document.getElementById('fac-review-comment')?.value.trim() || '';

  if ((action === 'REJECT' || action === 'ESCALATE') && !comment) {
    showToast('A comment is required when rejecting or escalating.', 'warning');
    return;
  }

  try {
    const res = await API.post(`/api/faculty/permissions/${activeReviewRequest.id}/review`, {
      action: action,
      comment: comment
    });

    showToast(res.message || 'Decision recorded successfully', 'success');
    closeModal('faculty-review-modal');
    await loadFacultyDashboard();

  } catch (err) {
    showToast(err.message || 'Action failed', 'error');
  }
}

// 8. Low Attendance Students List
async function loadFacultyLowAttendance() {
  const tbody = document.getElementById('faculty-low-table-body');
  if (!tbody) return;

  try {
    const data = await API.get('/api/faculty/low-attendance');
    const students = data.low_attendance_students || [];

    if (students.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" class="p-8 text-center text-xs text-emerald-600 font-medium">All students currently meet the 75% attendance threshold.</td></tr>`;
      return;
    }

    tbody.innerHTML = students.map(st => `
      <tr class="border-b border-slate-100 text-xs hover:bg-slate-50">
        <td class="px-4 py-3 font-bold font-mono-code text-rose-700">${st.usn}</td>
        <td class="px-4 py-3 font-semibold text-slate-800">${st.student_name}</td>
        <td class="px-4 py-3 font-medium text-slate-700">${st.subject_code}</td>
        <td class="px-4 py-3 text-center text-slate-600">${st.attended} / ${st.conducted}</td>
        <td class="px-4 py-3 text-center font-bold text-rose-600">${st.percentage}%</td>
        <td class="px-4 py-3 text-center">
          <span class="px-2 py-0.5 rounded font-bold bg-rose-100 text-rose-800 text-[11px]">
            Attend ${st.required_classes} classes
          </span>
        </td>
      </tr>
    `).join('');

  } catch (err) {
    console.error('Failed to load low attendance students:', err);
  }
}

// 9. Attendance Marking History
async function loadFacultyAttendanceHistory() {
  // Stub for sessions list if element present
}

// 10. Tab Switching for Faculty
function setupFacultyTabs() {
  const tabs = document.querySelectorAll('[data-fac-tab-target]');
  tabs.forEach(t => {
    t.addEventListener('click', (e) => {
      e.preventDefault();
      const targetId = t.getAttribute('data-fac-tab-target');

      tabs.forEach(link => link.classList.remove('active'));
      t.classList.add('active');

      const views = document.querySelectorAll('.fac-tab-view');
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

// 11. Master Data (Branches & Classes)
async function loadFacultyMasterData() {
  try {
    const [branchData, classData] = await Promise.all([
      API.get('/api/branches'),
      API.get('/api/classes')
    ]);
    allBranches = branchData.branches || [];
    allClasses = classData.classes || [];

    populateBranchSelects();
    populateClassSelects();
  } catch (err) {
    console.error('Failed to load master data:', err);
  }
}

function populateBranchSelects() {
  const stBranchSel = document.getElementById('new-st-branch');
  const allocBranchSel = document.getElementById('alloc-subj-branch');

  const options = allBranches.map(b => `<option value="${b.id}">${b.branch_name} (${b.branch_code})</option>`).join('');

  if (stBranchSel) {
    stBranchSel.innerHTML = `<option value="" disabled selected>-- Select Academic Branch --</option>` + options;
  }
  if (allocBranchSel) {
    allocBranchSel.innerHTML = `<option value="" disabled selected>-- Select Department Branch --</option>` + options;
  }
}

function populateClassSelects() {
  const classFilter = document.getElementById('fac-student-class-filter');
  const allocClassSelect = document.getElementById('alloc-class-select');

  const filterOpts = `<option value="">All Enrolled Students</option>` +
    allClasses.map(c => `<option value="${c.id}">${c.class_name} (${c.branch_code} Sem ${c.semester}-${c.section})</option>`).join('');

  const allocOpts = `<option value="" disabled selected>-- Select Class to Allocate --</option>` +
    allClasses.map(c => `<option value="${c.id}">${c.class_name} (${c.branch_code} Sem ${c.semester}-${c.section})</option>`).join('');

  if (classFilter) classFilter.innerHTML = filterOpts;
  if (allocClassSelect) allocClassSelect.innerHTML = allocOpts;
}

// 12. Student Enrollment & Directory
async function loadFacultyStudentsRoster() {
  const tbody = document.getElementById('fac-students-table-body');
  if (!tbody) return;

  try {
    const data = await API.get('/api/faculty/students');
    allFacultyStudents = data.students || [];
    renderFacultyStudentsTable(allFacultyStudents);
  } catch (err) {
    console.error('Failed to load students roster:', err);
  }
}

function renderFacultyStudentsTable(students) {
  const tbody = document.getElementById('fac-students-table-body');
  if (!tbody) return;

  if (students.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="p-8 text-center text-slate-400">No students enrolled yet. Click "+ Add New Student" to onboard.</td></tr>`;
    return;
  }

  tbody.innerHTML = students.map(st => `
    <tr class="hover:bg-slate-50 transition border-b border-slate-100">
      <td class="px-4 py-3 font-mono-code font-bold text-brand-900">${st.usn}</td>
      <td class="px-4 py-3 font-semibold text-slate-900">${st.name}</td>
      <td class="px-4 py-3 font-mono text-slate-600">${st.roll_no || '--'}</td>
      <td class="px-4 py-3 text-slate-700">${st.branch_name || st.branch_code || '--'}</td>
      <td class="px-4 py-3"><span class="px-2 py-0.5 rounded-md bg-blue-50 text-blue-700 font-bold text-[10px]">${st.class_name || `Sem ${st.semester}-${st.section}`}</span></td>
      <td class="px-4 py-3 text-slate-600">${st.email}</td>
      <td class="px-4 py-3 text-center"><span class="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 font-bold text-[10px]">${st.status || 'ACTIVE'}</span></td>
    </tr>
  `).join('');
}

function filterFacultyStudents() {
  const query = document.getElementById('fac-student-search-input')?.value.toLowerCase().trim() || '';
  const classFilter = document.getElementById('fac-student-class-filter')?.value;

  const filtered = allFacultyStudents.filter(st => {
    const matchesSearch = !query || st.name.toLowerCase().includes(query) || st.usn.toLowerCase().includes(query) || st.email.toLowerCase().includes(query);
    const matchesClass = !classFilter || String(st.class_id) === String(classFilter);
    return matchesSearch && matchesClass;
  });

  renderFacultyStudentsTable(filtered);
}

// 13. Subject Allocation Tab & Cards
function renderFacultyAllocatedSubjects(subjects) {
  const grid = document.getElementById('fac-allocated-subjects-grid');
  if (!grid) return;

  const subjs = subjects || facultyDashboardData?.subjects || [];
  if (subjs.length === 0) {
    grid.innerHTML = `<div class="col-span-full p-8 text-center text-slate-400 border border-dashed rounded-2xl">No subjects allocated yet. Click "+ Allocate Subject to Class".</div>`;
    return;
  }

  grid.innerHTML = subjs.map(s => `
    <div class="erp-card p-5 bg-white border border-slate-200 hover:shadow-md transition space-y-3">
      <div class="flex items-start justify-between">
        <div>
          <span class="px-2 py-0.5 rounded font-mono font-bold bg-brand-100 text-brand-800 text-[10px]">${s.subject_code}</span>
          <h4 class="text-sm font-bold text-slate-900 mt-1">${s.subject_name}</h4>
        </div>
        <span class="px-2 py-0.5 rounded-full font-bold bg-emerald-50 text-emerald-700 text-[10px]">${s.subject_type || 'THEORY'}</span>
      </div>
      <div class="grid grid-cols-2 gap-2 text-[11px] text-slate-600 bg-slate-50 p-2.5 rounded-xl border border-slate-100">
        <div>Class: <strong class="text-slate-800">${s.class_name || '--'}</strong></div>
        <div>Credits: <strong class="text-slate-800">${s.credits || 4}</strong></div>
        <div>Enrolled: <strong class="text-blue-700 font-bold">${s.enrolled_count || 0} Students</strong></div>
        <div>Min Attendance: <strong class="text-amber-700 font-bold">${s.minimum_attendance || 75}%</strong></div>
      </div>
      <div class="pt-2 border-t border-slate-100 flex items-center justify-between text-xs">
        <span class="text-[11px] text-slate-400">AY: ${s.academic_year || '2026-2027'}</span>
        <button onclick="selectSubjectForAttendance(${s.id})" class="text-brand-600 hover:text-brand-800 font-bold text-xs flex items-center gap-1">
          Mark Attendance →
        </button>
      </div>
    </div>
  `).join('');
}

function selectSubjectForAttendance(subjectId) {
  const sel = document.getElementById('att-subject-select');
  if (sel) {
    sel.value = subjectId;
  }
  const tabBtn = document.querySelector('[data-fac-tab-target="fac-tab-mark"]');
  if (tabBtn) tabBtn.click();
}

// 14. Modals & Action Handlers
function openAddStudentModal() {
  document.getElementById('fac-add-student-form')?.reset();
  document.getElementById('add-student-error')?.classList.add('hidden');
  generateRandomTempPassword();
  openModal('faculty-add-student-modal');
}

function generateRandomTempPassword() {
  const specialChars = "!@#$%^&*";
  const num = Math.floor(100 + Math.random() * 900);
  const spec = specialChars[Math.floor(Math.random() * specialChars.length)];
  const pwd = `Smart@${num}${spec}`;
  const pwdInput = document.getElementById('new-st-pwd');
  if (pwdInput) pwdInput.value = pwd;
}

function openAddBranchModal() {
  document.getElementById('fac-add-branch-form')?.reset();
  document.getElementById('add-branch-error')?.classList.add('hidden');
  openModal('faculty-add-branch-modal');
}

function displayCredentialsModal(cred) {
  lastCreatedCredentials = cred;
  document.getElementById('cred-name').textContent = cred.name;
  document.getElementById('cred-usn').textContent = cred.usn;
  document.getElementById('cred-email').textContent = cred.email;
  document.getElementById('cred-password').textContent = cred.temporary_password;
  document.getElementById('cred-branch').textContent = cred.branch_name || cred.branch_code || 'Assigned';
  document.getElementById('cred-class').textContent = cred.class_name || `Sem ${cred.semester}-${cred.section}`;

  openModal('student-credentials-modal');
}

function copyCredentialsToClipboard() {
  if (!lastCreatedCredentials) return;
  const text = `SmartAttend ERP — Student Credentials\nName: ${lastCreatedCredentials.name}\nUSN: ${lastCreatedCredentials.usn}\nEmail: ${lastCreatedCredentials.email}\nTemporary Password: ${lastCreatedCredentials.temporary_password}\nPortal: ${window.location.origin}/`;
  navigator.clipboard.writeText(text).then(() => {
    showToast('Credentials copied to clipboard!', 'success');
  }).catch(() => {
    showToast('Failed to copy to clipboard', 'warning');
  });
}

function openAllocateSubjectModal() {
  document.getElementById('fac-allocate-subject-form')?.reset();
  document.getElementById('alloc-subject-error')?.classList.add('hidden');
  document.getElementById('alloc-students-container')?.classList.add('hidden');
  openModal('faculty-allocate-subject-modal');
}

async function handleClassSelectForAllocation(classId) {
  const container = document.getElementById('alloc-students-container');
  const tbody = document.getElementById('alloc-students-table-body');
  if (!container || !tbody) return;

  container.classList.remove('hidden');
  tbody.innerHTML = `<tr><td colspan="4" class="p-4 text-center text-slate-400">Loading class roster...</td></tr>`;

  try {
    const data = await API.get(`/api/classes/${classId}/students`);
    currentClassRoster = data.students || [];

    if (currentClassRoster.length === 0) {
      tbody.innerHTML = `<tr><td colspan="4" class="p-4 text-center text-slate-400">No students currently enrolled in this class.</td></tr>`;
      updateAllocSelectedCount();
      return;
    }

    tbody.innerHTML = currentClassRoster.map(st => `
      <tr class="hover:bg-slate-50 transition alloc-st-row" data-st-usn="${st.usn}" data-st-name="${st.name.toLowerCase()}">
        <td class="p-2 text-center">
          <input type="checkbox" name="alloc-student-checkbox" value="${st.id}" checked onchange="updateAllocSelectedCount()" class="rounded border-slate-300 text-brand-600 focus:ring-brand-500">
        </td>
        <td class="p-2 font-mono font-bold text-brand-900">${st.usn}</td>
        <td class="p-2 font-semibold text-slate-800">${st.name}</td>
        <td class="p-2 text-slate-600">${st.roll_no || '--'}</td>
      </tr>
    `).join('');

    const selectAllCb = document.getElementById('alloc-select-all');
    if (selectAllCb) selectAllCb.checked = true;
    updateAllocSelectedCount();

  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="4" class="p-4 text-center text-rose-600 font-bold">Failed to load class students: ${err.message}</td></tr>`;
  }
}

function toggleSelectAllAllocStudents(checked) {
  const checkboxes = document.querySelectorAll('input[name="alloc-student-checkbox"]');
  checkboxes.forEach(cb => {
    const row = cb.closest('tr');
    if (row && !row.classList.contains('hidden')) {
      cb.checked = checked;
    }
  });
  updateAllocSelectedCount();
}

function filterAllocClassStudents() {
  const query = document.getElementById('alloc-student-search')?.value.toLowerCase().trim() || '';
  const rows = document.querySelectorAll('.alloc-st-row');
  rows.forEach(r => {
    const usn = r.getAttribute('data-st-usn').toLowerCase();
    const name = r.getAttribute('data-st-name').toLowerCase();
    if (!query || usn.includes(query) || name.includes(query)) {
      r.classList.remove('hidden');
    } else {
      r.classList.add('hidden');
    }
  });
}

function updateAllocSelectedCount() {
  const checked = document.querySelectorAll('input[name="alloc-student-checkbox"]:checked');
  const badge = document.getElementById('alloc-selected-count-badge');
  if (badge) {
    badge.textContent = `${checked.length} of ${currentClassRoster.length} selected`;
  }
}

// 15. Form Submission Event Listeners
function setupStudentManagementListeners() {
  // Add Student Form
  const addStudentForm = document.getElementById('fac-add-student-form');
  if (addStudentForm) {
    addStudentForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const errEl = document.getElementById('add-student-error');
      const submitBtn = document.getElementById('fac-submit-student-btn');

      errEl.classList.add('hidden');
      submitBtn.disabled = true;
      submitBtn.textContent = 'Creating Account...';

      const payload = {
        name: document.getElementById('new-st-name').value.trim(),
        usn: document.getElementById('new-st-usn').value.trim().toUpperCase(),
        email: document.getElementById('new-st-email').value.trim(),
        temporary_password: document.getElementById('new-st-pwd').value,
        phone: document.getElementById('new-st-phone').value.trim(),
        branch_id: parseInt(document.getElementById('new-st-branch').value),
        semester: parseInt(document.getElementById('new-st-sem').value),
        section: document.getElementById('new-st-sec').value,
        roll_no: document.getElementById('new-st-roll').value.trim(),
        academic_year: document.getElementById('new-st-year').value.trim()
      };

      try {
        const res = await API.post('/api/faculty/students', payload);
        closeModal('faculty-add-student-modal');
        displayCredentialsModal(res.student_credentials);
        await loadFacultyStudentsRoster();
        await loadFacultyDashboard();
        showToast('Student account created successfully!', 'success');
      } catch (err) {
        errEl.textContent = err.message || 'Failed to create student account.';
        errEl.classList.remove('hidden');
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Create Student Account';
      }
    });
  }

  // Add Branch Form
  const addBranchForm = document.getElementById('fac-add-branch-form');
  if (addBranchForm) {
    addBranchForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const errEl = document.getElementById('add-branch-error');
      const submitBtn = document.getElementById('fac-submit-branch-btn');

      errEl.classList.add('hidden');
      submitBtn.disabled = true;
      submitBtn.textContent = 'Adding Branch...';

      const payload = {
        branch_name: document.getElementById('new-branch-name').value.trim(),
        branch_code: document.getElementById('new-branch-code').value.trim().toUpperCase()
      };

      try {
        const res = await API.post('/api/branches', payload);
        const newBranch = res.branch;
        
        // Add to branches array if not already present
        if (!allBranches.some(b => b.id === newBranch.id)) {
          allBranches.push(newBranch);
        }

        populateBranchSelects();

        // Select the newly added branch in student modal
        const stBranchSel = document.getElementById('new-st-branch');
        if (stBranchSel) stBranchSel.value = newBranch.id;

        closeModal('faculty-add-branch-modal');
        showToast(`Branch "${newBranch.branch_name}" added successfully!`, 'success');
      } catch (err) {
        errEl.textContent = err.message || 'Failed to add branch.';
        errEl.classList.remove('hidden');
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Add Branch to System';
      }
    });
  }

  // Allocate Subject Form
  const allocSubjectForm = document.getElementById('fac-allocate-subject-form');
  if (allocSubjectForm) {
    allocSubjectForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const errEl = document.getElementById('alloc-subject-error');
      const submitBtn = document.getElementById('fac-submit-alloc-btn');

      const classId = document.getElementById('alloc-class-select').value;
      if (!classId) {
        errEl.textContent = 'Please select a target class.';
        errEl.classList.remove('hidden');
        return;
      }

      errEl.classList.add('hidden');
      submitBtn.disabled = true;
      submitBtn.textContent = 'Allocating Subject...';

      const subjectPayload = {
        subject_code: document.getElementById('alloc-subj-code').value.trim().toUpperCase(),
        subject_name: document.getElementById('alloc-subj-name').value.trim(),
        subject_type: document.getElementById('alloc-subj-type').value,
        credits: parseInt(document.getElementById('alloc-subj-credits').value) || 4,
        minimum_attendance: parseFloat(document.getElementById('alloc-subj-min-pct').value) || 75.0,
        branch_id: parseInt(document.getElementById('alloc-subj-branch').value),
        class_id: parseInt(classId),
        semester: parseInt(document.getElementById('alloc-subj-sem').value),
        section: document.getElementById('alloc-subj-sec').value,
        planned_classes: parseInt(document.getElementById('alloc-subj-hours').value) || 45,
        description: document.getElementById('alloc-subj-desc').value.trim(),
        academic_year: '2026-2027'
      };

      try {
        const res = await API.post('/api/faculty/subjects', subjectPayload);
        const subjectId = res.subject_id;

        // Assign checked students
        const checkedStudents = Array.from(document.querySelectorAll('input[name="alloc-student-checkbox"]:checked'))
          .map(cb => parseInt(cb.value));

        if (checkedStudents.length > 0) {
          await API.post(`/api/faculty/subjects/${subjectId}/assign-students`, {
            student_ids: checkedStudents
          });
        }

        closeModal('faculty-allocate-subject-modal');
        await loadFacultyDashboard();
        showToast('Subject allocated and students enrolled successfully!', 'success');
      } catch (err) {
        errEl.textContent = err.message || 'Failed to allocate subject.';
        errEl.classList.remove('hidden');
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Allocate Subject & Enroll Students';
      }
    });
  }
}
