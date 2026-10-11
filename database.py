"""
SmartAttend - Database Schema and Helper Functions
SQLite3 Relational Database Implementation with Request-Scoped Connection, WAL Mode,
and Comprehensive Academic Allocation Schema (Branches, Classes, Subjects, Allocations)
"""
import os
import sqlite3
from contextlib import contextmanager
from flask import g, has_app_context

DB_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DB_DIR, "smartattend.db")


def create_connection():
    """Create and configure a SQLite connection."""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


@contextmanager
def get_db():
    """
    Context manager for SQLite database connection.
    If within a Flask app context, reuses g.db to avoid nested transaction locks.
    """
    if has_app_context():
        if "db" not in g or g.db is None:
            g.db = create_connection()
        conn = g.db
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    else:
        conn = create_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def close_db(e=None):
    """Closes the database again at the end of the request."""
    if has_app_context():
        db = g.pop("db", None)
        if db is not None:
            db.close()


def init_db():
    """Initialize database tables with constraints and indexes."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # 1. Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('STUDENT', 'FACULTY', 'HOD', 'ADMIN')),
                status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE', 'DISABLED')),
                avatar_url TEXT DEFAULT '',
                phone TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Migration: Ensure phone column exists in users table
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN phone TEXT DEFAULT ''")
        except Exception:
            pass
        
        # 2. Branches / Departments table (dedicated, expandable)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS branches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                branch_code TEXT UNIQUE NOT NULL COLLATE NOCASE,
                branch_name TEXT UNIQUE NOT NULL COLLATE NOCASE,
                status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE', 'DISABLED')),
                created_by INTEGER DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
            )
        """)

        # Also support legacy alias 'departments' view or table if needed
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS departments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL COLLATE NOCASE,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 3. Classes table (Class Master Data)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS classes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                branch_id INTEGER NOT NULL,
                semester INTEGER NOT NULL,
                section TEXT NOT NULL,
                academic_year TEXT NOT NULL DEFAULT '2026-2027',
                class_name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(branch_id, semester, section, academic_year),
                FOREIGN KEY (branch_id) REFERENCES branches(id) ON DELETE RESTRICT
            )
        """)

        # 4. Faculty table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS faculty (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                branch_id INTEGER NOT NULL,
                department_id INTEGER DEFAULT 1,
                designation TEXT NOT NULL DEFAULT 'Assistant Professor',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (branch_id) REFERENCES branches(id) ON DELETE RESTRICT
            )
        """)
        
        # 5. Students table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                usn TEXT UNIQUE NOT NULL COLLATE NOCASE,
                branch_id INTEGER NOT NULL,
                department_id INTEGER DEFAULT 1,
                class_id INTEGER DEFAULT NULL,
                semester INTEGER NOT NULL DEFAULT 5,
                section TEXT NOT NULL DEFAULT 'A',
                academic_year TEXT NOT NULL DEFAULT '2026-2027',
                phone TEXT DEFAULT '',
                roll_no TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (branch_id) REFERENCES branches(id) ON DELETE RESTRICT,
                FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE SET NULL
            )
        """)

        # Migration: Ensure profile enhancement columns exist in students table
        for col_def in [
            "emergency_contact TEXT DEFAULT ''",
            "blood_group TEXT DEFAULT ''",
            "bio TEXT DEFAULT ''"
        ]:
            try:
                cursor.execute(f"ALTER TABLE students ADD COLUMN {col_def}")
            except Exception:
                pass
        
        # 6. Subjects table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_code TEXT UNIQUE NOT NULL COLLATE NOCASE,
                subject_name TEXT NOT NULL,
                branch_id INTEGER NOT NULL,
                department_id INTEGER DEFAULT 1,
                semester INTEGER NOT NULL DEFAULT 5,
                credits INTEGER NOT NULL DEFAULT 4,
                subject_type TEXT NOT NULL DEFAULT 'Theory' CHECK(subject_type IN ('Theory', 'Practical', 'Laboratory', 'Tutorial', 'Seminar', 'Project')),
                description TEXT DEFAULT '',
                planned_classes INTEGER NOT NULL DEFAULT 45,
                minimum_attendance REAL NOT NULL DEFAULT 75.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (branch_id) REFERENCES branches(id) ON DELETE RESTRICT
            )
        """)
        
        # 7. Faculty-Subjects assignment table (Linked to Class)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS faculty_subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                faculty_id INTEGER NOT NULL,
                subject_id INTEGER NOT NULL,
                class_id INTEGER DEFAULT NULL,
                academic_year TEXT NOT NULL DEFAULT '2026-2027',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(faculty_id, subject_id, class_id, academic_year),
                FOREIGN KEY (faculty_id) REFERENCES faculty(id) ON DELETE CASCADE,
                FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
                FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE SET NULL
            )
        """)
        
        # 8. Student-Subjects enrollment table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS student_subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                subject_id INTEGER NOT NULL,
                faculty_subject_id INTEGER DEFAULT NULL,
                academic_year TEXT NOT NULL DEFAULT '2026-2027',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(student_id, subject_id, academic_year),
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
                FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
                FOREIGN KEY (faculty_subject_id) REFERENCES faculty_subjects(id) ON DELETE SET NULL
            )
        """)
        
        # 9. Attendance records table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                subject_id INTEGER NOT NULL,
                faculty_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                hour INTEGER NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('PRESENT', 'ABSENT', 'APPROVED_PERMISSION')),
                original_status TEXT DEFAULT NULL,
                updated_by INTEGER DEFAULT NULL,
                audit_notes TEXT DEFAULT '',
                permission_request_id INTEGER DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(student_id, subject_id, date, hour),
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
                FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE RESTRICT,
                FOREIGN KEY (faculty_id) REFERENCES faculty(id) ON DELETE RESTRICT,
                FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE SET NULL
            )
        """)
        
        # 10. Permission Requests table (with branch_id for HOD isolation)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS permission_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_code TEXT UNIQUE NOT NULL,
                student_id INTEGER NOT NULL,
                subject_id INTEGER NOT NULL,
                faculty_id INTEGER NOT NULL,
                branch_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                hour INTEGER NOT NULL,
                reason TEXT NOT NULL,
                description TEXT NOT NULL,
                document_filename TEXT DEFAULT '',
                document_original_name TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'PENDING' CHECK(status IN ('PENDING', 'UNDER_REVIEW', 'APPROVED', 'REJECTED', 'ESCALATED_HOD')),
                faculty_comment TEXT DEFAULT '',
                hod_comment TEXT DEFAULT '',
                reviewed_by INTEGER DEFAULT NULL,
                reviewed_at TIMESTAMP DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
                FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE RESTRICT,
                FOREIGN KEY (faculty_id) REFERENCES faculty(id) ON DELETE RESTRICT,
                FOREIGN KEY (branch_id) REFERENCES branches(id) ON DELETE RESTRICT,
                FOREIGN KEY (reviewed_by) REFERENCES users(id) ON DELETE SET NULL
            )
        """)
        
        # 11. Notifications table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                type TEXT NOT NULL DEFAULT 'ALERT' CHECK(type IN ('ATTENDANCE', 'PERMISSION', 'ALERT', 'SYSTEM', 'WARNING')),
                read_status INTEGER NOT NULL DEFAULT 0,
                link TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        
        # 12. Academic Settings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS academic_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                minimum_attendance_percentage REAL NOT NULL DEFAULT 75.0,
                academic_year TEXT NOT NULL DEFAULT '2026-2027',
                current_semester INTEGER NOT NULL DEFAULT 5,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 13. Audit Logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id TEXT DEFAULT '',
                details TEXT DEFAULT '',
                ip_address TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
            )
        """)

        # 14. Password Resets table (for OTP / secure tokens)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS password_resets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                email TEXT NOT NULL,
                token_hash TEXT NOT NULL,
                otp TEXT NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                used INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        
        # Indexes for fast lookup & branch isolation
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_branches_code ON branches(branch_code)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_classes_lookup ON classes(branch_id, semester, section)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_students_branch ON students(branch_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_students_class ON students(class_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_faculty_branch ON faculty(branch_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_subjects_branch ON subjects(branch_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_attendance_student ON attendance(student_id, subject_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(date, hour)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_permission_student ON permission_requests(student_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_permission_branch ON permission_requests(branch_id, status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_permission_faculty ON permission_requests(faculty_id, status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, read_status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(created_at DESC)")


if __name__ == "__main__":
    init_db()
    print("Database tables initialized successfully at:", DB_PATH)
