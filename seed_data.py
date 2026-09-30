"""
SmartAttend - Comprehensive Database Seeder
Populates rich college ERP data across Branches, Classes, Faculty, Students, and Subjects.
"""
import os
import random
import datetime
from database import get_db, init_db, DB_PATH
from auth import hash_password

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def create_sample_documents():
    """Create sample PDF documents for verification."""
    pdf_content = b"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj
4 0 obj << /Length 190 >> stream
BT
/F1 18 Tf
50 720 Td
(CITY GENERAL HOSPITAL - MEDICAL CERTIFICATE) Tj
/F1 12 Tf
0 -30 Td
(Date: 15-Sep-2026) Tj
0 -25 Td
(Patient Name: Rahul Sharma  |  USN: 4SJ22CS045) Tj
0 -25 Td
(Diagnosis: Acute Gastroenteritis / Food Poisoning) Tj
0 -25 Td
(Advice: Complete bed rest recommended from 14-Sep-2026 to 16-Sep-2026.) Tj
0 -40 Td
(Dr. S. K. Gupta, MD (Medicine) - Reg No: KMC/48291) Tj
ET
endstream endobj
5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000224 00000 n 
0000000465 00000 n 
trailer << /Size 6 /Root 1 0 R >>
startxref
536
%%EOF"""
    with open(os.path.join(UPLOAD_DIR, "sample_medical_certificate.pdf"), "wb") as f:
        f.write(pdf_content)

    event_pdf = b"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj
4 0 obj << /Length 210 >> stream
BT
/F1 18 Tf
50 720 Td
(OFFICIAL DUTY CERTIFICATE - COLLEGE HACKATHON) Tj
/F1 12 Tf
0 -30 Td
(Date: 22-Sep-2026) Tj
0 -25 Td
(This is to certify that Rahul Sharma (4SJ22CS045) represented) Tj
0 -20 Td
(the Institution at the State Inter-Collegiate Smart India Hackathon) Tj
0 -20 Td
(held on 22-Sep-2026. Granted On-Duty Attendance.) Tj
0 -40 Td
(Prof. Arvind Kumar - Faculty Coordinator) Tj
ET
endstream endobj
5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000224 00000 n 
0000000485 00000 n 
trailer << /Size 6 /Root 1 0 R >>
startxref
556
%%EOF"""
    with open(os.path.join(UPLOAD_DIR, "sample_event_letter.pdf"), "wb") as f:
        f.write(event_pdf)


def seed_database():
    """Populate database with complete sample data."""
    # Remove existing db file so CREATE TABLE creates the upgraded schema
    for f in [DB_PATH, DB_PATH + "-wal", DB_PATH + "-shm"]:
        if os.path.exists(f):
            try:
                os.remove(f)
            except Exception:
                pass

    init_db()
    create_sample_documents()

    with get_db() as conn:
        cursor = conn.cursor()

        # Clean slate for predictable seeding
        cursor.execute("DELETE FROM password_resets")
        cursor.execute("DELETE FROM audit_logs")
        cursor.execute("DELETE FROM notifications")
        cursor.execute("DELETE FROM permission_requests")
        cursor.execute("DELETE FROM attendance")
        cursor.execute("DELETE FROM student_subjects")
        cursor.execute("DELETE FROM faculty_subjects")
        cursor.execute("DELETE FROM subjects")
        cursor.execute("DELETE FROM students")
        cursor.execute("DELETE FROM faculty")
        cursor.execute("DELETE FROM classes")
        cursor.execute("DELETE FROM departments")
        cursor.execute("DELETE FROM branches")
        cursor.execute("DELETE FROM academic_settings")
        cursor.execute("DELETE FROM users")

        default_pwd_hash = hash_password("password123")

        # 1. Academic Settings
        cursor.execute("""
            INSERT INTO academic_settings (minimum_attendance_percentage, academic_year, current_semester)
            VALUES (75.0, '2026-2027', 5)
        """)

        # 2. Branches Master (12 standard engineering branches)
        branches = [
            (1, 'AI&DS', 'Artificial Intelligence and Data Science'),
            (2, 'CSE', 'Computer Science and Engineering'),
            (3, 'ISE', 'Information Science and Engineering'),
            (4, 'ECE', 'Electronics and Communication Engineering'),
            (5, 'EEE', 'Electrical and Electronics Engineering'),
            (6, 'ME', 'Mechanical Engineering'),
            (7, 'CV', 'Civil Engineering'),
            (8, 'AIML', 'Artificial Intelligence and Machine Learning'),
            (9, 'CS-DS', 'Computer Science and Engineering (Data Science)'),
            (10, 'CYBER', 'Cyber Security'),
            (11, 'ROBOTICS', 'Robotics and Automation'),
            (12, 'BIOTECH', 'Biotechnology')
        ]
        for b_id, b_code, b_name in branches:
            cursor.execute("""
                INSERT INTO branches (id, branch_code, branch_name, status)
                VALUES (?, ?, ?, 'ACTIVE')
            """, (b_id, b_code, b_name))
            # Sync departments table
            cursor.execute("""
                INSERT INTO departments (id, code, name) VALUES (?, ?, ?)
            """, (b_id, b_code, b_name))

        # 3. Classes Master Data
        classes = [
            (1, 1, 4, 'A', '2026-2027', '4 AI&DS A'),
            (2, 2, 5, 'A', '2026-2027', '5 CSE A'),
            (3, 4, 5, 'A', '2026-2027', '5 ECE A')
        ]
        for c_id, b_id, sem, sec, acad_yr, c_name in classes:
            cursor.execute("""
                INSERT INTO classes (id, branch_id, semester, section, academic_year, class_name)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (c_id, b_id, sem, sec, acad_yr, c_name))

        # 4. Core Demo Users
        # Admin
        cursor.execute("""
            INSERT INTO users (id, name, email, password_hash, role, status, avatar_url)
            VALUES (1, 'ERP Administrator', 'admin@college.edu', ?, 'ADMIN', 'ACTIVE', 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150')
        """, (default_pwd_hash,))

        # HOD CSE (Dr. Rajesh Sharma, branch_id = 2)
        cursor.execute("""
            INSERT INTO users (id, name, email, password_hash, role, status, avatar_url)
            VALUES (2, 'Dr. Rajesh Sharma', 'hod@college.edu', ?, 'HOD', 'ACTIVE', 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150')
        """, (default_pwd_hash,))
        cursor.execute("""
            INSERT INTO faculty (id, user_id, branch_id, designation)
            VALUES (1, 2, 2, 'Professor & Head, CSE')
        """)

        # Faculty 1 (Prof. Arvind Kumar, CSE Dept, branch_id = 2)
        cursor.execute("""
            INSERT INTO users (id, name, email, password_hash, role, status, avatar_url)
            VALUES (3, 'Prof. Arvind Kumar', 'faculty@college.edu', ?, 'FACULTY', 'ACTIVE', 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=150')
        """, (default_pwd_hash,))
        cursor.execute("""
            INSERT INTO faculty (id, user_id, branch_id, designation)
            VALUES (2, 3, 2, 'Associate Professor')
        """)

        # Faculty 2 (Prof. Priya Nair, CSE)
        cursor.execute("""
            INSERT INTO users (id, name, email, password_hash, role, status, avatar_url)
            VALUES (4, 'Prof. Priya Nair', 'priya.nair@college.edu', ?, 'FACULTY', 'ACTIVE', 'https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=150')
        """, (default_pwd_hash,))
        cursor.execute("""
            INSERT INTO faculty (id, user_id, branch_id, designation)
            VALUES (3, 4, 2, 'Assistant Professor')
        """)

        # Faculty 3 (Prof. Suresh Verma, CSE)
        cursor.execute("""
            INSERT INTO users (id, name, email, password_hash, role, status, avatar_url)
            VALUES (5, 'Prof. Suresh Verma', 'suresh.verma@college.edu', ?, 'FACULTY', 'ACTIVE', 'https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=150')
        """, (default_pwd_hash,))
        cursor.execute("""
            INSERT INTO faculty (id, user_id, branch_id, designation)
            VALUES (4, 5, 2, 'Assistant Professor')
        """)

        # HOD ECE (Dr. Anita Desai, branch_id = 4)
        cursor.execute("""
            INSERT INTO users (id, name, email, password_hash, role, status, avatar_url)
            VALUES (6, 'Dr. Anita Desai', 'anita.desai@college.edu', ?, 'HOD', 'ACTIVE', 'https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=150')
        """, (default_pwd_hash,))
        cursor.execute("""
            INSERT INTO faculty (id, user_id, branch_id, designation)
            VALUES (5, 6, 4, 'Professor & Head, ECE')
        """)

        # HOD AI&DS (Dr. K. S. Rao, branch_id = 1)
        cursor.execute("""
            INSERT INTO users (id, name, email, password_hash, role, status, avatar_url)
            VALUES (7, 'Dr. K. S. Rao', 'hod.aids@college.edu', ?, 'HOD', 'ACTIVE', 'https://images.unsplash.com/photo-1537368910025-700350fe46c7?w=150')
        """, (default_pwd_hash,))
        cursor.execute("""
            INSERT INTO faculty (id, user_id, branch_id, designation)
            VALUES (6, 7, 1, 'Professor & Head, AI & DS')
        """)

        # Faculty AI&DS (Prof. Sneha Iyer, branch_id = 1)
        cursor.execute("""
            INSERT INTO users (id, name, email, password_hash, role, status, avatar_url)
            VALUES (8, 'Prof. Sneha Iyer', 'sneha.iyer@college.edu', ?, 'FACULTY', 'ACTIVE', 'https://images.unsplash.com/photo-1580489944761-15a19d654956?w=150')
        """, (default_pwd_hash,))
        cursor.execute("""
            INSERT INTO faculty (id, user_id, branch_id, designation)
            VALUES (7, 8, 1, 'Assistant Professor')
        """)

        # 5. Core Demo Students
        # Demo Student 1: Rahul Sharma (CSE, Class 5 CSE A, user_id = 9, student_id = 1)
        cursor.execute("""
            INSERT INTO users (id, name, email, password_hash, role, status, avatar_url)
            VALUES (9, 'Rahul Sharma', 'student@college.edu', ?, 'STUDENT', 'ACTIVE', 'https://images.unsplash.com/photo-1539571696357-5a69c17a67c6?w=150')
        """, (default_pwd_hash,))
        cursor.execute("""
            INSERT INTO students (id, user_id, usn, branch_id, class_id, semester, section, academic_year, phone, roll_no)
            VALUES (1, 9, '4SJ22CS045', 2, 2, 5, 'A', '2026-2027', '+91 98765 43210', '45')
        """)

        # Demo Student 2: Venu Gopal (AI&DS, Class 4 AI&DS A, user_id = 10, student_id = 2)
        cursor.execute("""
            INSERT INTO users (id, name, email, password_hash, role, status, avatar_url)
            VALUES (10, 'Venu Gopal', 'venu.aids@college.edu', ?, 'STUDENT', 'ACTIVE', 'https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?w=150')
        """, (default_pwd_hash,))
        cursor.execute("""
            INSERT INTO students (id, user_id, usn, branch_id, class_id, semester, section, academic_year, phone, roll_no)
            VALUES (2, 10, '4SJ23AD001', 1, 1, 4, 'A', '2026-2027', '+91 98123 45678', '01')
        """)

        # Additional 23 CSE Students (Class 5 CSE A, student_id 3 to 25)
        cse_student_names = [
            ("Aakash Gowda", "4SJ22CS001"), ("Aanya Sen", "4SJ22CS002"),
            ("Abhishek Hegde", "4SJ22CS003"), ("Aditi Bhat", "4SJ22CS004"),
            ("Akshay Shenoy", "4SJ22CS005"), ("Ananya Pillai", "4SJ22CS006"),
            ("Arjun Menon", "4SJ22CS007"), ("Bhavana Reddy", "4SJ22CS008"),
            ("Chaitra Kamath", "4SJ22CS009"), ("Darshan Naik", "4SJ22CS010"),
            ("Deepika Nair", "4SJ22CS011"), ("Gautam Prabhu", "4SJ22CS012"),
            ("Harish Kumar", "4SJ22CS013"), ("Ishaan Joshi", "4SJ22CS014"),
            ("Karthik Shetty", "4SJ22CS015"), ("Kavya Kulkarni", "4SJ22CS016"),
            ("Manoj Poojary", "4SJ22CS017"), ("Meghana Acharya", "4SJ22CS018"),
            ("Nikhil Rao", "4SJ22CS019"), ("Pooja Hegde", "4SJ22CS020"),
            ("Pranav DSouza", "4SJ22CS021"), ("Rithika Shetty", "4SJ22CS022"),
            ("Sneha Kulkarni", "4SJ22CS024")
        ]

        curr_user_id = 11
        curr_student_id = 3
        for name, usn in cse_student_names:
            sanitized = name.lower().replace(' ', '.').replace("'", "")
            email = f"{sanitized}@college.edu"
            cursor.execute("""
                INSERT INTO users (id, name, email, password_hash, role, status)
                VALUES (?, ?, ?, ?, 'STUDENT', 'ACTIVE')
            """, (curr_user_id, name, email, default_pwd_hash))
            cursor.execute("""
                INSERT INTO students (id, user_id, usn, branch_id, class_id, semester, section, academic_year, phone, roll_no)
                VALUES (?, ?, ?, 2, 2, 5, 'A', '2026-2027', '+91 99000 11223', ?)
            """, (curr_student_id, curr_user_id, usn, str(curr_student_id).zfill(2)))
            curr_user_id += 1
            curr_student_id += 1

        # Additional 5 AI&DS Students (Class 4 AI&DS A, student_id 26 to 30)
        aids_student_names = [
            ("Aniket Sharma", "4SJ23AD002"),
            ("Divya Nair", "4SJ23AD003"),
            ("Karan Patel", "4SJ23AD004"),
            ("Neha Gupta", "4SJ23AD005"),
            ("Siddharth Roy", "4SJ23AD006")
        ]
        for name, usn in aids_student_names:
            sanitized = name.lower().replace(' ', '.').replace("'", "")
            email = f"{sanitized}@college.edu"
            cursor.execute("""
                INSERT INTO users (id, name, email, password_hash, role, status)
                VALUES (?, ?, ?, ?, 'STUDENT', 'ACTIVE')
            """, (curr_user_id, name, email, default_pwd_hash))
            cursor.execute("""
                INSERT INTO students (id, user_id, usn, branch_id, class_id, semester, section, academic_year, phone, roll_no)
                VALUES (?, ?, ?, 1, 1, 4, 'A', '2026-2027', '+91 97000 33445', ?)
            """, (curr_student_id, curr_user_id, usn, str(curr_student_id).zfill(2)))
            curr_user_id += 1
            curr_student_id += 1

        # Additional 5 ECE Students (Class 5 ECE A, student_id 31 to 35)
        ece_student_names = [
            ("Varun Deshpande", "4SJ22EC001"),
            ("Vidya Shankar", "4SJ22EC002"),
            ("Yashasvi Pai", "4SJ22EC003"),
            ("Zainab Khan", "4SJ22EC004"),
            ("Chethan Urs", "4SJ22EC005")
        ]
        for name, usn in ece_student_names:
            sanitized = name.lower().replace(' ', '.').replace("'", "")
            email = f"{sanitized}@college.edu"
            cursor.execute("""
                INSERT INTO users (id, name, email, password_hash, role, status)
                VALUES (?, ?, ?, ?, 'STUDENT', 'ACTIVE')
            """, (curr_user_id, name, email, default_pwd_hash))
            cursor.execute("""
                INSERT INTO students (id, user_id, usn, branch_id, class_id, semester, section, academic_year, phone, roll_no)
                VALUES (?, ?, ?, 4, 3, 5, 'A', '2026-2027', '+91 96000 55667', ?)
            """, (curr_student_id, curr_user_id, usn, str(curr_student_id).zfill(2)))
            curr_user_id += 1
            curr_student_id += 1

        # 6. Subjects (Linked to Branches and Subject Types)
        subjects = [
            # CSE Subjects (branch 2)
            (1, 'CS501', 'Database Management Systems', 2, 5, 4, 'Theory', 'Relational models, SQL, Normalization and Transaction processing', 45, 75.0),
            (2, 'CS502', 'Advanced Java Programming', 2, 5, 4, 'Theory', 'Multithreading, Collections, Spring Boot and REST APIs', 45, 75.0),
            (3, 'CS503', 'Data Structures & Algorithms', 2, 5, 4, 'Theory', 'Trees, Graphs, Dynamic Programming and Algorithm Analysis', 45, 75.0),
            (4, 'CS504', 'Web Technologies', 2, 5, 3, 'Practical', 'HTML5, CSS3, JavaScript, Node.js and Single Page Applications', 40, 75.0),
            (5, 'CS505', 'Operating Systems', 2, 5, 4, 'Theory', 'Process scheduling, Memory management and File systems', 45, 75.0),
            (6, 'CS506', 'Computer Networks', 2, 5, 3, 'Theory', 'OSI model, TCP/IP, Routing algorithms and Network Security', 40, 75.0),
            # AI&DS Subjects (branch 1)
            (7, '21AD52', 'Database Management Systems', 1, 4, 4, 'Theory', 'Database concepts, SQL, normalization, transactions and database design for AI systems.', 45, 75.0),
            (8, '21AD53', 'Python for Data Science', 1, 4, 4, 'Laboratory', 'NumPy, Pandas, Matplotlib, Scikit-learn and exploratory data analysis', 45, 75.0),
            (9, '21AD54', 'Operating Systems', 1, 4, 3, 'Theory', 'Process synchronization, concurrency and virtualization in distributed systems', 40, 75.0),
            # ECE Subjects (branch 4)
            (10, 'EC501', 'Digital Signal Processing', 4, 5, 4, 'Theory', 'Discrete-time signals, DFT, FFT and filter designs', 45, 75.0),
            (11, 'EC502', 'Microcontrollers & Embedded Systems', 4, 5, 4, 'Practical', 'ARM Cortex architecture, GPIO programming and interfacing', 45, 75.0)
        ]
        for sub in subjects:
            cursor.execute("""
                INSERT INTO subjects (id, subject_code, subject_name, branch_id, semester, credits, subject_type, description, planned_classes, minimum_attendance)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, sub)

        # 7. Faculty-Subject Allocations (Linked to Class)
        faculty_subject_allocations = [
            (1, 2, 1, 2),  # Prof Arvind -> CS501 for Class 2 (5 CSE A)
            (2, 2, 4, 2),  # Prof Arvind -> CS504 for Class 2 (5 CSE A)
            (3, 2, 7, 1),  # Prof Arvind -> 21AD52 (DBMS) for Class 1 (4 AI&DS A) [Demonstrating multi-class allocation!]
            (4, 3, 2, 2),  # Prof Priya  -> CS502 for Class 2 (5 CSE A)
            (5, 4, 3, 2),  # Prof Suresh -> CS503 for Class 2 (5 CSE A)
            (6, 7, 8, 1),  # Prof Sneha  -> 21AD53 for Class 1 (4 AI&DS A)
            (7, 7, 9, 1),  # Prof Sneha  -> 21AD54 for Class 1 (4 AI&DS A)
            (8, 5, 10, 3), # Dr Anita   -> EC501 for Class 3 (5 ECE A)
            (9, 5, 11, 3)  # Dr Anita   -> EC502 for Class 3 (5 ECE A)
        ]
        for fs_id, fac_id, sub_id, cls_id in faculty_subject_allocations:
            cursor.execute("""
                INSERT INTO faculty_subjects (id, faculty_id, subject_id, class_id, academic_year)
                VALUES (?, ?, ?, ?, '2026-2027')
            """, (fs_id, fac_id, sub_id, cls_id))

        # 8. Student-Subject Enrollment (Only enrolled in their class subjects)
        # Class 2 (5 CSE A): Students 1 and 3-25 enrolled in subjects 1-6
        for st_id in [1] + list(range(3, 26)):
            for fs_id, fac_id, sub_id, cls_id in faculty_subject_allocations:
                if cls_id == 2:
                    cursor.execute("""
                        INSERT INTO student_subjects (student_id, subject_id, faculty_subject_id, academic_year)
                        VALUES (?, ?, ?, '2026-2027')
                    """, (st_id, sub_id, fs_id))

        # Class 1 (4 AI&DS A): Students 2 and 26-30 enrolled in subjects 7-9
        for st_id in [2] + list(range(26, 31)):
            for fs_id, fac_id, sub_id, cls_id in faculty_subject_allocations:
                if cls_id == 1:
                    cursor.execute("""
                        INSERT INTO student_subjects (student_id, subject_id, faculty_subject_id, academic_year)
                        VALUES (?, ?, ?, '2026-2027')
                    """, (st_id, sub_id, fs_id))

        # Class 3 (5 ECE A): Students 31-35 enrolled in subjects 10-11
        for st_id in range(31, 36):
            for fs_id, fac_id, sub_id, cls_id in faculty_subject_allocations:
                if cls_id == 3:
                    cursor.execute("""
                        INSERT INTO student_subjects (student_id, subject_id, faculty_subject_id, academic_year)
                        VALUES (?, ?, ?, '2026-2027')
                    """, (st_id, sub_id, fs_id))

        # 9. Realistic Attendance for CSE Class 2 (past 4 weeks)
        # Rahul Sharma (student 1) attendance numbers:
        # CS501: 40 conducted, 34 attended (85%)
        # CS502: 35 conducted, 25 attended (71.4%) -> LOW ATTENDANCE
        # CS503: 42 conducted, 35 attended (83.3%)
        # CS504: 36 conducted, 28 attended (77.8%)
        # CS505: 38 conducted, 29 attended (76.3%)
        # CS506: 37 conducted, 31 attended (83.8%)
        subject_faculty_map = {1: 2, 2: 3, 3: 4, 4: 2, 5: 3, 6: 4}
        rahul_specs = {
            1: {"conducted": 40, "attended": 34},
            2: {"conducted": 35, "attended": 25},
            3: {"conducted": 42, "attended": 35},
            4: {"conducted": 36, "attended": 28},
            5: {"conducted": 38, "attended": 29},
            6: {"conducted": 37, "attended": 31}
        }
        absent_indices_rahul = {}
        for sub_id, spec in rahul_specs.items():
            needed_absent = spec["conducted"] - spec["attended"]
            step = max(1, spec["conducted"] // max(1, needed_absent))
            absent_indices_rahul[sub_id] = set(range(1, spec["conducted"] + 1, step)[:needed_absent])

        session_list = []
        start_date = datetime.date(2026, 9, 1)
        day_offset = 0
        hour_counter = {sub_id: 0 for sub_id in range(1, 7)}
        while any(hour_counter[s] < rahul_specs[s]["conducted"] for s in range(1, 7)):
            curr_date = start_date + datetime.timedelta(days=day_offset)
            day_offset += 1
            if curr_date.weekday() >= 5:
                continue
            day_hour = 1
            for sub_id in range(1, 7):
                if hour_counter[sub_id] < rahul_specs[sub_id]["conducted"] and day_hour <= 6:
                    session_list.append((sub_id, curr_date.strftime("%Y-%m-%d"), day_hour, subject_faculty_map[sub_id]))
                    hour_counter[sub_id] += 1
                    day_hour += 1

        sub_session_idx = {s: 0 for s in range(1, 7)}
        low_att_students = {5: 0.65, 10: 0.68, 17: 0.70}
        random.seed(42)

        for sub_id, date_str, hour, fac_id in session_list:
            sub_session_idx[sub_id] += 1
            idx = sub_session_idx[sub_id]
            is_absent_rahul = idx in absent_indices_rahul[sub_id]
            rahul_status = 'ABSENT' if is_absent_rahul else 'PRESENT'

            if sub_id == 1 and date_str == '2026-09-15' and hour == 2:
                rahul_status = 'APPROVED_PERMISSION'
                orig_status = 'ABSENT'
                audit_notes = 'Attendance credited via Permission Request PR-2026-001 (Medical Emergency)'
                perm_id = 1
            else:
                orig_status = None
                audit_notes = ''
                perm_id = None

            cursor.execute("""
                INSERT INTO attendance (student_id, subject_id, faculty_id, date, hour, status, original_status, audit_notes, permission_request_id)
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (sub_id, fac_id, date_str, hour, rahul_status, orig_status, audit_notes, perm_id))

            for st_id in [s for s in list(range(3, 26))]:
                prob = 0.88
                if st_id in low_att_students:
                    prob = low_att_students[st_id]
                status = 'PRESENT' if random.random() < prob else 'ABSENT'
                cursor.execute("""
                    INSERT INTO attendance (student_id, subject_id, faculty_id, date, hour, status)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (st_id, sub_id, fac_id, date_str, hour, status))

        # Attendance for AI&DS Class 1 (Students 2 and 26-30 in subjects 7-9)
        aids_sessions = [
            (7, '2026-09-08', 1, 2),
            (7, '2026-09-10', 2, 2),
            (7, '2026-09-15', 3, 2),
            (7, '2026-09-17', 1, 2),
            (7, '2026-09-22', 2, 2),
            (8, '2026-09-09', 2, 7),
            (8, '2026-09-11', 1, 7),
            (8, '2026-09-16', 4, 7),
            (8, '2026-09-23', 3, 7),
            (9, '2026-09-12', 3, 7),
            (9, '2026-09-18', 2, 7),
            (9, '2026-09-24', 1, 7)
        ]
        for sub_id, date_str, hour, fac_id in aids_sessions:
            for st_id in [2] + list(range(26, 31)):
                status = 'PRESENT' if random.random() < 0.86 else 'ABSENT'
                cursor.execute("""
                    INSERT INTO attendance (student_id, subject_id, faculty_id, date, hour, status)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (st_id, sub_id, fac_id, date_str, hour, status))

        # 10. Permission Requests with branch_id for Strict HOD Isolation
        # Request 1: Approved CSE request (Rahul Sharma, CS501 DBMS, branch_id = 2)
        cursor.execute("""
            INSERT INTO permission_requests (
                id, request_code, student_id, subject_id, faculty_id, branch_id, date, hour,
                reason, description, document_filename, document_original_name,
                status, faculty_comment, hod_comment, reviewed_by, reviewed_at, created_at
            ) VALUES (
                1, 'PR-2026-001', 1, 1, 2, 2, '2026-09-15', 2,
                'Medical Emergency',
                'Suffered severe food poisoning with fever; hospitalized for day observation.',
                'sample_medical_certificate.pdf', 'Hospital_Discharge_Summary.pdf',
                'APPROVED',
                'Verified medical certificate from City Hospital. Legitimate medical emergency. Attendance granted.',
                '', 3, '2026-09-16 11:30:00', '2026-09-15 18:45:00'
            )
        """)

        # Request 2: Pending CSE request (Rahul Sharma, CS502 Java, branch_id = 2)
        cursor.execute("""
            INSERT INTO permission_requests (
                id, request_code, student_id, subject_id, faculty_id, branch_id, date, hour,
                reason, description, document_filename, document_original_name,
                status, faculty_comment, hod_comment, created_at
            ) VALUES (
                2, 'PR-2026-002', 1, 2, 3, 2, '2026-09-22', 1,
                'College Event',
                'Participated in State-level Inter-College Smart India Hackathon representing our CSE department.',
                'sample_event_letter.pdf', 'Hackathon_Participation_Proof.pdf',
                'PENDING', '', '', '2026-09-22 17:15:00'
            )
        """)

        # Request 3: Escalated to CSE HOD (Rahul Sharma, CS503 DSA, branch_id = 2)
        cursor.execute("""
            INSERT INTO permission_requests (
                id, request_code, student_id, subject_id, faculty_id, branch_id, date, hour,
                reason, description, document_filename, document_original_name,
                status, faculty_comment, hod_comment, reviewed_by, reviewed_at, created_at
            ) VALUES (
                3, 'PR-2026-003', 1, 3, 4, 2, '2026-09-24', 3,
                'Hospital Visit',
                'Consultation for orthopedic examination following knee sprain.',
                'sample_medical_certificate.pdf', 'Orthopedic_Clinic_Slip.pdf',
                'ESCALATED_HOD',
                'Forwarding to HOD Dr. Rajesh Sharma for policy discretion.',
                '', 5, '2026-09-25 10:15:00', '2026-09-24 19:20:00'
            )
        """)

        # Request 4: Escalated to AI&DS HOD (Venu Gopal, 21AD52 DBMS, branch_id = 1) -> ONLY visible to Dr. K. S. Rao!
        cursor.execute("""
            INSERT INTO permission_requests (
                id, request_code, student_id, subject_id, faculty_id, branch_id, date, hour,
                reason, description, document_filename, document_original_name,
                status, faculty_comment, hod_comment, reviewed_by, reviewed_at, created_at
            ) VALUES (
                4, 'PR-2026-004', 2, 7, 2, 1, '2026-09-17', 1,
                'Official Representation',
                'Represented the AI&DS department at National Data Analytics Symposium.',
                'sample_event_letter.pdf', 'Symposium_OD_Letter.pdf',
                'ESCALATED_HOD',
                'Faculty recommends duty leave approval. Escalated for AI&DS HOD sanction.',
                '', 3, '2026-09-18 10:00:00', '2026-09-17 18:00:00'
            )
        """)

        # 11. Initial Notifications
        notifs = [
            (9, "Low Attendance Warning ⚠", "Your attendance in Advanced Java Programming (CS502) is 71.4%. Attend at least 5 consecutive classes.", "WARNING", "/student#calculator"),
            (9, "Permission Approved ✓", "Your permission request PR-2026-001 for DBMS was approved by Prof. Arvind Kumar.", "PERMISSION", "/student#permissions"),
            (2, "Escalated Permission Awaiting Review", "Prof. Suresh Verma has escalated PR-2026-003 (Rahul Sharma, CSE) for your review.", "PERMISSION", "/hod#permissions"),
            (7, "AI&DS Leave Request Escalated", "Prof. Arvind Kumar escalated PR-2026-004 (Venu Gopal, AI&DS) for your review.", "PERMISSION", "/hod#permissions"),
            (1, "SmartAttend Academic ERP Initialized", "System updated with Branch Isolation, Class Master Data, and Dynamic Allocation.", "SYSTEM", "/admin#dashboard")
        ]
        for n in notifs:
            cursor.execute("""
                INSERT INTO notifications (user_id, title, message, type, link)
                VALUES (?, ?, ?, ?, ?)
            """, n)

        # 12. Audit Logs
        audit_entries = [
            (1, "INITIALIZE_SYSTEM", "SYSTEM", "1", "Seeded branches, classes, subjects, faculty and students.", "127.0.0.1"),
            (3, "ALLOCATE_SUBJECT", "SUBJECT", "21AD52", "Prof. Arvind Kumar allocated 21AD52 to Class 4 AI&DS A.", "192.168.1.15"),
            (3, "ASSIGN_STUDENTS", "CLASS", "4 AI&DS A", "Assigned 6 students of 4 AI&DS A to subject 21AD52.", "192.168.1.15")
        ]
        for a in audit_entries:
            cursor.execute("""
                INSERT INTO audit_logs (user_id, action, entity_type, entity_id, details, ip_address)
                VALUES (?, ?, ?, ?, ?, ?)
            """, a)

    print("SmartAttend database re-seeded successfully with Updated Access Control Schema!")
    print("Demo Accounts:")
    print("  Student (CSE):   student@college.edu    / password123 (Rahul Sharma, 5 CSE A)")
    print("  Student (AI&DS): venu.aids@college.edu  / password123 (Venu Gopal, 4 AI&DS A)")
    print("  Faculty (CSE):   faculty@college.edu    / password123 (Prof. Arvind Kumar)")
    print("  HOD (CSE):       hod@college.edu        / password123 (Dr. Rajesh Sharma)")
    print("  HOD (AI&DS):     hod.aids@college.edu   / password123 (Dr. K. S. Rao)")
    print("  Admin:           admin@college.edu      / password123 (ERP Administrator)")


if __name__ == "__main__":
    seed_database()
