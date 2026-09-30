"""
SmartAttend - Authentication, JWT Token Management, Role Guards, Password Policy, and Audit Logger
"""
import datetime
import functools
import os
import re
import jwt
from flask import request, jsonify, g, session
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db

JWT_SECRET = os.environ.get("JWT_SECRET", "smartattend-super-secret-key-2026-prod")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24


def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Validate that password satisfies institutional security requirements:
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one number
    - At least one special character
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter (A-Z)."
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter (a-z)."
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one numeric digit (0-9)."
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{}|;:,.<>?/`~]", password):
        return False, "Password must contain at least one special character (!@#$%^&*...)."
    return True, ""


def hash_password(password: str) -> str:
    """Generate secure password hash using PBKDF2 with SHA-256."""
    return generate_password_hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify plain password against hashed password."""
    return check_password_hash(password_hash, password)


def create_token(user_id: int, role: str, email: str, name: str) -> str:
    """Create a signed JWT token."""
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "user_id": user_id,
        "role": role,
        "email": email,
        "name": name,
        "exp": now + datetime.timedelta(hours=JWT_EXPIRATION_HOURS),
        "iat": now
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def get_current_user():
    """Retrieve currently authenticated user with associated branch, department, and class metadata."""
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1].strip()
    
    if not token and request.cookies.get("smartattend_token"):
        token = request.cookies.get("smartattend_token")
    
    user_id = None
    if token:
        payload = decode_token(token)
        if payload:
            user_id = payload.get("user_id")
    elif "user_id" in session:
        user_id = session["user_id"]
        
    if not user_id:
        return None
        
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, email, role, status, avatar_url, phone FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        if row and row["status"] == "ACTIVE":
            user_data = dict(row)
            
            # Role-specific profile details
            if user_data["role"] == "STUDENT":
                cursor.execute("""
                    SELECT s.id as student_id, s.usn, s.semester, s.section, s.academic_year,
                           s.phone, s.roll_no, s.class_id,
                           b.id as branch_id, b.branch_name, b.branch_code,
                           c.class_name
                    FROM students s
                    JOIN branches b ON s.branch_id = b.id
                    LEFT JOIN classes c ON s.class_id = c.id
                    WHERE s.user_id = ?
                """, (user_id,))
                st_row = cursor.fetchone()
                if st_row:
                    st_dict = dict(st_row)
                    if not st_dict.get("phone") and user_data.get("phone"):
                        st_dict["phone"] = user_data["phone"]
                    elif st_dict.get("phone") and not user_data.get("phone"):
                        user_data["phone"] = st_dict["phone"]
                    user_data["student"] = st_dict
                    user_data["branch_id"] = st_row["branch_id"]
                    user_data["branch_name"] = st_row["branch_name"]

            elif user_data["role"] in ("FACULTY", "HOD"):
                cursor.execute("""
                    SELECT f.id as faculty_id, f.designation, f.branch_id,
                           b.branch_name, b.branch_code
                    FROM faculty f
                    JOIN branches b ON f.branch_id = b.id
                    WHERE f.user_id = ?
                """, (user_id,))
                fac_row = cursor.fetchone()
                if fac_row:
                    user_data["faculty"] = dict(fac_row)
                    user_data["branch_id"] = fac_row["branch_id"]
                    user_data["branch_name"] = fac_row["branch_name"]

            return user_data
    return None


def require_auth(f):
    """Decorator to enforce authenticated user."""
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({"error": "Authentication required. Please login."}), 401
        g.current_user = user
        return f(*args, **kwargs)
    return decorated_function


def require_roles(*roles):
    """Decorator to enforce role-based access control."""
    def decorator(f):
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            if not user:
                return jsonify({"error": "Authentication required. Please login."}), 401
            if user["role"] not in roles:
                return jsonify({
                    "error": "Forbidden: You do not have permission to access this resource.",
                    "required_roles": list(roles),
                    "user_role": user["role"]
                }), 403
            g.current_user = user
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def log_audit(user_id: int, action: str, entity_type: str, entity_id: str = "", details: str = ""):
    """Record administrative or critical action in audit log."""
    try:
        ip = request.remote_addr or "127.0.0.1" if request else "127.0.0.1"
    except Exception:
        ip = "127.0.0.1"
        
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO audit_logs (user_id, action, entity_type, entity_id, details, ip_address)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, action, entity_type, str(entity_id), details, ip))
    except Exception as e:
        print(f"Error logging audit: {e}")


def create_notification(user_id: int, title: str, message: str, notif_type: str = "ALERT", link: str = ""):
    """Create a persistent in-app notification for a user."""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO notifications (user_id, title, message, type, link)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, title, message, notif_type, link))
    except Exception as e:
        print(f"Error creating notification: {e}")
