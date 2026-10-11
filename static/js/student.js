/**
 * SmartAttend - Student Portal Script
 * Dashboard, Required Classes Calculator, Calendar, and Permission Portal
 */

let studentDashboardData = null;
let currentSelectedSubject = null;

document.addEventListener('DOMContentLoaded', async () => {
  await loadStudentDashboard();
  await loadUserProfile();
  await loadSecurityActivity();
  setupNavigationTabs();
  setupCalculatorListeners();
  setupPermissionForm();
  await loadMissedClassesForPermission();
  setupPasswordChangeForm();
});

// 1. Load Complete Dashboard Data
async function loadStudentDashboard() {
  try {
    const data = await API.get('/api/student/dashboard');
    studentDashboardData = data;

    renderStudentHeader(data.student);
    renderAmISafeBanner(data.overall, data.subjects);
    renderKpiCards(data.overall);
    renderLowAttendanceWarning(data.subjects, data.overall.minimum_required);
    renderSubjectsTable(data.subjects);
    renderRecentPermissions(data.recent_permissions);
    populateCalculatorSubjectDropdown(data.subjects, data.overall);
    updateCalculatorMath();
    await loadAttendanceCalendar();
    await loadPermissionRequestsTable();

  } catch (err) {
    showToast('Failed to load student dashboard: ' + err.message, 'error');
  }
}

// 2. Student Header & Profile Details
function renderStudentHeader(student) {
  const nameEl = document.getElementById('student-welcome-name');
  const detailsEl = document.getElementById('student-meta-details');
  if (nameEl) nameEl.textContent = `Welcome back, ${student.name}`;
  if (detailsEl) {
    detailsEl.textContent = `USN: ${student.usn} • ${student.department_code} • Sem ${student.semester} - Sec ${student.section} • AY ${student.academic_year}`;
  }

  // Top pill
  const topName = document.getElementById('top-profile-name');
  const topUsn = document.getElementById('top-profile-usn');
  const topAvatar = document.getElementById('top-profile-avatar');
  const initials = student.name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();

  if (topName) topName.textContent = student.name;
  if (topUsn) topUsn.textContent = student.usn;
  if (topAvatar) topAvatar.textContent = initials;

  // Profile Card
  const profName = document.getElementById('profile-card-name');
  const profUsn = document.getElementById('profile-card-usn');
  const profEmail = document.getElementById('profile-card-email');
  const profDept = document.getElementById('profile-card-dept');
  const profClass = document.getElementById('profile-card-class');
  const profSemSec = document.getElementById('profile-card-sem-sec');
  const profRoll = document.getElementById('profile-card-roll');
  const profAy = document.getElementById('profile-card-ay');
  const profInitials = document.getElementById('profile-card-initials');

  if (profName) profName.textContent = student.name;
  if (profUsn) profUsn.textContent = student.usn;
  if (profEmail) profEmail.textContent = student.email || `${student.usn.toLowerCase()}@college.edu`;
  if (profDept) profDept.textContent = student.department_name || student.department_code || student.branch_name || 'Department of Engineering';
  if (profClass) profClass.textContent = student.class_name || `Sem ${student.semester} - Sec ${student.section}`;
  if (profSemSec) profSemSec.textContent = `Semester ${student.semester} - Section ${student.section}`;
  if (profRoll) profRoll.textContent = student.roll_no || '--';
  if (profAy) profAy.textContent = student.academic_year || '2026-2027';
  if (profInitials) profInitials.textContent = initials;
}

// 3. "Am I Safe?" Attendance Status Banner
function renderAmISafeBanner(overall, subjects) {
  const container = document.getElementById('am-i-safe-banner');
  if (!container) return;

  const lowSubjects = subjects.filter(s => s.percentage < overall.minimum_required);
  const isOverallSafe = overall.percentage >= overall.minimum_required;
  const isCompletelySafe = isOverallSafe && lowSubjects.length === 0;

  let bannerClass = '';
  let badgeClass = '';
  let icon = '';
  let headline = '';
  let subline = '';
  let actionHtml = '';

  if (isCompletelySafe) {
    bannerClass = 'bg-gradient-to-r from-emerald-500/10 via-teal-500/10 to-emerald-500/5 border-emerald-300';
    badgeClass = 'bg-emerald-600 text-white';
    icon = '✓';
    headline = `ATTENDANCE STATUS: SAFE (${overall.percentage}%)`;
    subline = `Your overall attendance meets institutional requirements. You can miss up to ${overall.missable_classes} classes without falling below ${overall.minimum_required}%.`;
    actionHtml = `
      <button onclick="switchToTab('tab-subjects')" class="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded-lg shadow-sm transition">
        View Subjects
      </button>
    `;
  } else if (!isOverallSafe) {
    bannerClass = 'bg-gradient-to-r from-rose-500/15 via-red-500/10 to-rose-500/5 border-rose-300';
    badgeClass = 'bg-rose-600 text-white';
    icon = '⚠';
    headline = `ATTENDANCE STATUS: CRITICAL — BELOW MINIMUM (${overall.percentage}%)`;
    subline = `Your overall attendance is below the mandatory ${overall.minimum_required}%. You must attend at least ${overall.required_classes} consecutive classes to regain eligibility.`;
    actionHtml = `
      <button onclick="switchToTab('tab-calculator')" class="px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold rounded-lg shadow-sm transition">
        Calculate Recovery Plan
      </button>
      <button onclick="openPermissionModal()" class="px-4 py-2 bg-white border border-rose-300 hover:bg-rose-50 text-rose-700 text-xs font-semibold rounded-lg shadow-sm transition">
        Request Permission
      </button>
    `;
  } else {
    // Overall safe, but has subject-specific shortfall (e.g. Java CS502)
    const worst = lowSubjects[0];
    bannerClass = 'bg-gradient-to-r from-amber-500/15 via-orange-500/10 to-amber-500/5 border-amber-300';
    badgeClass = 'bg-amber-600 text-white';
    icon = '⚠';
    headline = `ATTENDANCE STATUS: ATTENTION NEEDED (${lowSubjects.length} Subject Below ${overall.minimum_required}%)`;
    subline = `Overall is ${overall.percentage}%, but ${worst.subject_code} (${worst.subject_name}) is at ${worst.percentage}%. You need ${worst.required_classes} consecutive classes in ${worst.subject_code} to reach ${overall.minimum_required}%.`;
    actionHtml = `
      <button onclick="switchToTab('tab-calculator')" class="px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold rounded-lg shadow-sm transition">
        View Required Classes
      </button>
      <button onclick="openPermissionModal()" class="px-4 py-2 bg-white border border-amber-300 hover:bg-amber-50 text-amber-800 text-xs font-semibold rounded-lg shadow-sm transition">
        Submit Permission
      </button>
    `;
  }

  container.className = `p-5 rounded-2xl border ${bannerClass} transition-all duration-300 shadow-sm`;
  container.innerHTML = `
    <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
      <div class="flex items-start gap-4">
        <div class="w-11 h-11 rounded-xl ${badgeClass} flex items-center justify-center font-bold text-lg shrink-0 shadow-sm">
          ${icon}
        </div>
        <div>
          <div class="flex items-center gap-2">
            <h3 class="text-base font-bold text-slate-900">${headline}</h3>
            <span class="text-[11px] font-semibold uppercase px-2 py-0.5 rounded-full ${badgeClass} tracking-wide">
              Threshold: ${overall.minimum_required}%
            </span>
          </div>
          <p class="text-xs text-slate-700 mt-1 max-w-2xl leading-relaxed">${subline}</p>
        </div>
      </div>
      <div class="flex items-center gap-2.5 shrink-0">
        ${actionHtml}
      </div>
    </div>
  `;
}

// 4. KPI Attendance Cards
function renderKpiCards(overall) {
  document.getElementById('kpi-overall-pct').textContent = `${overall.percentage}%`;
  document.getElementById('kpi-conducted').textContent = overall.conducted;
  document.getElementById('kpi-attended').textContent = overall.attended;
  document.getElementById('kpi-absent').textContent = overall.absent;
  document.getElementById('kpi-min-req').textContent = `${overall.minimum_required}%`;
  
  const reqEl = document.getElementById('kpi-required-classes');
  if (reqEl) {
    if (overall.required_classes > 0) {
      reqEl.textContent = overall.required_classes;
      reqEl.className = 'text-2xl font-bold text-rose-600';
    } else {
      reqEl.textContent = '0 (Safe)';
      reqEl.className = 'text-2xl font-bold text-emerald-600';
    }
  }

  // Progress Bar
  const pbar = document.getElementById('overall-progress-bar');
  if (pbar) {
    pbar.style.width = `${Math.min(100, overall.percentage)}%`;
    pbar.className = overall.percentage >= overall.minimum_required
      ? 'h-2 rounded-full bg-emerald-500 transition-all duration-500'
      : 'h-2 rounded-full bg-rose-500 transition-all duration-500';
  }
}

// 5. Low Attendance Alert Banner for Defaulter Subjects
function renderLowAttendanceWarning(subjects, minPct) {
  const container = document.getElementById('low-attendance-alert-container');
  if (!container) return;

  const lowSubjects = subjects.filter(s => s.percentage < minPct);
  if (lowSubjects.length === 0) {
    container.classList.add('hidden');
    return;
  }

  container.classList.remove('hidden');
  container.innerHTML = lowSubjects.map(sub => `
    <div class="p-4 rounded-xl border border-rose-200 bg-rose-50/70 flex flex-col md:flex-row md:items-center justify-between gap-3">
      <div class="flex items-start gap-3">
        <div class="w-8 h-8 rounded-lg bg-rose-100 text-rose-700 flex items-center justify-center font-bold text-sm shrink-0">
          ⚠
        </div>
        <div>
          <h4 class="text-sm font-bold text-rose-900">
            LOW ATTENDANCE: ${sub.subject_code} — ${sub.subject_name}
          </h4>
          <p class="text-xs text-rose-700 mt-0.5">
            Current: <strong class="font-bold">${sub.percentage}%</strong> (${sub.attended}/${sub.conducted} classes). 
            Minimum required: <strong class="font-bold">${minPct}%</strong>.
            <span class="inline-block font-semibold bg-rose-200/60 text-rose-900 px-1.5 py-0.5 rounded ml-1">
              ⚠ You need to attend at least ${sub.required_classes} consecutive classes to reach ${minPct}%.
            </span>
          </p>
        </div>
      </div>
      <div class="flex items-center gap-2 shrink-0">
        <button onclick="selectSubjectInCalculator('${sub.subject_id}')" class="px-3 py-1.5 bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold rounded-lg shadow-sm transition">
          Simulate ${sub.subject_code}
        </button>
        <button onclick="openPermissionModalWithSubject('${sub.subject_id}')" class="px-3 py-1.5 bg-white border border-rose-300 text-rose-700 hover:bg-rose-100 text-xs font-semibold rounded-lg transition">
          Request Permission
        </button>
      </div>
    </div>
  `).join('');
}

// 6. Subject-Wise Attendance Table
function renderSubjectsTable(subjects) {
  const tbody = document.getElementById('subjects-table-body');
  if (!tbody) return;

  if (subjects.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="p-8 text-center text-sm text-slate-500">No enrolled subjects found.</td></tr>`;
    return;
  }

  tbody.innerHTML = subjects.map(s => {
    let statusClass = 'bg-emerald-50 text-emerald-700 border-emerald-200';
    let statusLabel = 'Good';
    if (s.status.level === 'warning') {
      statusClass = 'bg-amber-50 text-amber-700 border-amber-200';
      statusLabel = 'Borderline';
    } else if (s.status.level === 'danger' || s.status.level === 'critical') {
      statusClass = 'bg-rose-50 text-rose-700 border-rose-200';
      statusLabel = 'Low Shortage';
    }

    return `
      <tr class="hover:bg-slate-50/80 transition border-b border-slate-100 text-sm">
        <td class="px-5 py-4 font-semibold text-slate-900">
          <div>${s.subject_code}</div>
          <div class="text-xs font-normal text-slate-500">${s.subject_name}</div>
        </td>
        <td class="px-5 py-4 text-slate-600 text-xs">${s.faculty_name}</td>
        <td class="px-5 py-4 text-center font-medium text-slate-700">${s.conducted}</td>
        <td class="px-5 py-4 text-center font-semibold text-emerald-600">${s.attended}</td>
        <td class="px-5 py-4 text-center font-semibold text-rose-600">${s.absent}</td>
        <td class="px-5 py-4 text-center">
          <div class="inline-flex items-center gap-2">
            <span class="font-bold ${s.percentage >= 75 ? 'text-slate-800' : 'text-rose-600'}">${s.percentage}%</span>
            <div class="w-16 h-1.5 rounded-full bg-slate-100 overflow-hidden hidden sm:block">
              <div class="h-full ${s.percentage >= 75 ? 'bg-emerald-500' : 'bg-rose-500'}" style="width: ${Math.min(100, s.percentage)}%"></div>
            </div>
          </div>
        </td>
        <td class="px-5 py-4 text-center">
          <span class="inline-block px-2.5 py-1 rounded-full text-xs font-semibold border ${statusClass}">
            ${statusLabel}
          </span>
        </td>
        <td class="px-5 py-4 text-right">
          <button onclick="viewSubjectDetails(${s.subject_id}, '${s.subject_code} - ${s.subject_name}')" class="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold rounded-lg text-xs transition">
            View Details
          </button>
        </td>
      </tr>
    `;
  }).join('');
}

// 7. Subject Attendance Details Modal
async function viewSubjectDetails(subjectId, title) {
  const modal = document.getElementById('subject-details-modal');
  const titleEl = document.getElementById('subject-details-title');
  const tbody = document.getElementById('subject-details-table-body');

  if (titleEl) titleEl.textContent = title;
  if (tbody) tbody.innerHTML = `<tr><td colspan="5" class="p-6 text-center text-xs text-slate-400">Loading session records...</td></tr>`;

  openModal('subject-details-modal');

  try {
    const data = await API.get(`/api/student/subjects/${subjectId}/attendance`);
    if (!data.records || data.records.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" class="p-6 text-center text-xs text-slate-400">No session attendance records found for this subject.</td></tr>`;
      return;
    }

    tbody.innerHTML = data.records.map(r => {
      let badge = '';
      if (r.status === 'PRESENT') {
        badge = '<span class="px-2 py-0.5 rounded text-xs font-semibold bg-emerald-100 text-emerald-800">Present</span>';
      } else if (r.status === 'ABSENT') {
        badge = '<span class="px-2 py-0.5 rounded text-xs font-semibold bg-rose-100 text-rose-800">Absent</span>';
      } else if (r.status === 'APPROVED_PERMISSION') {
        badge = '<span class="px-2 py-0.5 rounded text-xs font-semibold bg-indigo-100 text-indigo-800" title="Excused via approved permission">Approved Permission</span>';
      }

      return `
        <tr class="border-b border-slate-100 text-xs hover:bg-slate-50">
          <td class="px-4 py-3 font-medium text-slate-800">${formatDate(r.date)}</td>
          <td class="px-4 py-3 text-center text-slate-600">Hour ${r.hour}</td>
          <td class="px-4 py-3 text-center">${badge}</td>
          <td class="px-4 py-3 text-slate-600">${r.faculty_name}</td>
          <td class="px-4 py-3 text-slate-500 italic">${r.audit_notes || '-'}</td>
        </tr>
      `;
    }).join('');

  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="5" class="p-6 text-center text-xs text-rose-500">Failed to load attendance history.</td></tr>`;
  }
}

// 8. Required Classes Calculator Engine
function populateCalculatorSubjectDropdown(subjects, overall) {
  const select = document.getElementById('calc-subject-select');
  if (!select) return;

  select.innerHTML = `
    <option value="OVERALL">Overall Attendance (${overall.conducted} classes conducted, ${overall.percentage}%)</option>
    ${subjects.map(s => `<option value="${s.subject_id}">${s.subject_code} — ${s.subject_name} (${s.percentage}%)</option>`).join('')}
  `;
}

function selectSubjectInCalculator(subjectId) {
  const select = document.getElementById('calc-subject-select');
  if (select) {
    select.value = subjectId;
    updateCalculatorMath();
    window.location.hash = '#calculator';
  }
}

function setupCalculatorListeners() {
  const subjectSelect = document.getElementById('calc-subject-select');
  const targetSlider = document.getElementById('calc-target-slider');
  const futureAttendedInput = document.getElementById('calc-future-attended');
  const futureMissedInput = document.getElementById('calc-future-missed');

  if (subjectSelect) subjectSelect.addEventListener('change', updateCalculatorMath);
  if (targetSlider) targetSlider.addEventListener('input', () => {
    document.getElementById('calc-target-label').textContent = `${targetSlider.value}%`;
    updateCalculatorMath();
  });
  if (futureAttendedInput) futureAttendedInput.addEventListener('input', updateCalculatorMath);
  if (futureMissedInput) futureMissedInput.addEventListener('input', updateCalculatorMath);
}

function updateCalculatorMath() {
  if (!studentDashboardData) return;

  const subjectVal = document.getElementById('calc-subject-select')?.value || 'OVERALL';
  const targetPct = parseFloat(document.getElementById('calc-target-slider')?.value || 75.0);
  const futureAtt = parseInt(document.getElementById('calc-future-attended')?.value || 0);
  const futureMiss = parseInt(document.getElementById('calc-future-missed')?.value || 0);

  let conducted = 0;
  let attended = 0;
  let name = 'Overall Attendance';

  if (subjectVal === 'OVERALL') {
    conducted = studentDashboardData.overall.conducted;
    attended = studentDashboardData.overall.attended;
  } else {
    const sub = studentDashboardData.subjects.find(s => String(s.subject_id) === String(subjectVal));
    if (sub) {
      conducted = sub.conducted;
      attended = sub.attended;
      name = `${sub.subject_code} ${sub.subject_name}`;
    }
  }

  const currentPct = conducted > 0 ? (attended / conducted) * 100 : 0;
  const currentPctFormatted = currentPct.toFixed(1);

  // Exact math:
  // (attended + x) / (conducted + x) >= targetPct / 100
  let requiredConsecutive = 0;
  let canSafelyMiss = 0;
  const targetFraction = targetPct / 100.0;

  if (conducted > 0 && targetFraction < 1.0) {
    if ((attended / conducted) < targetFraction) {
      const num = (targetFraction * conducted) - attended;
      const den = 1.0 - targetFraction;
      requiredConsecutive = Math.max(0, Math.ceil(num / den));
    } else {
      const num = attended - (targetFraction * conducted);
      canSafelyMiss = Math.max(0, Math.floor(num / targetFraction));
    }
  }

  // Display Output Card
  const outputBox = document.getElementById('calc-result-box');
  if (outputBox) {
    if (conducted === 0) {
      outputBox.innerHTML = `<p class="text-slate-500 text-sm">No classes conducted yet for this selection.</p>`;
    } else if (currentPct < targetPct) {
      outputBox.innerHTML = `
        <div class="p-4 rounded-xl border border-rose-200 bg-rose-50 text-rose-900">
          <div class="flex items-center gap-2 font-bold text-base">
            <span class="text-xl">⚠</span>
            <span>You need to attend at least <span class="underline text-lg font-black text-rose-700">${requiredConsecutive}</span> consecutive classes to reach ${targetPct}% attendance.</span>
          </div>
          <div class="mt-2 text-xs text-rose-700 leading-relaxed font-mono-code bg-white/70 p-2.5 rounded-lg border border-rose-100">
            Current: ${attended} attended / ${conducted} conducted = ${currentPctFormatted}%<br>
            Formula: (${attended} + ${requiredConsecutive}) / (${conducted} + ${requiredConsecutive}) = ${attended + requiredConsecutive}/${conducted + requiredConsecutive} = ${(((attended + requiredConsecutive)/(conducted + requiredConsecutive))*100).toFixed(1)}% >= ${targetPct}%
          </div>
        </div>
      `;
    } else {
      outputBox.innerHTML = `
        <div class="p-4 rounded-xl border border-emerald-200 bg-emerald-50 text-emerald-900">
          <div class="flex items-center gap-2 font-bold text-base">
            <span class="text-xl">✓</span>
            <span>You are currently eligible! You can miss up to <span class="underline text-lg font-black text-emerald-700">${canSafelyMiss}</span> more classes without falling below ${targetPct}%.</span>
          </div>
          <div class="mt-2 text-xs text-emerald-700 leading-relaxed font-mono-code bg-white/70 p-2.5 rounded-lg border border-emerald-100">
            Current: ${attended} attended / ${conducted} conducted = ${currentPctFormatted}%<br>
            If you miss ${canSafelyMiss} classes: ${attended} / (${conducted} + ${canSafelyMiss}) = ${attended}/${conducted + canSafelyMiss} = ${(((attended)/(conducted + canSafelyMiss))*100).toFixed(1)}% >= ${targetPct}%
          </div>
        </div>
      `;
    }
  }

  // Future Simulator Math
  const simConducted = conducted + futureAtt + futureMiss;
  const simAttended = attended + futureAtt;
  const simPct = simConducted > 0 ? ((simAttended / simConducted) * 100).toFixed(1) : '0.0';

  const simResultEl = document.getElementById('calc-sim-result');
  if (simResultEl) {
    simResultEl.innerHTML = `
      <div class="flex items-center justify-between text-xs">
        <span class="text-slate-500">Projected Attendance:</span>
        <span class="font-bold text-base ${parseFloat(simPct) >= targetPct ? 'text-emerald-600' : 'text-rose-600'}">${simPct}%</span>
      </div>
      <div class="text-[11px] text-slate-500 mt-1">
        New Conducted: ${simConducted} | New Attended: ${simAttended} | Change: ${(parseFloat(simPct) - parseFloat(currentPctFormatted)).toFixed(1)}%
      </div>
    `;
  }
}

// 9. Attendance Calendar View
async function loadAttendanceCalendar() {
  const container = document.getElementById('calendar-grid');
  if (!container) return;

  try {
    const data = await API.get('/api/student/calendar');
    const calMap = data.calendar || {};

    // Generate days for September 2026 (Sept 1 to Sept 30)
    let gridHtml = '';
    for (let day = 1; day <= 30; day++) {
      const dateStr = `2026-09-${day < 10 ? '0' + day : day}`;
      const dayData = calMap[dateStr];
      const dateObj = new Date(2026, 8, day);
      const isWeekend = dateObj.getDay() === 0 || dateObj.getDay() === 6;

      let dotHtml = '';
      let borderClass = 'border-slate-100 bg-white hover:border-blue-300';
      if (isWeekend) {
        borderClass = 'border-slate-100 bg-slate-50 text-slate-400';
      }

      if (dayData) {
        if (dayData.has_absent) {
          dotHtml += '<span class="w-2 h-2 rounded-full bg-rose-500" title="Has Absent Class"></span>';
        }
        if (dayData.has_present) {
          dotHtml += '<span class="w-2 h-2 rounded-full bg-emerald-500" title="Present"></span>';
        }
        if (dayData.has_permission) {
          dotHtml += '<span class="w-2 h-2 rounded-full bg-indigo-500" title="Permission Approved"></span>';
        }
      }

      gridHtml += `
        <div onclick="openDayCalendarModal('${dateStr}')" class="p-2.5 min-h-[4rem] rounded-xl border ${borderClass} cursor-pointer transition flex flex-col justify-between">
          <div class="flex items-center justify-between">
            <span class="text-xs font-semibold ${isWeekend ? 'text-slate-400' : 'text-slate-800'}">${day}</span>
            <span class="text-[10px] text-slate-400">${dateObj.toLocaleDateString('en-US', { weekday: 'narrow' })}</span>
          </div>
          <div class="flex items-center gap-1 mt-1">
            ${dotHtml}
          </div>
        </div>
      `;
    }

    container.innerHTML = gridHtml;

  } catch (err) {
    console.error('Failed to load calendar:', err);
  }
}

async function openDayCalendarModal(dateStr) {
  const modal = document.getElementById('day-calendar-modal');
  const titleEl = document.getElementById('day-calendar-title');
  const bodyEl = document.getElementById('day-calendar-body');

  if (titleEl) titleEl.textContent = `Attendance Details — ${formatDate(dateStr)}`;
  if (bodyEl) bodyEl.innerHTML = '<div class="p-4 text-center text-xs text-slate-400">Loading day schedule...</div>';

  openModal('day-calendar-modal');

  try {
    const data = await API.get('/api/student/calendar');
    const dayData = (data.calendar || {})[dateStr];

    if (!dayData || !dayData.sessions || dayData.sessions.length === 0) {
      bodyEl.innerHTML = `
        <div class="p-6 text-center text-xs text-slate-500">
          No classes scheduled or recorded on this date.
        </div>
      `;
      return;
    }

    bodyEl.innerHTML = `
      <div class="space-y-2.5">
        ${dayData.sessions.map(s => {
          let badge = '';
          if (s.status === 'PRESENT') {
            badge = '<span class="px-2 py-0.5 rounded text-xs font-bold bg-emerald-100 text-emerald-800">Present</span>';
          } else if (s.status === 'ABSENT') {
            badge = '<span class="px-2 py-0.5 rounded text-xs font-bold bg-rose-100 text-rose-800">Absent</span>';
          } else {
            badge = '<span class="px-2 py-0.5 rounded text-xs font-bold bg-indigo-100 text-indigo-800">Approved Permission</span>';
          }

          return `
            <div class="p-3 rounded-xl border border-slate-100 bg-slate-50/70 flex items-center justify-between text-xs">
              <div>
                <span class="font-bold text-slate-800">${s.subject_code}</span>: ${s.subject_name}
                <div class="text-[11px] text-slate-500 mt-0.5">Faculty: ${s.faculty_name}</div>
              </div>
              <div class="flex items-center gap-3">
                <span class="text-slate-600 font-medium">Hour ${s.hour}</span>
                ${badge}
              </div>
            </div>
          `;
        }).join('')}
      </div>
    `;

  } catch (e) {
    bodyEl.innerHTML = '<div class="p-4 text-center text-xs text-rose-500">Failed to load day details.</div>';
  }
}

// 10. Permission Portal: Load Missed Classes & Requests
async function loadMissedClassesForPermission() {
  const container = document.getElementById('missed-classes-picker');
  if (!container) return;

  try {
    const data = await API.get('/api/student/missed-classes');
    const missed = data.missed_classes || [];

    if (missed.length === 0) {
      container.innerHTML = `<p class="text-xs text-slate-400">No unexcused absent classes found.</p>`;
      return;
    }

    container.innerHTML = `
      <div class="text-xs text-slate-500 mb-1.5 font-medium">Quick Pick from Absent Classes:</div>
      <div class="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto p-1">
        ${missed.map(m => `
          <button type="button" onclick="selectMissedClass('${m.subject_id}', '${m.faculty_id}', '${m.date}', ${m.hour})" class="px-2.5 py-1 rounded-lg border border-slate-200 bg-slate-50 hover:bg-blue-50 hover:border-blue-300 text-xs font-medium text-slate-700 transition">
            ${m.subject_code} • ${formatDate(m.date)} (Hr ${m.hour})
          </button>
        `).join('')}
      </div>
    `;

  } catch (err) {
    console.error('Failed to load missed classes:', err);
  }
}

function selectMissedClass(subId, facId, dateVal, hourVal) {
  const subSelect = document.getElementById('perm-subject');
  const dateInput = document.getElementById('perm-date');
  const hourInput = document.getElementById('perm-hour');

  if (subSelect) subSelect.value = subId;
  if (dateInput) dateInput.value = dateVal;
  if (hourInput) hourInput.value = hourVal;
  showToast(`Selected ${dateVal} Hour ${hourVal}`, 'info', 2000);
}

function openPermissionModal() {
  openModal('permission-request-modal');
  loadMissedClassesForPermission();
}

function openPermissionModalWithSubject(subjectId) {
  openPermissionModal();
  const subSelect = document.getElementById('perm-subject');
  if (subSelect) subSelect.value = subjectId;
}

// 11. Permission Form Submission
function setupPermissionForm() {
  const form = document.getElementById('permission-request-form');
  const fileInput = document.getElementById('perm-document');
  const filePreview = document.getElementById('file-preview-name');

  if (fileInput && filePreview) {
    fileInput.addEventListener('change', () => {
      if (fileInput.files.length > 0) {
        const file = fileInput.files[0];
        if (file.size > 5 * 1024 * 1024) {
          showToast('File size must be below 5 MB.', 'error');
          fileInput.value = '';
          filePreview.textContent = '';
          return;
        }
        filePreview.textContent = `Selected: ${file.name} (${(file.size / 1024).toFixed(0)} KB)`;
      } else {
        filePreview.textContent = '';
      }
    });
  }

  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const submitBtn = document.getElementById('perm-submit-btn');
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Submitting Request...';
      }

      const formData = new FormData(form);

      try {
        const res = await API.post('/api/student/permissions', formData);
        showToast(res.message || 'Permission request submitted successfully!', 'success');
        closeModal('permission-request-modal');
        form.reset();
        if (filePreview) filePreview.textContent = '';

        // Reload data
        await loadStudentDashboard();
        await loadPermissionRequestsTable();

      } catch (err) {
        showToast(err.message || 'Submission failed. Please check form.', 'error');
      } finally {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.textContent = 'Submit Request';
        }
      }
    });
  }
}

// 12. Permission Requests Status Table
async function loadPermissionRequestsTable() {
  const tbody = document.getElementById('permission-requests-table-body');
  if (!tbody) return;

  try {
    const data = await API.get('/api/student/permissions');
    const requests = data.requests || [];

    if (requests.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" class="p-8 text-center text-xs text-slate-400">No permission requests submitted yet.</td></tr>`;
      return;
    }

    tbody.innerHTML = requests.map(pr => {
      let statusBadge = '';
      if (pr.status === 'APPROVED') {
        statusBadge = '<span class="px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-200">Approved</span>';
      } else if (pr.status === 'PENDING') {
        statusBadge = '<span class="px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-200">Pending Review</span>';
      } else if (pr.status === 'ESCALATED_HOD') {
        statusBadge = '<span class="px-2.5 py-1 rounded-full text-xs font-semibold bg-purple-100 text-purple-800 border border-purple-200">Escalated to HOD</span>';
      } else if (pr.status === 'REJECTED') {
        statusBadge = '<span class="px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-100 text-rose-800 border border-rose-200">Rejected</span>';
      } else {
        statusBadge = '<span class="px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-100 text-blue-800 border border-blue-200">Under Review</span>';
      }

      return `
        <tr class="border-b border-slate-100 text-xs hover:bg-slate-50 transition">
          <td class="px-4 py-3.5 font-bold text-blue-700 font-mono-code">${pr.request_code}</td>
          <td class="px-4 py-3.5 font-semibold text-slate-800">${pr.subject_code}</td>
          <td class="px-4 py-3.5 text-slate-600">${formatDate(pr.date)} (Hr ${pr.hour})</td>
          <td class="px-4 py-3.5 font-medium text-slate-700">${pr.reason}</td>
          <td class="px-4 py-3.5 text-slate-500">${formatDate(pr.created_at ? pr.created_at.split(' ')[0] : '')}</td>
          <td class="px-4 py-3.5 text-center">${statusBadge}</td>
          <td class="px-4 py-3.5 text-right">
            <button onclick='viewPermissionDetailsModal(${JSON.stringify(pr)})' class="px-3 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold rounded-lg transition">
              Details
            </button>
          </td>
        </tr>
      `;
    }).join('');

  } catch (err) {
    console.error('Failed to load permission requests:', err);
  }
}

// 13. Permission Request Details Modal
function viewPermissionDetailsModal(pr) {
  const modal = document.getElementById('permission-details-modal');
  const codeEl = document.getElementById('modal-perm-code');
  const bodyEl = document.getElementById('modal-perm-body');

  if (codeEl) codeEl.textContent = `Request ${pr.request_code}`;
  if (bodyEl) {
    let docBtn = '<span class="text-xs text-slate-400 italic">No document attached</span>';
    if (pr.document_filename) {
      docBtn = `
        <a href="/api/files/${pr.document_filename}" target="_blank" class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-50 border border-blue-200 text-blue-700 text-xs font-semibold hover:bg-blue-100 transition">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path></svg>
          View Attached Document (${pr.document_original_name || 'Document'})
        </a>
      `;
    }

    bodyEl.innerHTML = `
      <div class="space-y-4 text-xs">
        <div class="grid grid-cols-2 gap-3 p-3 bg-slate-50 rounded-xl border border-slate-100">
          <div><span class="text-slate-500">Subject:</span> <strong class="text-slate-800">${pr.subject_code} — ${pr.subject_name}</strong></div>
          <div><span class="text-slate-500">Assigned Faculty:</span> <strong class="text-slate-800">${pr.faculty_name || 'Faculty Member'}</strong></div>
          <div><span class="text-slate-500">Date & Hour:</span> <strong class="text-slate-800">${formatDate(pr.date)}, Hour ${pr.hour}</strong></div>
          <div><span class="text-slate-500">Status:</span> <strong class="text-blue-700 font-bold">${pr.status}</strong></div>
        </div>

        <div>
          <div class="font-bold text-slate-800 mb-1">Reason: ${pr.reason}</div>
          <div class="p-3 bg-white border border-slate-200 rounded-xl text-slate-700 leading-relaxed">${pr.description}</div>
        </div>

        <div>
          <div class="font-bold text-slate-800 mb-1">Supporting Document:</div>
          ${docBtn}
        </div>

        ${pr.faculty_comment ? `
          <div class="p-3 rounded-xl border border-amber-200 bg-amber-50">
            <span class="font-bold text-amber-900">Faculty Feedback / Comment:</span>
            <p class="text-amber-800 mt-1">${pr.faculty_comment}</p>
          </div>
        ` : ''}

        ${pr.hod_comment ? `
          <div class="p-3 rounded-xl border border-purple-200 bg-purple-50">
            <span class="font-bold text-purple-900">HOD Remarks:</span>
            <p class="text-purple-800 mt-1">${pr.hod_comment}</p>
          </div>
        ` : ''}
      </div>
    `;
  }

  openModal('permission-details-modal');
}

// 14. Tab switching for student portal
function switchToTab(targetId) {
  if (!targetId) return;
  if (targetId.startsWith('#')) {
    targetId = 'tab-' + targetId.substring(1);
  }

  const tabs = document.querySelectorAll('[data-tab-target]');
  tabs.forEach(link => {
    if (link.getAttribute('data-tab-target') === targetId) {
      link.classList.add('active');
    } else {
      link.classList.remove('active');
    }
  });

  const views = document.querySelectorAll('.tab-view');
  views.forEach(v => v.classList.add('hidden'));

  const targetView = document.getElementById(targetId);
  if (targetView) targetView.classList.remove('hidden');

  if (targetId === 'tab-security') {
    loadUserProfile();
    loadSecurityActivity();
  }

  // Close mobile drawer if open
  const sidebar = document.getElementById('app-sidebar');
  const backdrop = document.getElementById('sidebar-backdrop');
  if (sidebar && backdrop) {
    sidebar.classList.add('-translate-x-full');
    backdrop.classList.add('hidden');
  }
}

function setupNavigationTabs() {
  const tabs = document.querySelectorAll('[data-tab-target]');
  tabs.forEach(t => {
    t.addEventListener('click', (e) => {
      e.preventDefault();
      const targetId = t.getAttribute('data-tab-target');
      switchToTab(targetId);
    });
  });

  // Handle URL hash changes
  window.addEventListener('hashchange', () => {
    if (window.location.hash) {
      switchToTab(window.location.hash);
    }
  });

  if (window.location.hash) {
    switchToTab(window.location.hash);
  }
}

// 15. Password Security & Visibility Toggles
function togglePasswordVisibility(inputId, btn) {
  const input = document.getElementById(inputId);
  if (!input) return;
  const isPwd = input.type === 'password';
  input.type = isPwd ? 'text' : 'password';

  if (btn) {
    const eyeOpen = btn.querySelector('.eye-open');
    const eyeClosed = btn.querySelector('.eye-closed');
    if (eyeOpen && eyeClosed) {
      if (isPwd) {
        eyeOpen.classList.add('hidden');
        eyeClosed.classList.remove('hidden');
      } else {
        eyeOpen.classList.remove('hidden');
        eyeClosed.classList.add('hidden');
      }
    }
  }
}

function checkPasswordStrength(pwd) {
  const reqLen = document.getElementById('req-len');
  const reqUpper = document.getElementById('req-upper');
  const reqLower = document.getElementById('req-lower');
  const reqNum = document.getElementById('req-num');
  const reqSpec = document.getElementById('req-spec');

  const hasLen = pwd.length >= 8;
  const hasUpper = /[A-Z]/.test(pwd);
  const hasLower = /[a-z]/.test(pwd);
  const hasNum = /\d/.test(pwd);
  const hasSpec = /[!@#$%^&*(),.?":{}|<>_\-+=\[\]\/\\`~]/.test(pwd);

  updateReqItem(reqLen, hasLen, 'At least 8 characters');
  updateReqItem(reqUpper, hasUpper, 'At least 1 uppercase letter (A-Z)');
  updateReqItem(reqLower, hasLower, 'At least 1 lowercase letter (a-z)');
  updateReqItem(reqNum, hasNum, 'At least 1 number (0-9)');
  updateReqItem(reqSpec, hasSpec, 'At least 1 special character (!@#$%^&*...)');

  // Strength score calculation
  let score = 0;
  if (hasLen) score += 20;
  if (hasUpper) score += 20;
  if (hasLower) score += 20;
  if (hasNum) score += 20;
  if (hasSpec) score += 20;

  const bar = document.getElementById('pwd-strength-bar');
  const text = document.getElementById('pwd-strength-text');
  if (bar) {
    bar.style.width = score + '%';
    bar.classList.remove('bg-slate-300', 'bg-rose-500', 'bg-amber-500', 'bg-blue-500', 'bg-emerald-500');
    if (score === 0) {
      bar.classList.add('bg-slate-300');
    } else if (score <= 40) {
      bar.classList.add('bg-rose-500');
    } else if (score <= 60) {
      bar.classList.add('bg-amber-500');
    } else if (score <= 80) {
      bar.classList.add('bg-blue-500');
    } else {
      bar.classList.add('bg-emerald-500');
    }
  }

  if (text) {
    text.classList.remove('text-slate-400', 'text-rose-600', 'text-amber-600', 'text-blue-600', 'text-emerald-600');
    if (score === 0) {
      text.textContent = 'None';
      text.classList.add('text-slate-400');
    } else if (score <= 40) {
      text.textContent = 'Weak';
      text.classList.add('text-rose-600');
    } else if (score <= 60) {
      text.textContent = 'Fair';
      text.classList.add('text-amber-600');
    } else if (score <= 80) {
      text.textContent = 'Good';
      text.classList.add('text-blue-600');
    } else {
      text.textContent = 'Strong (Compliant)';
      text.classList.add('text-emerald-600');
    }
  }

  checkPasswordMatch();
}

function checkPasswordMatch() {
  const newPwd = document.getElementById('new-pwd')?.value || '';
  const confirmPwd = document.getElementById('confirm-pwd')?.value || '';
  const indicator = document.getElementById('pwd-match-indicator');
  if (!indicator) return;

  if (!confirmPwd) {
    indicator.textContent = '';
    return;
  }

  if (newPwd === confirmPwd) {
    indicator.textContent = '✓ Passwords match';
    indicator.className = 'text-[10px] font-bold text-emerald-600';
  } else {
    indicator.textContent = '✗ Passwords do not match';
    indicator.className = 'text-[10px] font-bold text-rose-600';
  }
}

function updateReqItem(el, passed, text) {
  if (!el) return;
  if (passed) {
    el.className = 'flex items-center gap-1.5 text-emerald-600 font-semibold';
    el.innerHTML = `<span>✓</span> ${text}`;
  } else {
    el.className = 'flex items-center gap-1.5 text-slate-400';
    el.innerHTML = `<span>•</span> ${text}`;
  }
}

// 16. Security Activity & Audit Trail
async function loadSecurityActivity() {
  const tbody = document.getElementById('security-activity-table-body');
  const devEl = document.getElementById('sec-device-info');
  if (devEl) {
    const isMobile = /Mobi|Android/i.test(navigator.userAgent);
    devEl.textContent = isMobile ? 'Mobile Browser' : 'Desktop Browser';
  }
  if (!tbody) return;

  try {
    const res = await API.get('/api/profile/activity');
    const logs = res.activity || [];
    if (logs.length === 0) {
      tbody.innerHTML = '<tr><td colspan="4" class="px-3 py-4 text-center text-slate-400">No security audit events recorded yet.</td></tr>';
      return;
    }

    tbody.innerHTML = logs.map(l => {
      let badge = 'bg-slate-100 text-slate-700';
      if (l.action === 'LOGIN') badge = 'bg-blue-100 text-blue-800';
      else if (l.action === 'CHANGE_PASSWORD') badge = 'bg-emerald-100 text-emerald-800';
      else if (l.action === 'UPDATE_PROFILE') badge = 'bg-purple-100 text-purple-800';
      else if (l.action === 'UPDATE_AVATAR') badge = 'bg-indigo-100 text-indigo-800';

      return `
        <tr class="hover:bg-slate-50 transition">
          <td class="px-3 py-2 font-bold"><span class="px-2 py-0.5 rounded text-[10px] font-semibold ${badge}">${l.action}</span></td>
          <td class="px-3 py-2 text-slate-700 max-w-xs truncate" title="${l.details || ''}">${l.details || '--'}</td>
          <td class="px-3 py-2 font-mono text-[11px] text-slate-500">${l.ip_address || '127.0.0.1'}</td>
          <td class="px-3 py-2 text-right text-slate-500 font-mono text-[11px]">${formatDate(l.created_at ? l.created_at.split(' ')[0] : '')} ${l.created_at ? l.created_at.split(' ')[1] || '' : ''}</td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    console.error('Failed to load security activity:', err);
    tbody.innerHTML = '<tr><td colspan="4" class="px-3 py-4 text-center text-slate-400">Security audit log temporarily unavailable.</td></tr>';
  }
}

// 17. Profile Editing, Photo Upload & Verification
let currentProfileData = null;
let selectedAvatarFile = null;

async function loadUserProfile() {
  try {
    const data = await API.get('/api/profile');
    if (data && data.profile) {
      currentProfileData = data.profile;
      renderUserProfile(currentProfileData);
    }
  } catch (err) {
    console.error('Failed to load user profile:', err);
  }
}

function renderUserProfile(profile) {
  if (!profile) return;

  // View fields
  const viewName = document.getElementById('profile-view-name');
  const viewUsnBadge = document.getElementById('profile-view-usn-badge');
  const viewPhone = document.getElementById('profile-view-phone-display');
  const viewEmer = document.getElementById('profile-view-emergency-display');
  const viewBlood = document.getElementById('profile-view-blood-display');
  const viewBio = document.getElementById('profile-view-bio-display');

  // Master records
  const cardUsn = document.getElementById('profile-card-usn');
  const cardEmail = document.getElementById('profile-card-email');
  const cardDept = document.getElementById('profile-card-dept');
  const cardClass = document.getElementById('profile-card-class');
  const cardSemester = document.getElementById('profile-card-semester');
  const cardSection = document.getElementById('profile-card-section');
  const cardRoll = document.getElementById('profile-card-roll');
  const cardAy = document.getElementById('profile-card-ay');
  const cardStatus = document.getElementById('profile-card-status');

  if (viewName) viewName.textContent = profile.name;
  if (viewUsnBadge) viewUsnBadge.textContent = profile.usn;
  if (viewPhone) viewPhone.textContent = profile.phone || 'Not provided';
  if (viewEmer) viewEmer.textContent = profile.emergency_contact || 'Not provided';
  if (viewBlood) viewBlood.textContent = profile.blood_group || '--';
  if (viewBio) viewBio.textContent = profile.bio || 'No personal bio provided.';

  if (cardUsn) cardUsn.textContent = profile.usn;
  if (cardEmail) cardEmail.textContent = profile.email;
  if (cardDept) cardDept.textContent = profile.branch_name || profile.branch_code || 'Engineering';
  if (cardClass) cardClass.textContent = profile.class_name || `Sem ${profile.semester}-${profile.section}`;
  if (cardSemester) cardSemester.textContent = `Sem ${profile.semester}`;
  if (cardSection) cardSection.textContent = `Section ${profile.section}`;
  if (cardRoll) cardRoll.textContent = profile.roll_no || '--';
  if (cardAy) cardAy.textContent = profile.academic_year || '2026-2027';
  if (cardStatus) cardStatus.textContent = profile.status === 'ACTIVE' ? 'Active & Verified' : profile.status;

  // Editable input fields
  const editName = document.getElementById('edit-profile-name');
  const editPhone = document.getElementById('edit-profile-phone');
  const editEmer = document.getElementById('edit-profile-emergency');
  const editBlood = document.getElementById('edit-profile-blood');
  const editBio = document.getElementById('edit-profile-bio');
  const editAvatar = document.getElementById('edit-profile-avatar');

  if (editName) editName.value = profile.name || '';
  if (editPhone) editPhone.value = profile.phone || '';
  if (editEmer) editEmer.value = profile.emergency_contact || '';
  if (editBlood) editBlood.value = profile.blood_group || '';
  if (editBio) editBio.value = profile.bio || '';
  if (editAvatar) editAvatar.value = profile.avatar_url || '';

  // Avatar display
  updateAvatarDisplay(profile.name, profile.avatar_url, profile.usn);

  // Sync with API localStorage user
  const user = API.getUser() || {};
  user.name = profile.name;
  user.avatar_url = profile.avatar_url;
  API.setUser(user);
}

function updateAvatarDisplay(name, avatarUrl, usn) {
  const avatarDisplay = document.getElementById('profile-avatar-display');
  const topAvatar = document.getElementById('top-profile-avatar');
  const topName = document.getElementById('top-profile-name');
  const topUsn = document.getElementById('top-profile-usn');
  const initials = name ? name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase() : 'ST';

  if (avatarUrl) {
    if (avatarDisplay) avatarDisplay.innerHTML = `<img src="${avatarUrl}" alt="${name}" class="w-full h-full object-cover rounded-2xl" onerror="this.onerror=null; this.parentElement.innerHTML='<span id=\\'profile-card-initials\\'>${initials}</span>'">`;
    if (topAvatar) topAvatar.innerHTML = `<img src="${avatarUrl}" alt="${name}" class="w-full h-full object-cover rounded-full" onerror="this.onerror=null; this.parentElement.textContent='${initials}'">`;
  } else {
    if (avatarDisplay) avatarDisplay.innerHTML = `<span id="profile-card-initials">${initials}</span>`;
    if (topAvatar) topAvatar.textContent = initials;
  }

  if (topName && name) topName.textContent = name;
  if (topUsn && usn) topUsn.textContent = usn;
}

function handleAvatarFileSelect(input) {
  if (!input.files || !input.files[0]) return;
  const file = input.files[0];
  selectedAvatarFile = file;

  const fileNameEl = document.getElementById('avatar-file-name');
  if (fileNameEl) fileNameEl.textContent = `Selected: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;

  const reader = new FileReader();
  reader.onload = (e) => {
    const avatarDisplay = document.getElementById('profile-avatar-display');
    if (avatarDisplay) {
      avatarDisplay.innerHTML = `<img src="${e.target.result}" class="w-full h-full object-cover rounded-2xl" alt="Preview">`;
    }
  };
  reader.readAsDataURL(file);
}

function previewAvatarUrl(url) {
  selectedAvatarFile = null;
  const fileNameEl = document.getElementById('avatar-file-name');
  if (fileNameEl) fileNameEl.textContent = 'Max 5 MB (JPG, PNG, WEBP)';

  if (url && url.trim()) {
    const avatarDisplay = document.getElementById('profile-avatar-display');
    if (avatarDisplay) {
      avatarDisplay.innerHTML = `<img src="${url.trim()}" class="w-full h-full object-cover rounded-2xl" alt="Preview" onerror="this.onerror=null; this.parentElement.innerHTML='<span id=\\'profile-card-initials\\'>ST</span>'">`;
    }
  }
}

function selectPresetAvatar(url) {
  selectedAvatarFile = null;
  const avatarInput = document.getElementById('edit-profile-avatar');
  const fileNameEl = document.getElementById('avatar-file-name');
  if (avatarInput) avatarInput.value = url;
  if (fileNameEl) fileNameEl.textContent = url ? 'Preset Avatar Selected' : 'Max 5 MB (JPG, PNG, WEBP)';
  previewAvatarUrl(url);
}

function toggleProfileEditMode(isEditing) {
  const editFields = document.getElementById('profile-edit-fields');
  const editActions = document.getElementById('profile-edit-actions');
  const viewExtra = document.getElementById('profile-view-extra');
  const btnEdit = document.getElementById('btn-edit-profile');
  const alertBox = document.getElementById('profile-alert');

  if (alertBox) alertBox.classList.add('hidden');

  if (isEditing) {
    if (editFields) editFields.classList.remove('hidden');
    if (editActions) editActions.classList.remove('hidden');
    if (viewExtra) viewExtra.classList.add('hidden');
    if (btnEdit) btnEdit.classList.add('hidden');

    if (currentProfileData) {
      const editName = document.getElementById('edit-profile-name');
      const editPhone = document.getElementById('edit-profile-phone');
      const editEmer = document.getElementById('edit-profile-emergency');
      const editBlood = document.getElementById('edit-profile-blood');
      const editBio = document.getElementById('edit-profile-bio');
      const editAvatar = document.getElementById('edit-profile-avatar');

      if (editName) editName.value = currentProfileData.name || '';
      if (editPhone) editPhone.value = currentProfileData.phone || '';
      if (editEmer) editEmer.value = currentProfileData.emergency_contact || '';
      if (editBlood) editBlood.value = currentProfileData.blood_group || '';
      if (editBio) editBio.value = currentProfileData.bio || '';
      if (editAvatar) editAvatar.value = currentProfileData.avatar_url || '';
      if (editName) editName.focus();
    }
  } else {
    if (editFields) editFields.classList.add('hidden');
    if (editActions) editActions.classList.add('hidden');
    if (viewExtra) viewExtra.classList.remove('hidden');
    if (btnEdit) btnEdit.classList.remove('hidden');
    selectedAvatarFile = null;
  }
}

function cancelProfileEdit() {
  toggleProfileEditMode(false);
  if (currentProfileData) {
    renderUserProfile(currentProfileData);
  }
}

async function saveProfileChanges() {
  const nameInput = document.getElementById('edit-profile-name');
  const phoneInput = document.getElementById('edit-profile-phone');
  const emerInput = document.getElementById('edit-profile-emergency');
  const bloodInput = document.getElementById('edit-profile-blood');
  const bioInput = document.getElementById('edit-profile-bio');
  const avatarInput = document.getElementById('edit-profile-avatar');
  const saveBtn = document.getElementById('btn-save-profile');
  const cancelBtn = document.getElementById('btn-cancel-profile');

  const name = nameInput ? nameInput.value.trim() : '';
  const phone = phoneInput ? phoneInput.value.trim() : '';
  const emergency = emerInput ? emerInput.value.trim() : '';
  const blood = bloodInput ? bloodInput.value.trim() : '';
  const bio = bioInput ? bioInput.value.trim() : '';
  let avatarUrl = avatarInput ? avatarInput.value.trim() : '';

  if (!name || name.length < 2) {
    showProfileAlert('Please enter a valid full name (minimum 2 characters).', 'error');
    if (nameInput) nameInput.focus();
    return;
  }

  if (phone && !/^[0-9+\-\s()]{7,20}$/.test(phone)) {
    showProfileAlert('Please enter a valid mobile phone number (7-20 digits).', 'error');
    if (phoneInput) phoneInput.focus();
    return;
  }

  if (emergency && !/^[0-9+\-\s()]{7,20}$/.test(emergency)) {
    showProfileAlert('Please enter a valid emergency contact number.', 'error');
    if (emerInput) emerInput.focus();
    return;
  }

  if (saveBtn) {
    saveBtn.disabled = true;
    saveBtn.innerHTML = '<span>Saving Profile...</span>';
  }
  if (cancelBtn) cancelBtn.disabled = true;

  try {
    // 1. If an image file was selected, upload it first
    if (selectedAvatarFile) {
      const formData = new FormData();
      formData.append('avatar', selectedAvatarFile);
      const uploadRes = await API.post('/api/profile/avatar', formData);
      if (uploadRes && uploadRes.avatar_url) {
        avatarUrl = uploadRes.avatar_url;
      }
      selectedAvatarFile = null;
    }

    // 2. Save profile fields
    const res = await API.put('/api/profile', {
      name: name,
      phone: phone,
      emergency_contact: emergency,
      blood_group: blood,
      bio: bio,
      avatar_url: avatarUrl
    });

    currentProfileData = res.profile;
    renderUserProfile(currentProfileData);
    toggleProfileEditMode(false);

    showToast('Profile updated successfully.', 'success');
    showProfileAlert('Profile updated successfully.', 'success');
    loadSecurityActivity();
  } catch (err) {
    showProfileAlert(err.message || 'Failed to update profile.', 'error');
    showToast(err.message || 'Failed to update profile.', 'error');
  } finally {
    if (saveBtn) {
      saveBtn.disabled = false;
      saveBtn.innerHTML = '<span>Save Changes</span>';
    }
    if (cancelBtn) cancelBtn.disabled = false;
  }
}

function showProfileAlert(msg, type) {
  const alertBox = document.getElementById('profile-alert');
  if (!alertBox) return;

  alertBox.classList.remove('hidden', 'bg-rose-50', 'border-rose-200', 'text-rose-800', 'bg-emerald-50', 'border-emerald-200', 'text-emerald-800');

  if (type === 'success') {
    alertBox.classList.add('bg-emerald-50', 'border-emerald-200', 'text-emerald-800');
    alertBox.innerHTML = `<strong>✓ Success:</strong> ${msg}`;
  } else {
    alertBox.classList.add('bg-rose-50', 'border-rose-200', 'text-rose-800');
    alertBox.innerHTML = `<strong>✗ Error:</strong> ${msg}`;
  }
}

// 18. Change Password Form Handler
function setupPasswordChangeForm() {
  const form = document.getElementById('change-password-form');
  if (!form) return;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const curPwd = document.getElementById('cur-pwd').value;
    const newPwd = document.getElementById('new-pwd').value;
    const confirmPwd = document.getElementById('confirm-pwd').value;
    const submitBtn = document.getElementById('change-pwd-btn');

    if (!curPwd || !newPwd || !confirmPwd) {
      showPwdAlert('Please fill in all password fields.', 'error');
      return;
    }

    if (newPwd !== confirmPwd) {
      showPwdAlert('New passwords do not match.', 'error');
      return;
    }

    // Client-side strength validation check
    const hasLen = newPwd.length >= 8;
    const hasUpper = /[A-Z]/.test(newPwd);
    const hasLower = /[a-z]/.test(newPwd);
    const hasNum = /\d/.test(newPwd);
    const hasSpec = /[!@#$%^&*(),.?":{}|<>_\-+=\[\]\/\\`~]/.test(newPwd);
    if (!hasLen || !hasUpper || !hasLower || !hasNum || !hasSpec) {
      showPwdAlert('New password does not satisfy all institutional complexity requirements.', 'error');
      return;
    }

    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span>Changing password...</span>';

    try {
      const res = await API.put('/api/profile/change-password', {
        currentPassword: curPwd,
        newPassword: newPwd,
        confirmPassword: confirmPwd
      });

      showPwdAlert('Password changed successfully.', 'success');
      form.reset();
      checkPasswordStrength('');
      showToast('Password changed successfully.', 'success');
      loadSecurityActivity();
    } catch (err) {
      showPwdAlert(err.message || 'Failed to change password.', 'error');
      showToast(err.message || 'Failed to change password.', 'error');
    } finally {
      submitBtn.disabled = false;
      submitBtn.innerHTML = `
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path></svg>
        <span>Change Password</span>
      `;
    }
  });
}

function showPwdAlert(msg, type) {
  const alertBox = document.getElementById('change-pwd-alert');
  if (!alertBox) return;

  alertBox.classList.remove('hidden', 'bg-rose-50', 'border-rose-200', 'text-rose-800', 'bg-emerald-50', 'border-emerald-200', 'text-emerald-800');

  if (type === 'success') {
    alertBox.classList.add('bg-emerald-50', 'border-emerald-200', 'text-emerald-800');
    alertBox.innerHTML = `<strong>✓ Success:</strong> ${msg}`;
  } else {
    alertBox.classList.add('bg-rose-50', 'border-rose-200', 'text-rose-800');
    alertBox.innerHTML = `<strong>✗ Error:</strong> ${msg}`;
  }
}
