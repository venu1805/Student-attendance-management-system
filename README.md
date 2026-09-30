# SmartAttend — Student Attendance Management System

> **"Track Attendance. Stay Eligible. Stay Informed."**

SmartAttend is a modern, responsive, full-stack Student Attendance Management System website built for colleges and universities. It provides separate portals for **Students**, **Faculty**, **Heads of Departments (HOD)**, and **Administrators**, designed like a professional college ERP system.

---

## 🌟 Key Differentiating Features

### 1. "Am I Safe?" Immediate Status Indicator
Prominently answers the student's most vital question as soon as they open the dashboard:
- **Green (Safe)**: Attendance $\ge 75\%$ across all enrolled subjects.
- **Yellow (Warning)**: Overall is above 75%, but one or more subjects is close to the threshold.
- **Red (Critical)**: Attendance is below 75%. Displays exact number of consecutive classes required to regain eligibility.

### 2. Required Classes Calculator (Dynamic Mathematical Engine)
- **Mathematical Formula**:
  $$\text{Smallest integer } x \ge 0 \text{ such that } \frac{\text{attended} + x}{\text{conducted} + x} \ge \frac{\text{minimum\_percentage}}{100}$$
  $$x = \max\left(0, \left\lceil \frac{(\text{min\_pct} / 100) \times \text{conducted} - \text{attended}}{1 - (\text{min\_pct} / 100)} \right\rceil\right)$$
- **Max Classes Missable Without Falling Below**:
  $$y = \max\left(0, \left\lfloor \frac{\text{attended} - (\text{min\_pct} / 100) \times \text{conducted}}{\text{min\_pct} / 100} \right\rfloor\right)$$
- **Interactive Simulator**: Allows testing hypothetical scenarios ("What if I attend 8 more classes and miss 2?").
- Handles all edge cases (0 conducted classes, 0 attendance, 100% attendance, no negative class counts).

### 3. Attendance Permission Request Portal & Multi-Tier Approval Workflow
When a student is absent, they can submit an official permission request:
- **Form fields**: Subject, Faculty, Date, Class Hour, Reason (Medical emergency, Hospital visit, Family emergency, College event, Official representation, Other), Detailed explanation, and Supporting document upload (PDF, JPG, PNG up to 5MB).
- **Workflow**:
  $$\text{Student Submits} \longrightarrow \text{Faculty Reviews (Approve / Reject / Escalate)} \longrightarrow \text{HOD Discretionary Decision (if escalated)}$$
- **Audit Trail & Attendance Credit**: When approved, the student's attendance record is updated from `Absent` to `Approved Permission` (Excused/Duty Leave) with reviewer remarks and timestamp recorded.

### 4. Real-Time In-App Notifications
- Notification bell in navbar with badge count for unread alerts.
- Triggers on attendance marked, low-attendance warnings, permission approvals/rejections, and administrative notices.

### 5. Automated Defaulter Watchlists
- Faculty and HOD can view all students falling short of 75% attendance.
- HOD can issue official warning notices with a single click.

### 6. Reports & Export Engine
- Export Student Overall Attendance Roster, Low-Attendance Defaulters List, and Permission Requests Audit Report as **CSV** or **Printable PDF**.

---

## 👥 Demo Accounts

All demo accounts have the password: **`password123`**.  
The login page also provides a **1-Click Demo Switcher** for instant testing!

| Role | Email | Password | Details |
|---|---|---|---|
| **Student** | `student@college.edu` | `password123` | Rahul Sharma (USN: `4SJ22CS045`, CSE Sem 5) |
| **Faculty** | `faculty@college.edu` | `password123` | Prof. Arvind Kumar (Associate Professor, CSE) |
| **HOD** | `hod@college.edu` | `password123` | Dr. Rajesh Sharma (Professor & Head, CSE) |
| **Admin** | `admin@college.edu` | `password123` | Central ERP Administrator |

---

## 🚀 Quick Start Guide

### 1. Launch with One Click (Windows)
Double-click `run.bat` in the project directory:
```bash
run.bat
```
This automatically verifies dependencies, seeds the SQLite database, and starts the server at `http://127.0.0.1:5000`.

### 2. Manual Launch via Python
```bash
# Install dependencies
pip install -r requirements.txt

# Seed realistic database
python seed_data.py

# Run the test suite
python test_backend.py

# Start the Flask web application
python app.py
```
Open **`http://127.0.0.1:5000`** in your browser.

---

## 🏗️ Project Architecture

```
smartattend/
├── app.py                     # Main Flask web application & REST API
├── database.py                # SQLite schema, connection pool & WAL mode
├── seed_data.py               # Comprehensive realistic data seeder
├── auth.py                    # JWT token management, password hashing & role guards
├── calculations.py           # Mathematical attendance & forecasting engine
├── test_backend.py            # Automated unit and integration test suite
├── requirements.txt           # Python dependencies
├── run.bat                    # 1-click Windows execution batch script
├── uploads/                   # Secure storage for supporting permission documents
├── static/
│   ├── css/
│   │   └── style.css          # College ERP styling & custom scrollbars
│   └── js/
│       ├── api.js             # Client API wrapper, JWT storage & toasts
│       ├── common.js          # Shared navbar, notification bell & drawer
│       ├── student.js         # Student dashboard, calculator & permission forms
│       ├── faculty.js         # Faculty attendance marker & review workflow
│       ├── hod.js             # HOD oversight & escalated approvals
│       └── admin.js           # User management, settings & reports engine
└── templates/
    ├── index.html             # Landing page & unified 1-click login portal
    ├── student.html           # Student portal template
    ├── faculty.html           # Faculty portal template
    ├── hod.html               # HOD portal template
    └── admin.html             # Admin portal template
```

---

## 🧪 Automated Test Suite

Run the test suite to verify math formulas, database integrity, and workflow end-to-end:
```bash
python test_backend.py
```
Expected output:
```
Ran 6 tests in 1.1s
OK
```

---

## 🔒 Security & Institutional Rules
- **Password Hashing**: PBKDF2 with SHA-256 via Werkzeug.
- **Role-Based Authorization**: Protected backend endpoints (`@require_roles`). Students cannot access faculty or admin endpoints.
- **Document Validation**: Allowed formats strictly limited to PDF, JPG, JPEG, and PNG up to 5 MB.
- **Audit Logging**: Every login, attendance modification, and permission approval is logged with actor ID, entity, details, and IP address.
- **WAL Mode**: SQLite Write-Ahead Logging enabled for high concurrency and zero database locks.
