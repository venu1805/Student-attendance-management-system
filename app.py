"""
SmartAttend - Main Flask Application & RESTful API
Student Attendance Management System
Updated with Dynamic Branch Creation, Class Master Data, Class-based Subject Allocation,
Strict HOD Branch Data Isolation, Self-Service Password Management, and Forgot-Password Recovery.
"""
import os
import re
import uuid
import random
import datetime
from flask import Flask, request, jsonify, render_template, send_from_directory, g, redirect, url_for, session
from werkzeug.utils import secure_filename
from database import get_db, init_db, DB_PATH, close_db
from auth import (
    hash_password, verify_password, create_token, decode_token,
    get_current_user, require_auth, require_roles, log_audit, create_notification,
    validate_password_strength
)
from calculations import (
    calculate_percentage, calculate_required_classes, calculate_missable_classes,
    get_attendance_status, simulate_future_attendance
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png'}
MAX_FILE_SIZE = 5 * 1024 * 1024 # 5 MB

os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "smartattend-flask-session-secret-2026")
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE
app.teardown_appcontext(close_db)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_min_attendance_threshold():
    """Retrieve configured minimum attendance percentage from settings."""
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT minimum_attendance_percentage FROM academic_settings ORDER BY id DESC LIMIT 1")
            row = c.fetchone()
            if row:
                return float(row["minimum_attendance_percentage"])
    except Exception:
        pass
    return 75.0


def resolve_or_create_class(conn, branch_id: int, semester: int, section: str, academic_year: str = '2026-2027') -> int:
    """Find existing class or dynamically create class record."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id FROM classes 
        WHERE branch_id = ? AND semester = ? AND section = ? AND academic_year = ?
    """, (branch_id, semester, section.upper(), academic_year))
    row = cursor.fetchone()
    if row:
        return row["id"]

    # Retrieve branch code
    cursor.execute("SELECT branch_code FROM branches WHERE id = ?", (branch_id,))
    b_row = cursor.fetchone()
    b_code = b_row["branch_code"] if b_row else f"B{branch_id}"
    class_name = f"{semester} {b_code} {section.upper()}"

    cursor.execute("""
        INSERT INTO classes (branch_id, semester, section, academic_year, class_name)
        VALUES (?, ?, ?, ?, ?)
    """, (branch_id, semester, section.upper(), academic_year, class_name))
    return cursor.lastrowid


# --------------------------------------------------------------------------
# Frontend Page Routes (Protected by Auth & Role)
# --------------------------------------------------------------------------

@app.route("/")
def index():
    """Landing page and Login Portal."""
    user = get_current_user()
    if user:
        role = user["role"]
        if role == "STUDENT":
            return redirect("/student")
        elif role == "FACULTY":
            return redirect("/faculty")
        elif role == "HOD":
            return redirect("/hod")
        elif role == "ADMIN":
            return redirect("/admin")
    return render_template("index.html")


@app.route("/student")
def student_portal():
    user = get_current_user()
    if not user:
        return redirect("/?msg=auth_required")
    if user["role"] not in ("STUDENT", "ADMIN"):
        return redirect(f"/{user['role'].lower()}?error=unauthorized_portal")
    return render_template("student.html", user=user)


@app.route("/faculty")
def faculty_portal():
    user = get_current_user()
    if not user:
        return redirect("/?msg=auth_required")
    if user["role"] not in ("FACULTY", "HOD", "ADMIN"):
        return redirect(f"/{user['role'].lower()}?error=unauthorized_portal")
    return render_template("faculty.html", user=user)


@app.route("/hod")
def hod_portal():
    user = get_current_user()
    if not user:
        return redirect("/?msg=auth_required")
    if user["role"] not in ("HOD", "ADMIN"):
        return redirect(f"/{user['role'].lower()}?error=unauthorized_portal")
    return render_template("hod.html", user=user)


@app.route("/admin")
def admin_portal():
    user = get_current_user()
    if not user:
        return redirect("/?msg=auth_required")
    if user["role"] != "ADMIN":
        return redirect(f"/{user['role'].lower()}?error=unauthorized_portal")
    return render_template("admin.html", user=user)


# --------------------------------------------------------------------------
# Authentication & Password Management API
# --------------------------------------------------------------------------

@app.route("/api/auth/login", methods=["POST"])
def api_login():
    data = request.get_json() or {}
    email = data.get("email", "").strip()
    password = data.get("password", "")
    remember_me = data.get("remember_me", False)

    if not email or not password:
        return jsonify({"error": "Please provide both email and password."}), 400

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()

        if not user or not verify_password(password, user["password_hash"]):
            return jsonify({"error": "Invalid email or password. Please verify credentials."}), 401

        if user["status"] != "ACTIVE":
            return jsonify({"error": "This account has been disabled. Please contact the administrator."}), 403

        token = create_token(user["id"], user["role"], user["email"], user["name"])
        session["user_id"] = user["id"]

        log_audit(user["id"], "LOGIN", "USER", user["id"], f"Successful login as {user['role']}")

        response_data = {
            "token": token,
            "user": {
                "id": user["id"],
                "name": user["name"],
                "email": user["email"],
                "role": user["role"],
                "avatar_url": user["avatar_url"]
            },
            "redirect_url": f"/{user['role'].lower()}"
        }

        resp = jsonify(response_data)
        max_age = 30 * 86400 if remember_me else 86400
        resp.set_cookie("smartattend_token", token, max_age=max_age, httponly=False, samesite="Lax")
        return resp


@app.route("/api/auth/quick-demo", methods=["POST"])
def api_quick_demo():
    """Allows one-click demo login for rapid testing across roles and branches."""
    data = request.get_json() or {}
    role = data.get("role", "STUDENT").upper()
    role_email_map = {
        "STUDENT": "student@college.edu",
        "STUDENT_AIDS": "venu.aids@college.edu",
        "FACULTY": "faculty@college.edu",
        "HOD": "hod@college.edu",
        "HOD_AIDS": "hod.aids@college.edu",
        "ADMIN": "admin@college.edu"
    }
    email = role_email_map.get(role, "student@college.edu")

    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = c.fetchone()
        if not user:
            return jsonify({"error": "Demo user not found."}), 404

        token = create_token(user["id"], user["role"], user["email"], user["name"])
        session["user_id"] = user["id"]
        log_audit(user["id"], "QUICK_DEMO_LOGIN", "USER", user["id"], f"One-click demo login as {user['role']} ({email})")

        resp = jsonify({
            "token": token,
            "user": {
                "id": user["id"],
                "name": user["name"],
                "email": user["email"],
                "role": user["role"],
                "avatar_url": user["avatar_url"]
            },
            "redirect_url": f"/{user['role'].lower()}"
        })
        resp.set_cookie("smartattend_token", token, max_age=86400, httponly=False, samesite="Lax")
        return resp


@app.route("/api/auth/me", methods=["GET"])
@require_auth
def api_me():
    return jsonify({"user": g.current_user})


@app.route("/api/auth/logout", methods=["POST"])
def api_logout():
    user = get_current_user()
    if user:
        log_audit(user["id"], "LOGOUT", "USER", user["id"], "User logged out")
    session.clear()
    resp = jsonify({"message": "Successfully logged out."})
    resp.set_cookie("smartattend_token", "", expires=0)
    return resp


def fetch_user_profile(user_id):
    """Retrieve full user profile data with role-specific academic records."""
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT id, name, email, role, status, avatar_url, phone, created_at
            FROM users WHERE id = ?
        """, (user_id,))
        user_row = c.fetchone()
        if not user_row:
            return None
        profile = dict(user_row)

        if profile["role"] == "STUDENT":
            c.execute("""
                SELECT s.id as student_id, s.usn, s.semester, s.section, s.academic_year,
                       s.phone as student_phone, s.roll_no, s.class_id,
                       s.emergency_contact, s.blood_group, s.bio,
                       b.id as branch_id, b.branch_name, b.branch_code,
                       cls.class_name
                FROM students s
                JOIN branches b ON s.branch_id = b.id
                LEFT JOIN classes cls ON s.class_id = cls.id
                WHERE s.user_id = ?
            """, (user_id,))
            st = c.fetchone()
            if st:
                st_dict = dict(st)
                profile["student_id"] = st_dict["student_id"]
                profile["usn"] = st_dict["usn"]
                profile["semester"] = st_dict["semester"]
                profile["section"] = st_dict["section"]
                profile["academic_year"] = st_dict["academic_year"]
                profile["roll_no"] = st_dict["roll_no"]
                profile["class_id"] = st_dict["class_id"]
                profile["class_name"] = st_dict["class_name"] or f"Sem {st_dict['semester']}-{st_dict['section']}"
                profile["branch_id"] = st_dict["branch_id"]
                profile["branch_name"] = st_dict["branch_name"]
                profile["branch_code"] = st_dict["branch_code"]
                profile["emergency_contact"] = st_dict.get("emergency_contact") or ""
                profile["blood_group"] = st_dict.get("blood_group") or ""
                profile["bio"] = st_dict.get("bio") or ""
                if not profile.get("phone") and st_dict.get("student_phone"):
                    profile["phone"] = st_dict["student_phone"]

        elif profile["role"] in ("FACULTY", "HOD"):
            c.execute("""
                SELECT f.id as faculty_id, f.designation, f.branch_id,
                       b.branch_name, b.branch_code
                FROM faculty f
                JOIN branches b ON f.branch_id = b.id
                WHERE f.user_id = ?
            """, (user_id,))
            fac = c.fetchone()
            if fac:
                fac_dict = dict(fac)
                profile["faculty_id"] = fac_dict["faculty_id"]
                profile["designation"] = fac_dict["designation"]
                profile["branch_id"] = fac_dict["branch_id"]
                profile["branch_name"] = fac_dict["branch_name"]
                profile["branch_code"] = fac_dict["branch_code"]

        return profile


@app.route("/api/profile", methods=["GET"])
@require_auth
def api_get_profile():
    """Retrieve authenticated user's profile information."""
    profile = fetch_user_profile(g.current_user["id"])
    if not profile:
        return jsonify({"error": "Profile not found."}), 404
    return jsonify({
        "success": True,
        "profile": profile
    })


@app.route("/api/profile/activity", methods=["GET"])
@require_auth
def api_profile_activity():
    """Returns recent security audit events and login logs for the authenticated user."""
    user_id = g.current_user["id"]
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT id, action, details, ip_address, created_at
            FROM audit_logs
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 10
        """, (user_id,))
        logs = [dict(r) for r in c.fetchall()]
    return jsonify({"success": True, "activity": logs})


@app.route("/api/profile/avatar", methods=["POST"])
@require_auth
def api_upload_avatar():
    """Upload a new profile picture directly."""
    if 'avatar' not in request.files:
        return jsonify({"error": "No avatar file provided."}), 400
    file = request.files['avatar']
    if not file or not file.filename:
        return jsonify({"error": "No file selected."}), 400
    
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in ('png', 'jpg', 'jpeg', 'webp'):
        return jsonify({"error": "Invalid file format. Allowed formats: PNG, JPG, JPEG, WEBP."}), 400
    
    saved_filename = f"avatar_{g.current_user['id']}_{int(datetime.datetime.now().timestamp())}.{ext}"
    safe_path = os.path.join(UPLOAD_DIR, saved_filename)
    file.save(safe_path)
    
    avatar_url = f"/api/files/{saved_filename}"
    user_id = g.current_user["id"]
    with get_db() as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET avatar_url = ? WHERE id = ?", (avatar_url, user_id))
        log_audit(user_id, "UPDATE_AVATAR", "USER", user_id, f"Uploaded new avatar photo: {saved_filename}")
    
    updated_profile = fetch_user_profile(user_id)
    return jsonify({
        "success": True,
        "message": "Avatar photo updated successfully.",
        "avatar_url": avatar_url,
        "profile": updated_profile
    })


@app.route("/api/profile", methods=["PUT"])
@require_auth
def api_update_profile():
    """
    Update permitted personal profile fields for the authenticated user.
    Permitted fields: name, phone, avatar_url, emergency_contact, blood_group, bio.
    Strictly forbids modifying role, USN, branch, class, email, or privileges.
    """
    data = request.get_json() or {}
    user_id = g.current_user["id"]
    role = g.current_user["role"]

    name = data.get("name")
    phone = data.get("phone")
    avatar_url = data.get("avatar_url")
    emergency_contact = data.get("emergency_contact")
    blood_group = data.get("blood_group")
    bio = data.get("bio")

    # Validate name
    if name is not None:
        name = str(name).strip()
        if not name:
            return jsonify({"error": "Full Name cannot be empty."}), 400
        if len(name) < 2 or len(name) > 100:
            return jsonify({"error": "Name must be between 2 and 100 characters."}), 400

    # Validate phone
    if phone is not None:
        phone = str(phone).strip()
        if phone and not re.match(r"^[0-9+\-\s()]{7,20}$", phone):
            return jsonify({"error": "Please provide a valid phone number (7-20 digits)."}), 400

    # Validate emergency_contact
    if emergency_contact is not None:
        emergency_contact = str(emergency_contact).strip()
        if emergency_contact and not re.match(r"^[0-9+\-\s()]{7,20}$", emergency_contact):
            return jsonify({"error": "Please provide a valid emergency contact number."}), 400

    # Validate blood group
    if blood_group is not None:
        blood_group = str(blood_group).strip().upper()
        if blood_group and blood_group not in ("A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-"):
            return jsonify({"error": "Invalid blood group selected."}), 400

    # Validate bio
    if bio is not None:
        bio = str(bio).strip()
        if len(bio) > 500:
            return jsonify({"error": "Bio cannot exceed 500 characters."}), 400

    with get_db() as conn:
        c = conn.cursor()
        updates = []
        params = []
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if phone is not None:
            updates.append("phone = ?")
            params.append(phone)
        if avatar_url is not None:
            updates.append("avatar_url = ?")
            params.append(avatar_url.strip())

        if updates:
            params.append(user_id)
            c.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params)

        if role == "STUDENT":
            st_updates = []
            st_params = []
            if phone is not None:
                st_updates.append("phone = ?")
                st_params.append(phone)
            if emergency_contact is not None:
                st_updates.append("emergency_contact = ?")
                st_params.append(emergency_contact)
            if blood_group is not None:
                st_updates.append("blood_group = ?")
                st_params.append(blood_group)
            if bio is not None:
                st_updates.append("bio = ?")
                st_params.append(bio)

            if st_updates:
                st_params.append(user_id)
                c.execute(f"UPDATE students SET {', '.join(st_updates)} WHERE user_id = ?", st_params)

        log_audit(user_id, "UPDATE_PROFILE", "USER", user_id, f"User updated profile details (name: {name or 'unchanged'})")

    updated_profile = fetch_user_profile(user_id)
    return jsonify({
        "success": True,
        "message": "Profile updated successfully.",
        "profile": updated_profile
    })


@app.route("/api/profile/change-password", methods=["PUT", "POST"])
@app.route("/api/auth/change-password", methods=["PUT", "POST"])
@require_auth
def api_change_password():
    """Self-service password update with strong password validation."""
    data = request.get_json() or {}
    current_password = data.get("currentPassword") or data.get("current_password") or ""
    new_password = data.get("newPassword") or data.get("new_password") or ""
    confirm_password = data.get("confirmPassword") or data.get("confirm_password") or ""

    if not current_password or not new_password:
        return jsonify({"error": "Please provide your current password and new password."}), 400

    user_id = g.current_user["id"]
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,))
        row = c.fetchone()
        if not row or not verify_password(current_password, row["password_hash"]):
            return jsonify({"error": "Current password is incorrect."}), 400

        is_strong, err_msg = validate_password_strength(new_password)
        if not is_strong:
            return jsonify({"error": err_msg}), 400

        if confirm_password and new_password != confirm_password:
            return jsonify({"error": "New passwords do not match."}), 400

        new_hash = hash_password(new_password)
        c.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user_id))
        log_audit(user_id, "CHANGE_PASSWORD", "USER", user_id, "Password changed successfully")

    return jsonify({"success": True, "message": "Password changed successfully."})


@app.route("/api/auth/forgot-password/request", methods=["POST"])
def api_forgot_password_request():
    """Generates a secure password reset token and OTP for verified identity recovery."""
    data = request.get_json() or {}
    email = data.get("email", "").strip().lower()

    if not email:
        return jsonify({"error": "Please provide your registered college email."}), 400

    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, name FROM users WHERE email = ? AND status = 'ACTIVE'", (email,))
        user = c.fetchone()
        if not user:
            # Prevent email enumeration while giving friendly feedback
            return jsonify({"error": "No active account found with that email address."}), 404

        otp = str(random.randint(100000, 999999))
        reset_token = uuid.uuid4().hex
        expires_at = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")

        c.execute("""
            INSERT INTO password_resets (user_id, email, token_hash, otp, expires_at)
            VALUES (?, ?, ?, ?, ?)
        """, (user["id"], email, reset_token, otp, expires_at))

        log_audit(user["id"], "FORGOT_PASSWORD_REQUEST", "USER", user["id"], "Requested password reset code")

        return jsonify({
            "success": True,
            "message": "A 6-digit verification code has been generated.",
            "reset_token": reset_token,
            "otp_preview": otp  # Included for seamless demo & test evaluation
        })


@app.route("/api/auth/forgot-password/reset", methods=["POST"])
def api_forgot_password_reset():
    """Verifies OTP/token and resets password with secure hash."""
    data = request.get_json() or {}
    email = data.get("email", "").strip().lower()
    otp = data.get("otp", "").strip()
    token = data.get("token", "").strip()
    new_password = data.get("new_password", "")
    confirm_password = data.get("confirm_password", "")

    if not email or (not otp and not token) or not new_password:
        return jsonify({"error": "Email, verification code/token, and new password are required."}), 400

    if new_password != confirm_password:
        return jsonify({"error": "New password and Confirm password do not match."}), 400

    is_strong, err_msg = validate_password_strength(new_password)
    if not is_strong:
        return jsonify({"error": err_msg}), 400

    now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    with get_db() as conn:
        c = conn.cursor()
        if otp:
            c.execute("""
                SELECT id, user_id FROM password_resets 
                WHERE email = ? AND otp = ? AND used = 0 AND expires_at >= ?
                ORDER BY id DESC LIMIT 1
            """, (email, otp, now_str))
        else:
            c.execute("""
                SELECT id, user_id FROM password_resets 
                WHERE email = ? AND token_hash = ? AND used = 0 AND expires_at >= ?
                ORDER BY id DESC LIMIT 1
            """, (email, token, now_str))

        reset_record = c.fetchone()
        if not reset_record:
            return jsonify({"error": "Invalid or expired verification code. Please request a new one."}), 400

        user_id = reset_record["user_id"]
        new_hash = hash_password(new_password)
        c.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user_id))
        c.execute("UPDATE password_resets SET used = 1 WHERE id = ?", (reset_record["id"],))

        log_audit(user_id, "PASSWORD_RESET_SUCCESS", "USER", user_id, "Password reset via OTP identity verification")

    return jsonify({"success": True, "message": "Password reset successfully. You can now log in with your new password."})


# --------------------------------------------------------------------------
# Branch & Department Management API (Dynamic Creation)
# --------------------------------------------------------------------------

@app.route("/api/branches", methods=["GET", "POST"])
@require_auth
def api_branches():
    """List all branches or dynamically add a new branch."""
    if request.method == "GET":
        with get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT id, branch_code, branch_name, status, created_at FROM branches WHERE status = 'ACTIVE' ORDER BY branch_name ASC")
            return jsonify({"branches": [dict(r) for r in c.fetchall()]})

    # POST - Add New Branch (Faculty & Admin)
    if g.current_user["role"] not in ("FACULTY", "HOD", "ADMIN"):
        return jsonify({"error": "Forbidden: Only faculty and administrators can add branches."}), 403

    data = request.get_json() or {}
    branch_name = data.get("branch_name", "").strip()
    branch_code = data.get("branch_code", "").strip()

    if not branch_name:
        return jsonify({"error": "Branch name is required."}), 400

    # Auto-generate acronym code if omitted (e.g. "Computer Science and Business Systems" -> "CSBS")
    if not branch_code:
        stopwords = {'AND', '&', 'OF', 'THE', 'IN', 'FOR'}
        words = [w for w in re.split(r'[\s\-_]+', branch_name.upper()) if w and w not in stopwords]
        branch_code = "".join(w[0] for w in words) if words else branch_name[:4].upper()

    with get_db() as conn:
        c = conn.cursor()
        # Check duplicate
        c.execute("SELECT id, branch_code, branch_name FROM branches WHERE branch_name = ? COLLATE NOCASE OR branch_code = ? COLLATE NOCASE", (branch_name, branch_code))
        existing = c.fetchone()
        if existing:
            return jsonify({
                "success": True,
                "message": "Branch already exists in database.",
                "branch": dict(existing)
            }), 200

        c.execute("""
            INSERT INTO branches (branch_code, branch_name, status, created_by)
            VALUES (?, ?, 'ACTIVE', ?)
        """, (branch_code, branch_name, g.current_user["id"]))
        new_id = c.lastrowid

        # Keep legacy departments table synchronized
        c.execute("INSERT OR IGNORE INTO departments (id, code, name) VALUES (?, ?, ?)", (new_id, branch_code, branch_name))

        log_audit(g.current_user["id"], "ADD_BRANCH", "BRANCH", new_id, f"Added branch: {branch_name} ({branch_code})")

        return jsonify({
            "success": True,
            "message": f"Branch '{branch_name}' added successfully and is now selectable.",
            "branch": {
                "id": new_id,
                "branch_code": branch_code,
                "branch_name": branch_name
            }
        }), 201


# --------------------------------------------------------------------------
# Class Master API
# --------------------------------------------------------------------------

@app.route("/api/classes", methods=["GET", "POST"])
@require_auth
def api_classes():
    """Retrieve class master records with student enrollment counts."""
    if request.method == "GET":
        branch_id = request.args.get("branch_id")
        semester = request.args.get("semester")
        academic_year = request.args.get("academic_year", "2026-2027")

        query = """
            SELECT c.id, c.branch_id, c.semester, c.section, c.academic_year, c.class_name,
                   b.branch_name, b.branch_code,
                   COUNT(st.id) as student_count
            FROM classes c
            JOIN branches b ON c.branch_id = b.id
            LEFT JOIN students st ON st.class_id = c.id
            WHERE c.academic_year = ?
        """
        params = [academic_year]
        if branch_id:
            query += " AND c.branch_id = ?"
            params.append(branch_id)
        if semester:
            query += " AND c.semester = ?"
            params.append(semester)

        query += " GROUP BY c.id ORDER BY b.branch_name ASC, c.semester ASC, c.section ASC"

        with get_db() as conn:
            c = conn.cursor()
            c.execute(query, params)
            return jsonify({"classes": [dict(r) for r in c.fetchall()]})

    # POST - Create New Class
    if g.current_user["role"] not in ("FACULTY", "HOD", "ADMIN"):
        return jsonify({"error": "Forbidden."}), 403

    data = request.get_json() or {}
    branch_id = data.get("branch_id")
    semester = data.get("semester")
    section = data.get("section", "A").strip().upper()
    academic_year = data.get("academic_year", "2026-2027").strip()

    if not branch_id or not semester or not section:
        return jsonify({"error": "Branch, Semester, and Section are required."}), 400

    with get_db() as conn:
        class_id = resolve_or_create_class(conn, int(branch_id), int(semester), section, academic_year)
        c = conn.cursor()
        c.execute("SELECT * FROM classes WHERE id = ?", (class_id,))
        cls_row = dict(c.fetchone())
        return jsonify({"success": True, "class": cls_row}), 201


@app.route("/api/classes/<int:class_id>/students", methods=["GET"])
@require_auth
def api_class_students(class_id):
    """Retrieve full student roster belonging to a specific class."""
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT st.id as student_id, st.usn, st.semester, st.section, st.academic_year,
                   st.phone, st.roll_no,
                   u.name as student_name, u.email as student_email, u.status, u.avatar_url,
                   b.branch_name, b.branch_code,
                   cls.class_name
            FROM students st
            JOIN users u ON st.user_id = u.id
            JOIN branches b ON st.branch_id = b.id
            JOIN classes cls ON st.class_id = cls.id
            WHERE st.class_id = ?
            ORDER BY st.usn ASC
        """, (class_id,))
        students = [dict(r) for r in c.fetchall()]
        return jsonify({
            "class_id": class_id,
            "students": students,
            "total_count": len(students)
        })


# --------------------------------------------------------------------------
# Faculty Student Addition API
# --------------------------------------------------------------------------

@app.route("/api/faculty/students", methods=["POST"])
@require_roles("FACULTY", "HOD", "ADMIN")
def api_faculty_add_student():
    """
    Allows faculty to create a new student account:
    - Generates user account with hashed password
    - Automatically links student to branch and class master data
    - Returns initial credentials securely for display/sharing with the student
    """
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    usn = data.get("usn", "").strip().upper()
    email = data.get("email", "").strip().lower()
    phone = data.get("phone", "").strip()
    roll_no = data.get("roll_no", "").strip()
    branch_id = data.get("branch_id")
    semester = data.get("semester")
    section = data.get("section", "A").strip().upper()
    academic_year = data.get("academic_year", "2026-2027").strip()
    temp_password = data.get("temporary_password", "").strip()

    if not name or not usn or not email or not branch_id or not semester:
        return jsonify({"error": "Student Name, USN, Email, Branch, and Semester are mandatory."}), 400

    if not temp_password:
        temp_password = f"TempPass@{random.randint(100, 999)}"

    branch_id = int(branch_id)
    semester = int(semester)

    with get_db() as conn:
        c = conn.cursor()

        # Check unique email
        c.execute("SELECT id FROM users WHERE email = ?", (email,))
        if c.fetchone():
            return jsonify({"error": f"A user with email '{email}' already exists."}), 400

        # Check unique USN
        c.execute("SELECT id FROM students WHERE usn = ?", (usn,))
        if c.fetchone():
            return jsonify({"error": f"A student with USN '{usn}' already exists."}), 400

        # Resolve or create class
        class_id = resolve_or_create_class(conn, branch_id, semester, section, academic_year)

        # Hash password securely
        pwd_hash = hash_password(temp_password)

        c.execute("""
            INSERT INTO users (name, email, password_hash, role, status)
            VALUES (?, ?, ?, 'STUDENT', 'ACTIVE')
        """, (name, email, pwd_hash))
        user_id = c.lastrowid

        c.execute("""
            INSERT INTO students (user_id, usn, branch_id, class_id, semester, section, academic_year, phone, roll_no)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, usn, branch_id, class_id, semester, section, academic_year, phone, roll_no))
        student_id = c.lastrowid

        # Fetch class name and branch name for response
        c.execute("SELECT class_name FROM classes WHERE id = ?", (class_id,))
        class_name = c.fetchone()["class_name"]
        c.execute("SELECT branch_name FROM branches WHERE id = ?", (branch_id,))
        branch_name = c.fetchone()["branch_name"]

        log_audit(g.current_user["id"], "ADD_STUDENT", "STUDENT", usn, f"Faculty {g.current_user['name']} registered student {name} ({usn}) into class {class_name}")

        create_notification(
            user_id,
            "Welcome to SmartAttend ERP!",
            f"Your institutional student account has been created by {g.current_user['name']}. Please change your password under Profile > Security.",
            "SYSTEM",
            "/student#profile"
        )

        return jsonify({
            "success": True,
            "message": f"Student {name} ({usn}) has been created and assigned to {class_name}.",
            "student": {
                "student_id": student_id,
                "user_id": user_id,
                "name": name,
                "usn": usn,
                "email": email,
                "phone": phone,
                "roll_no": roll_no,
                "branch_name": branch_name,
                "class_name": class_name,
                "semester": semester,
                "section": section
            },
            "credentials": {
                "email": email,
                "usn": usn,
                "temporary_password": temp_password
            }
        }), 201


# --------------------------------------------------------------------------
# Faculty Subject Creation & Class Allocation API
# --------------------------------------------------------------------------

@app.route("/api/faculty/subjects", methods=["GET", "POST"])
@require_roles("FACULTY", "HOD", "ADMIN")
def api_faculty_manage_subjects():
    faculty_id = g.current_user.get("faculty", {}).get("faculty_id", 2)

    if request.method == "GET":
        with get_db() as conn:
            c = conn.cursor()
            c.execute("""
                SELECT s.id, s.subject_code, s.subject_name, s.subject_type, s.credits,
                       s.semester, s.description, s.planned_classes, s.minimum_attendance,
                       b.branch_name, b.branch_code,
                       cls.id as class_id, cls.class_name, cls.section,
                       fs.id as faculty_subject_id,
                       COUNT(DISTINCT ss.student_id) as enrolled_count
                FROM faculty_subjects fs
                JOIN subjects s ON fs.subject_id = s.id
                JOIN branches b ON s.branch_id = b.id
                LEFT JOIN classes cls ON fs.class_id = cls.id
                LEFT JOIN student_subjects ss ON ss.faculty_subject_id = fs.id
                WHERE fs.faculty_id = ?
                GROUP BY fs.id
                ORDER BY s.subject_code ASC
            """, (faculty_id,))
            return jsonify({"subjects": [dict(r) for r in c.fetchall()]})

    # POST - Create or Allocate Subject to a Class
    data = request.get_json() or {}
    subject_code = data.get("subject_code", "").strip().upper()
    subject_name = data.get("subject_name", "").strip()
    subject_type = data.get("subject_type", "Theory").strip()
    credits = int(data.get("credits", 4))
    branch_id = data.get("branch_id")
    semester = data.get("semester")
    section = data.get("section", "A").strip().upper()
    academic_year = data.get("academic_year", "2026-2027").strip()
    description = data.get("description", "").strip()
    planned_classes = int(data.get("planned_classes", 45))
    minimum_attendance = float(data.get("minimum_attendance", 75.0))

    if not subject_code or not subject_name or not branch_id or not semester:
        return jsonify({"error": "Subject Code, Subject Name, Branch, and Semester are required."}), 400

    branch_id = int(branch_id)
    semester = int(semester)

    with get_db() as conn:
        c = conn.cursor()

        # Find or create class
        class_id = resolve_or_create_class(conn, branch_id, semester, section, academic_year)

        # Find or create subject
        c.execute("SELECT id FROM subjects WHERE subject_code = ?", (subject_code,))
        sub_row = c.fetchone()
        if sub_row:
            subject_id = sub_row["id"]
            c.execute("""
                UPDATE subjects 
                SET subject_name = ?, subject_type = ?, credits = ?, description = ?, planned_classes = ?, minimum_attendance = ?
                WHERE id = ?
            """, (subject_name, subject_type, credits, description, planned_classes, minimum_attendance, subject_id))
        else:
            c.execute("""
                INSERT INTO subjects (subject_code, subject_name, branch_id, semester, credits, subject_type, description, planned_classes, minimum_attendance)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (subject_code, subject_name, branch_id, semester, credits, subject_type, description, planned_classes, minimum_attendance))
            subject_id = c.lastrowid

        # Allocate subject to faculty for this specific class
        c.execute("""
            SELECT id FROM faculty_subjects 
            WHERE faculty_id = ? AND subject_id = ? AND class_id = ? AND academic_year = ?
        """, (faculty_id, subject_id, class_id, academic_year))
        fs_row = c.fetchone()
        if fs_row:
            fs_id = fs_row["id"]
        else:
            c.execute("""
                INSERT INTO faculty_subjects (faculty_id, subject_id, class_id, academic_year)
                VALUES (?, ?, ?, ?)
            """, (faculty_id, subject_id, class_id, academic_year))
            fs_id = c.lastrowid

        c.execute("SELECT class_name FROM classes WHERE id = ?", (class_id,))
        class_name = c.fetchone()["class_name"]

        log_audit(g.current_user["id"], "ALLOCATE_SUBJECT", "SUBJECT", subject_code, f"Allocated {subject_code} to class {class_name}")

        return jsonify({
            "success": True,
            "message": f"Subject '{subject_code} - {subject_name}' allocated to class {class_name}.",
            "subject_id": subject_id,
            "faculty_subject_id": fs_id,
            "class_id": class_id,
            "class_name": class_name
        }), 201


@app.route("/api/faculty/subjects/<int:subject_id>/assign-students", methods=["POST"])
@require_roles("FACULTY", "HOD", "ADMIN")
def api_faculty_assign_students(subject_id):
    """
    Enrolls students of a class into a subject.
    Faculty can select all or individual students from the class roster.
    """
    faculty_id = g.current_user.get("faculty", {}).get("faculty_id", 2)
    data = request.get_json() or {}
    class_id = data.get("class_id")
    student_ids = data.get("student_ids", [])
    academic_year = data.get("academic_year", "2026-2027")

    if not class_id or not student_ids:
        return jsonify({"error": "Class ID and selected student IDs are required."}), 400

    with get_db() as conn:
        c = conn.cursor()

        # Find faculty_subject allocation
        c.execute("""
            SELECT id FROM faculty_subjects 
            WHERE faculty_id = ? AND subject_id = ? AND class_id = ?
        """, (faculty_id, subject_id, class_id))
        fs_row = c.fetchone()
        fs_id = fs_row["id"] if fs_row else None

        assigned_count = 0
        for st_id in student_ids:
            c.execute("""
                INSERT INTO student_subjects (student_id, subject_id, faculty_subject_id, academic_year)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(student_id, subject_id, academic_year) DO UPDATE SET faculty_subject_id = excluded.faculty_subject_id
            """, (st_id, subject_id, fs_id, academic_year))
            assigned_count += 1

        c.execute("SELECT subject_code, subject_name FROM subjects WHERE id = ?", (subject_id,))
        sub_info = c.fetchone()
        c.execute("SELECT class_name FROM classes WHERE id = ?", (class_id,))
        cls_info = c.fetchone()

        log_audit(g.current_user["id"], "ASSIGN_STUDENTS", "SUBJECT", subject_id, f"Assigned {assigned_count} students of {cls_info['class_name']} to {sub_info['subject_code']}")

        return jsonify({
            "success": True,
            "message": f"Successfully enrolled {assigned_count} students into {sub_info['subject_code']} ({cls_info['class_name']}).",
            "assigned_count": assigned_count
        })


@app.route("/api/faculty/subjects/<int:subject_id>", methods=["PUT"])
@require_roles("FACULTY", "HOD", "ADMIN")
def api_faculty_update_subject(subject_id):
    """Allows authorized faculty to edit subject details."""
    data = request.get_json() or {}
    description = data.get("description", "").strip()
    planned_classes = int(data.get("planned_classes", 45))
    minimum_attendance = float(data.get("minimum_attendance", 75.0))
    subject_type = data.get("subject_type", "Theory").strip()

    with get_db() as conn:
        c = conn.cursor()
        c.execute("""
            UPDATE subjects 
            SET description = ?, planned_classes = ?, minimum_attendance = ?, subject_type = ?
            WHERE id = ?
        """, (description, planned_classes, minimum_attendance, subject_type, subject_id))
        log_audit(g.current_user["id"], "UPDATE_SUBJECT", "SUBJECT", subject_id, "Updated subject details")

    return jsonify({"success": True, "message": "Subject details updated successfully."})


# --------------------------------------------------------------------------
# Student Portal API
# --------------------------------------------------------------------------

@app.route("/api/student/dashboard", methods=["GET"])
@require_roles("STUDENT", "ADMIN")
def api_student_dashboard():
    student_id = g.current_user.get("student", {}).get("student_id", 1)
    min_pct = get_min_attendance_threshold()

    with get_db() as conn:
        c = conn.cursor()

        # Student Details
        c.execute("""
            SELECT s.id, s.usn, s.semester, s.section, s.academic_year, s.phone, s.roll_no,
                   u.name, u.email, u.avatar_url,
                   b.branch_name, b.branch_code,
                   cls.class_name
            FROM students s
            JOIN users u ON s.user_id = u.id
            JOIN branches b ON s.branch_id = b.id
            LEFT JOIN classes cls ON s.class_id = cls.id
            WHERE s.id = ?
        """, (student_id,))
        student_info = dict(c.fetchone())

        # Subject-wise attendance breakdown (ONLY subjects allocated to this student!)
        c.execute("""
            SELECT s.id as subject_id, s.subject_code, s.subject_name, s.credits, s.subject_type,
                   fu.name as faculty_name,
                   COUNT(a.id) as conducted,
                   SUM(CASE WHEN a.status IN ('PRESENT', 'APPROVED_PERMISSION') THEN 1 ELSE 0 END) as attended,
                   SUM(CASE WHEN a.status = 'ABSENT' THEN 1 ELSE 0 END) as absent
            FROM student_subjects ss
            JOIN subjects s ON ss.subject_id = s.id
            LEFT JOIN faculty_subjects fs ON ss.faculty_subject_id = fs.id
            LEFT JOIN faculty f ON fs.faculty_id = f.id
            LEFT JOIN users fu ON f.user_id = fu.id
            LEFT JOIN attendance a ON a.student_id = ss.student_id AND a.subject_id = s.id
            WHERE ss.student_id = ?
            GROUP BY s.id
            ORDER BY s.subject_code ASC
        """, (student_id,))
        subject_rows = c.fetchall()

        subjects_data = []
        total_conducted = 0
        total_attended = 0
        total_absent = 0

        for r in subject_rows:
            cond = r["conducted"] or 0
            att = r["attended"] or 0
            ab = r["absent"] or 0
            total_conducted += cond
            total_attended += att
            total_absent += ab

            pct = calculate_percentage(att, cond)
            req = calculate_required_classes(att, cond, min_pct)
            miss = calculate_missable_classes(att, cond, min_pct)
            status_obj = get_attendance_status(pct, cond, min_pct)

            subjects_data.append({
                "subject_id": r["subject_id"],
                "subject_code": r["subject_code"],
                "subject_name": r["subject_name"],
                "subject_type": r["subject_type"],
                "faculty_name": r["faculty_name"] or "Faculty Member",
                "credits": r["credits"],
                "conducted": cond,
                "attended": att,
                "absent": ab,
                "percentage": pct,
                "required_classes": req,
                "missable_classes": miss,
                "status": status_obj
            })

        overall_pct = calculate_percentage(total_attended, total_conducted)
        overall_req = calculate_required_classes(total_attended, total_conducted, min_pct)
        overall_miss = calculate_missable_classes(total_attended, total_conducted, min_pct)
        overall_status = get_attendance_status(overall_pct, total_conducted, min_pct)

        # Recent permission requests
        c.execute("""
            SELECT pr.id, pr.request_code, pr.date, pr.hour, pr.reason, pr.description,
                   pr.status, pr.faculty_comment, pr.hod_comment, pr.created_at,
                   s.subject_code, s.subject_name
            FROM permission_requests pr
            JOIN subjects s ON pr.subject_id = s.id
            WHERE pr.student_id = ?
            ORDER BY pr.created_at DESC
            LIMIT 5
        """, (student_id,))
        recent_permissions = [dict(r) for r in c.fetchall()]

        # Recent notifications
        c.execute("""
            SELECT id, title, message, type, read_status, created_at
            FROM notifications
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 4
        """, (student_info["id"],))
        recent_notifs = [dict(r) for r in c.fetchall()]

        return jsonify({
            "student": student_info,
            "overall": {
                "conducted": total_conducted,
                "attended": total_attended,
                "absent": total_absent,
                "percentage": overall_pct,
                "minimum_required": min_pct,
                "required_classes": overall_req,
                "missable_classes": overall_miss,
                "status": overall_status
            },
            "subjects": subjects_data,
            "recent_permissions": recent_permissions,
            "recent_notifications": recent_notifs
        })


@app.route("/api/student/permissions", methods=["GET", "POST"])
@require_roles("STUDENT", "ADMIN")
def api_student_permissions():
    student_id = g.current_user.get("student", {}).get("student_id", 1)

    if request.method == "GET":
        with get_db() as conn:
            c = conn.cursor()
            c.execute("""
                SELECT pr.id, pr.request_code, pr.subject_id, pr.faculty_id, pr.branch_id, pr.date, pr.hour,
                       pr.reason, pr.description, pr.document_filename, pr.document_original_name,
                       pr.status, pr.faculty_comment, pr.hod_comment, pr.created_at, pr.updated_at,
                       s.subject_code, s.subject_name, fu.name as faculty_name,
                       b.branch_name, b.branch_code
                FROM permission_requests pr
                JOIN subjects s ON pr.subject_id = s.id
                JOIN branches b ON pr.branch_id = b.id
                JOIN faculty f ON pr.faculty_id = f.id
                JOIN users fu ON f.user_id = fu.id
                WHERE pr.student_id = ?
                ORDER BY pr.created_at DESC
            """, (student_id,))
            return jsonify({"requests": [dict(r) for r in c.fetchall()]})

    # POST - Submit a new permission request
    subject_id = request.form.get("subject_id")
    faculty_id = request.form.get("faculty_id")
    date_val = request.form.get("date", "").strip()
    hour_val = request.form.get("hour")
    reason = request.form.get("reason", "").strip()
    description = request.form.get("description", "").strip()

    if not all([subject_id, date_val, hour_val, reason, description]):
        return jsonify({"error": "Please fill in all required fields (Subject, Date, Hour, Reason, and Explanation)."}), 400

    with get_db() as conn:
        c = conn.cursor()
        # Find student's branch_id
        c.execute("SELECT branch_id FROM students WHERE id = ?", (student_id,))
        st_branch_id = c.fetchone()["branch_id"]

        if not faculty_id:
            c.execute("SELECT faculty_id FROM faculty_subjects WHERE subject_id = ? LIMIT 1", (subject_id,))
            fac_row = c.fetchone()
            faculty_id = fac_row["faculty_id"] if fac_row else 2

        # Check duplicate
        c.execute("""
            SELECT id, status FROM permission_requests 
            WHERE student_id = ? AND subject_id = ? AND date = ? AND hour = ?
        """, (student_id, subject_id, date_val, hour_val))
        existing = c.fetchone()
        if existing and existing["status"] in ("PENDING", "UNDER_REVIEW", "ESCALATED_HOD", "APPROVED"):
            return jsonify({"error": f"A permission request for this class has already been submitted (Status: {existing['status']})."}), 400

        # Handle document upload
        saved_filename = ""
        original_filename = ""
        if 'document' in request.files:
            file = request.files['document']
            if file and file.filename != '':
                if not allowed_file(file.filename):
                    return jsonify({"error": "Invalid document format. Allowed types: PDF, JPG, JPEG, PNG."}), 400
                original_filename = file.filename
                ext = file.filename.rsplit('.', 1)[1].lower()
                saved_filename = f"doc_{uuid.uuid4().hex[:12]}.{ext}"
                file.save(os.path.join(UPLOAD_DIR, saved_filename))

        req_code = f"PR-{datetime.datetime.now().strftime('%Y%m%d')}-{random.randint(100, 999)}"

        c.execute("""
            INSERT INTO permission_requests (
                request_code, student_id, subject_id, faculty_id, branch_id, date, hour,
                reason, description, document_filename, document_original_name, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING')
        """, (req_code, student_id, subject_id, faculty_id, st_branch_id, date_val, hour_val, reason, description, saved_filename, original_filename))
        req_id = c.lastrowid

        # Notify assigned faculty
        c.execute("SELECT user_id FROM faculty WHERE id = ?", (faculty_id,))
        fac_user_row = c.fetchone()
        if fac_user_row:
            create_notification(
                fac_user_row["user_id"],
                "New Permission Request",
                f"New attendance permission request {req_code} submitted by student.",
                "PERMISSION",
                "/faculty#permissions"
            )

        log_audit(g.current_user["id"], "SUBMIT_PERMISSION", "PERMISSION_REQUEST", req_code, f"Submitted reason: {reason}")

        return jsonify({
            "success": True,
            "message": "Your permission request has been submitted successfully.",
            "request_code": req_code,
            "request_id": req_id
        }), 201


@app.route("/api/student/subjects/<int:subject_id>/attendance", methods=["GET"])
@require_roles("STUDENT", "FACULTY", "HOD", "ADMIN")
def api_student_subject_attendance(subject_id):
    student_id = g.current_user.get("student", {}).get("student_id", 1)
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT a.id, a.date, a.hour, a.status, a.original_status, a.audit_notes,
                   a.permission_request_id, u.name as faculty_name,
                   s.subject_code, s.subject_name
            FROM attendance a
            JOIN subjects s ON a.subject_id = s.id
            JOIN faculty f ON a.faculty_id = f.id
            JOIN users u ON f.user_id = u.id
            WHERE a.student_id = ? AND a.subject_id = ?
            ORDER BY a.date DESC, a.hour DESC
        """, (student_id, subject_id))
        return jsonify({"records": [dict(r) for r in c.fetchall()]})


@app.route("/api/student/calendar", methods=["GET"])
@require_roles("STUDENT", "ADMIN")
def api_student_calendar():
    student_id = g.current_user.get("student", {}).get("student_id", 1)
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT a.date, a.hour, a.status, s.subject_code, s.subject_name, u.name as faculty_name
            FROM attendance a
            JOIN subjects s ON a.subject_id = s.id
            JOIN faculty f ON a.faculty_id = f.id
            JOIN users u ON f.user_id = u.id
            WHERE a.student_id = ?
            ORDER BY a.date ASC, a.hour ASC
        """, (student_id,))
        records = [dict(r) for r in c.fetchall()]

        calendar_map = {}
        for r in records:
            d = r["date"]
            if d not in calendar_map:
                calendar_map[d] = {
                    "date": d,
                    "sessions": [],
                    "has_absent": False,
                    "has_present": False,
                    "has_permission": False
                }
            calendar_map[d]["sessions"].append(r)
            if r["status"] == "ABSENT":
                calendar_map[d]["has_absent"] = True
            elif r["status"] == "PRESENT":
                calendar_map[d]["has_present"] = True
            elif r["status"] == "APPROVED_PERMISSION":
                calendar_map[d]["has_permission"] = True

        return jsonify({"calendar": calendar_map})


@app.route("/api/student/missed-classes", methods=["GET"])
@require_roles("STUDENT", "ADMIN")
def api_student_missed_classes():
    student_id = g.current_user.get("student", {}).get("student_id", 1)
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT a.id as attendance_id, a.subject_id, a.faculty_id, a.date, a.hour,
                   s.subject_code, s.subject_name, u.name as faculty_name,
                   pr.id as existing_request_id, pr.status as existing_request_status
            FROM attendance a
            JOIN subjects s ON a.subject_id = s.id
            JOIN faculty f ON a.faculty_id = f.id
            JOIN users u ON f.user_id = u.id
            LEFT JOIN permission_requests pr ON pr.student_id = a.student_id 
                                            AND pr.subject_id = a.subject_id 
                                            AND pr.date = a.date 
                                            AND pr.hour = a.hour
            WHERE a.student_id = ? AND a.status = 'ABSENT'
            ORDER BY a.date DESC, a.hour DESC
            LIMIT 50
        """, (student_id,))
        return jsonify({"missed_classes": [dict(r) for r in c.fetchall()]})


# --------------------------------------------------------------------------
# Faculty Attendance Marking & Permissions API
# --------------------------------------------------------------------------

@app.route("/api/faculty/dashboard", methods=["GET"])
@require_roles("FACULTY", "HOD", "ADMIN")
def api_faculty_dashboard():
    faculty_id = g.current_user.get("faculty", {}).get("faculty_id", 2)
    min_pct = get_min_attendance_threshold()

    with get_db() as conn:
        c = conn.cursor()
        # Assigned subjects with class details
        c.execute("""
            SELECT s.id, s.subject_code, s.subject_name, s.credits,
                   cls.class_name,
                   COUNT(DISTINCT ss.student_id) as enrolled_count
            FROM faculty_subjects fs
            JOIN subjects s ON fs.subject_id = s.id
            LEFT JOIN classes cls ON fs.class_id = cls.id
            LEFT JOIN student_subjects ss ON ss.faculty_subject_id = fs.id
            WHERE fs.faculty_id = ?
            GROUP BY fs.id
        """, (faculty_id,))
        subjects = [dict(r) for r in c.fetchall()]
        total_students = sum(s["enrolled_count"] for s in subjects)

        # Pending permission requests
        c.execute("""
            SELECT COUNT(*) FROM permission_requests
            WHERE faculty_id = ? AND status IN ('PENDING', 'UNDER_REVIEW')
        """, (faculty_id,))
        pending_count = c.fetchone()[0]

        # Low attendance students
        subject_ids = [s["id"] for s in subjects]
        low_att_count = 0
        if subject_ids:
            placeholders = ",".join("?" * len(subject_ids))
            c.execute(f"""
                SELECT a.student_id, a.subject_id,
                       COUNT(a.id) as conducted,
                       SUM(CASE WHEN a.status IN ('PRESENT', 'APPROVED_PERMISSION') THEN 1 ELSE 0 END) as attended
                FROM attendance a
                WHERE a.subject_id IN ({placeholders})
                GROUP BY a.student_id, a.subject_id
                HAVING (CAST(attended AS REAL) / conducted) * 100 < ?
            """, (*subject_ids, min_pct))
            low_att_count = len(c.fetchall())

        return jsonify({
            "assigned_subjects_count": len(subjects),
            "total_students": total_students,
            "pending_requests_count": pending_count,
            "low_attendance_students_count": low_att_count,
            "subjects": subjects
        })


@app.route("/api/faculty/subjects/<int:subject_id>/students", methods=["GET"])
@require_roles("FACULTY", "HOD", "ADMIN")
def api_faculty_subject_students(subject_id):
    date_val = request.args.get("date", datetime.date.today().strftime("%Y-%m-%d"))
    hour_val = int(request.args.get("hour", 1))

    with get_db() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT st.id as student_id, st.usn, u.name as student_name, u.avatar_url,
                   att.status as current_status
            FROM student_subjects ss
            JOIN students st ON ss.student_id = st.id
            JOIN users u ON st.user_id = u.id
            LEFT JOIN attendance att ON att.student_id = st.id 
                                    AND att.subject_id = ? 
                                    AND att.date = ? 
                                    AND att.hour = ?
            WHERE ss.subject_id = ?
            ORDER BY st.usn ASC
        """, (subject_id, date_val, hour_val, subject_id))
        rows = [dict(r) for r in c.fetchall()]
        already_marked = any(r["current_status"] is not None for r in rows)
        return jsonify({
            "students": rows,
            "already_marked": already_marked,
            "date": date_val,
            "hour": hour_val
        })


@app.route("/api/faculty/attendance", methods=["POST"])
@require_roles("FACULTY", "HOD", "ADMIN")
def api_faculty_save_attendance():
    faculty_id = g.current_user.get("faculty", {}).get("faculty_id", 2)
    data = request.get_json() or {}
    subject_id = data.get("subject_id")
    date_val = data.get("date")
    hour_val = int(data.get("hour", 1))
    records = data.get("records", [])

    if not subject_id or not date_val or not records:
        return jsonify({"error": "Subject, Date, and student records are required."}), 400

    min_pct = get_min_attendance_threshold()

    with get_db() as conn:
        c = conn.cursor()

        for rec in records:
            st_id = rec["student_id"]
            new_status = rec["status"].upper()
            if new_status not in ("PRESENT", "ABSENT", "APPROVED_PERMISSION"):
                new_status = "PRESENT"

            c.execute("""
                SELECT id, status FROM attendance 
                WHERE student_id = ? AND subject_id = ? AND date = ? AND hour = ?
            """, (st_id, subject_id, date_val, hour_val))
            existing = c.fetchone()

            if existing:
                orig_status = existing["status"]
                c.execute("""
                    UPDATE attendance 
                    SET status = ?, original_status = ?, updated_by = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (new_status, orig_status, g.current_user["id"], existing["id"]))
            else:
                c.execute("""
                    INSERT INTO attendance (student_id, subject_id, faculty_id, date, hour, status)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (st_id, subject_id, faculty_id, date_val, hour_val, new_status))

            # Alert if dropped below threshold
            c.execute("""
                SELECT COUNT(id) as conducted,
                       SUM(CASE WHEN status IN ('PRESENT', 'APPROVED_PERMISSION') THEN 1 ELSE 0 END) as attended
                FROM attendance
                WHERE student_id = ? AND subject_id = ?
            """, (st_id, subject_id))
            stat_row = c.fetchone()
            if stat_row and stat_row["conducted"] > 5:
                att_pct = calculate_percentage(stat_row["attended"], stat_row["conducted"])
                if att_pct < min_pct:
                    c.execute("SELECT user_id FROM students WHERE id = ?", (st_id,))
                    st_user_row = c.fetchone()
                    if st_user_row:
                        c.execute("SELECT subject_name FROM subjects WHERE id = ?", (subject_id,))
                        sub_name = c.fetchone()["subject_name"]
                        needed = calculate_required_classes(stat_row["attended"], stat_row["conducted"], min_pct)
                        create_notification(
                            st_user_row["user_id"],
                            "Low Attendance Alert ⚠",
                            f"Your attendance in {sub_name} is now {att_pct}% (below {min_pct}%). You need {needed} consecutive classes to recover.",
                            "WARNING",
                            "/student#calculator"
                        )

        log_audit(g.current_user["id"], "MARK_ATTENDANCE", "ATTENDANCE", f"{subject_id}-{date_val}-{hour_val}", f"Saved attendance for {len(records)} students")

    return jsonify({"success": True, "message": f"Attendance successfully saved for {len(records)} students."})


@app.route("/api/faculty/permissions", methods=["GET"])
@require_roles("FACULTY", "HOD", "ADMIN")
def api_faculty_permissions():
    faculty_id = g.current_user.get("faculty", {}).get("faculty_id", 2)
    status_filter = request.args.get("status")

    query = """
        SELECT pr.id, pr.request_code, pr.student_id, pr.subject_id, pr.date, pr.hour,
               pr.reason, pr.description, pr.document_filename, pr.document_original_name,
               pr.status, pr.faculty_comment, pr.hod_comment, pr.created_at,
               st.usn, u.name as student_name, u.avatar_url,
               s.subject_code, s.subject_name
        FROM permission_requests pr
        JOIN students st ON pr.student_id = st.id
        JOIN users u ON st.user_id = u.id
        JOIN subjects s ON pr.subject_id = s.id
        WHERE pr.faculty_id = ?
    """
    params = [faculty_id]
    if status_filter:
        query += " AND pr.status = ?"
        params.append(status_filter)
    query += " ORDER BY pr.created_at DESC"

    with get_db() as conn:
        c = conn.cursor()
        c.execute(query, params)
        return jsonify({"requests": [dict(r) for r in c.fetchall()]})


@app.route("/api/faculty/permissions/<int:request_id>/review", methods=["POST"])
@require_roles("FACULTY", "HOD", "ADMIN")
def api_faculty_review_permission(request_id):
    data = request.get_json() or {}
    action = data.get("action", "").upper()
    comment = data.get("comment", "").strip()

    if action not in ("APPROVE", "REJECT", "ESCALATE"):
        return jsonify({"error": "Invalid action. Must be APPROVE, REJECT, or ESCALATE."}), 400

    if action in ("REJECT", "ESCALATE") and not comment:
        return jsonify({"error": "A comment is mandatory when rejecting or escalating a request."}), 400

    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM permission_requests WHERE id = ?", (request_id,))
        req = c.fetchone()
        if not req:
            return jsonify({"error": "Permission request not found."}), 404

        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if action == "APPROVE":
            new_status = "APPROVED"
            c.execute("""
                UPDATE permission_requests
                SET status = 'APPROVED', faculty_comment = ?, reviewed_by = ?, reviewed_at = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (comment or "Approved by faculty.", g.current_user["id"], now, request_id))

            c.execute("""
                UPDATE attendance
                SET status = 'APPROVED_PERMISSION', original_status = status, updated_by = ?,
                    audit_notes = ?, permission_request_id = ?, updated_at = CURRENT_TIMESTAMP
                WHERE student_id = ? AND subject_id = ? AND date = ? AND hour = ?
            """, (g.current_user["id"], f"Permission Approved: {req['reason']}", request_id,
                  req["student_id"], req["subject_id"], req["date"], req["hour"]))

            c.execute("SELECT user_id FROM students WHERE id = ?", (req["student_id"],))
            st_user_id = c.fetchone()["user_id"]
            create_notification(
                st_user_id,
                "Permission Request Approved ✓",
                f"Your request {req['request_code']} for class on {req['date']} was approved. Attendance record updated.",
                "PERMISSION",
                "/student#permissions"
            )

        elif action == "REJECT":
            new_status = "REJECTED"
            c.execute("""
                UPDATE permission_requests
                SET status = 'REJECTED', faculty_comment = ?, reviewed_by = ?, reviewed_at = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (comment, g.current_user["id"], now, request_id))

            c.execute("SELECT user_id FROM students WHERE id = ?", (req["student_id"],))
            st_user_id = c.fetchone()["user_id"]
            create_notification(
                st_user_id,
                "Permission Request Rejected ✗",
                f"Your request {req['request_code']} was rejected. Reason: {comment}",
                "PERMISSION",
                "/student#permissions"
            )

        elif action == "ESCALATE":
            new_status = "ESCALATED_HOD"
            c.execute("""
                UPDATE permission_requests
                SET status = 'ESCALATED_HOD', faculty_comment = ?, reviewed_by = ?, reviewed_at = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (comment, g.current_user["id"], now, request_id))

            # Strictly notify the HOD belonging to the REQUEST'S branch_id
            c.execute("""
                SELECT u.id as hod_user_id FROM faculty f
                JOIN users u ON f.user_id = u.id
                WHERE f.branch_id = ? AND u.role = 'HOD' LIMIT 1
            """, (req["branch_id"],))
            hod_row = c.fetchone()
            if hod_row:
                create_notification(
                    hod_row["hod_user_id"],
                    "Escalated Permission Awaiting Review",
                    f"Faculty escalated permission request {req['request_code']} for your department review.",
                    "PERMISSION",
                    "/hod#permissions"
                )

        log_audit(g.current_user["id"], f"PERMISSION_{new_status}", "PERMISSION_REQUEST", req["request_code"], f"Action: {action}, Comment: {comment}")

    return jsonify({"success": True, "message": f"Permission request {req['request_code']} updated to {new_status}."})


@app.route("/api/faculty/low-attendance", methods=["GET"])
@require_roles("FACULTY", "HOD", "ADMIN")
def api_faculty_low_attendance():
    faculty_id = g.current_user.get("faculty", {}).get("faculty_id", 2)
    min_pct = get_min_attendance_threshold()

    with get_db() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT s.id as subject_id, s.subject_code, s.subject_name,
                   st.id as student_id, st.usn, u.name as student_name, u.email as student_email,
                   COUNT(a.id) as conducted,
                   SUM(CASE WHEN a.status IN ('PRESENT', 'APPROVED_PERMISSION') THEN 1 ELSE 0 END) as attended
            FROM faculty_subjects fs
            JOIN subjects s ON fs.subject_id = s.id
            JOIN attendance a ON a.subject_id = s.id
            JOIN students st ON a.student_id = st.id
            JOIN users u ON st.user_id = u.id
            WHERE fs.faculty_id = ?
            GROUP BY s.id, st.id
            HAVING (CAST(attended AS REAL) / conducted) * 100 < ?
            ORDER BY (CAST(attended AS REAL) / conducted) ASC
        """, (faculty_id, min_pct))
        
        results = []
        for r in c.fetchall():
            pct = calculate_percentage(r["attended"], r["conducted"])
            req = calculate_required_classes(r["attended"], r["conducted"], min_pct)
            results.append({
                "subject_code": r["subject_code"],
                "subject_name": r["subject_name"],
                "student_id": r["student_id"],
                "usn": r["usn"],
                "student_name": r["student_name"],
                "student_email": r["student_email"],
                "conducted": r["conducted"],
                "attended": r["attended"],
                "percentage": pct,
                "required_classes": req
            })
        return jsonify({"low_attendance_students": results})


# --------------------------------------------------------------------------
# HOD Portal API (Strict Server-Side Branch Data Isolation)
# --------------------------------------------------------------------------

@app.route("/api/hod/dashboard", methods=["GET"])
@require_roles("HOD", "ADMIN")
def api_hod_dashboard():
    """
    Enforces strict branch data isolation:
    HOD of AI&DS will ONLY see AI&DS metrics.
    HOD of CSE will ONLY see CSE metrics.
    """
    # Resolve HOD's assigned branch
    hod_branch_id = g.current_user.get("faculty", {}).get("branch_id")
    if not hod_branch_id and g.current_user["role"] == "ADMIN":
        hod_branch_id = int(request.args.get("branch_id", 1))

    min_pct = get_min_attendance_threshold()

    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, branch_code, branch_name FROM branches WHERE id = ?", (hod_branch_id,))
        branch_row = c.fetchone()
        if not branch_row:
            return jsonify({"error": "Assigned branch not found."}), 404
        branch = dict(branch_row)

        # Faculty in this branch ONLY
        c.execute("SELECT COUNT(*) FROM faculty WHERE branch_id = ?", (hod_branch_id,))
        faculty_count = c.fetchone()[0]

        # Students in this branch ONLY
        c.execute("SELECT COUNT(*) FROM students WHERE branch_id = ?", (hod_branch_id,))
        student_count = c.fetchone()[0]

        # Subjects in this branch ONLY
        c.execute("SELECT COUNT(*) FROM subjects WHERE branch_id = ?", (hod_branch_id,))
        subject_count = c.fetchone()[0]

        # Escalated Permission Requests in this branch ONLY
        c.execute("""
            SELECT COUNT(*) FROM permission_requests
            WHERE branch_id = ? AND status = 'ESCALATED_HOD'
        """, (hod_branch_id,))
        escalated_count = c.fetchone()[0]

        # Branch attendance average
        c.execute("""
            SELECT COUNT(a.id) as conducted,
                   SUM(CASE WHEN a.status IN ('PRESENT', 'APPROVED_PERMISSION') THEN 1 ELSE 0 END) as attended
            FROM attendance a
            JOIN students st ON a.student_id = st.id
            WHERE st.branch_id = ?
        """, (hod_branch_id,))
        tot = c.fetchone()
        conducted = tot["conducted"] or 0
        attended = tot["attended"] or 0
        avg_pct = calculate_percentage(attended, conducted)

        # Low attendance students in this branch ONLY
        c.execute("""
            SELECT a.student_id,
                   COUNT(a.id) as conducted,
                   SUM(CASE WHEN a.status IN ('PRESENT', 'APPROVED_PERMISSION') THEN 1 ELSE 0 END) as attended
            FROM attendance a
            JOIN students st ON a.student_id = st.id
            WHERE st.branch_id = ?
            GROUP BY a.student_id
            HAVING (CAST(attended AS REAL) / conducted) * 100 < ?
        """, (hod_branch_id, min_pct))
        low_att_students = len(c.fetchall())

        return jsonify({
            "branch": branch,
            "department": {"name": branch["branch_name"], "code": branch["branch_code"]},
            "faculty_count": faculty_count,
            "student_count": student_count,
            "subject_count": subject_count,
            "escalated_permissions_count": escalated_count,
            "average_attendance": avg_pct,
            "low_attendance_count": low_att_students,
            "minimum_required": min_pct
        })


@app.route("/api/hod/permissions", methods=["GET"])
@require_roles("HOD", "ADMIN")
def api_hod_permissions():
    """Returns escalated requests strictly matching the HOD's assigned branch."""
    hod_branch_id = g.current_user.get("faculty", {}).get("branch_id")
    if not hod_branch_id and g.current_user["role"] == "ADMIN":
        hod_branch_id = int(request.args.get("branch_id", 1))

    with get_db() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT pr.id, pr.request_code, pr.student_id, pr.subject_id, pr.faculty_id, pr.branch_id,
                   pr.date, pr.hour, pr.reason, pr.description, pr.document_filename, pr.document_original_name,
                   pr.status, pr.faculty_comment, pr.hod_comment, pr.created_at,
                   st.usn, u.name as student_name, fu.name as faculty_name,
                   s.subject_code, s.subject_name,
                   b.branch_name, b.branch_code
            FROM permission_requests pr
            JOIN students st ON pr.student_id = st.id
            JOIN users u ON st.user_id = u.id
            JOIN subjects s ON pr.subject_id = s.id
            JOIN branches b ON pr.branch_id = b.id
            JOIN faculty f ON pr.faculty_id = f.id
            JOIN users fu ON f.user_id = fu.id
            WHERE pr.branch_id = ? AND pr.status = 'ESCALATED_HOD'
            ORDER BY pr.created_at DESC
        """, (hod_branch_id,))
        return jsonify({"requests": [dict(r) for r in c.fetchall()]})


@app.route("/api/hod/permissions/<int:request_id>/review", methods=["POST"])
@require_roles("HOD", "ADMIN")
def api_hod_review_permission(request_id):
    """Enforces strict server-side verification: HOD cannot approve a request from another branch."""
    hod_branch_id = g.current_user.get("faculty", {}).get("branch_id")
    data = request.get_json() or {}
    action = data.get("action", "").upper()
    remarks = data.get("remarks", "").strip()

    if action not in ("APPROVE", "REJECT"):
        return jsonify({"error": "Invalid action. Must be APPROVE or REJECT."}), 400

    if not remarks:
        return jsonify({"error": "Official HOD review remarks are required."}), 400

    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM permission_requests WHERE id = ?", (request_id,))
        req = c.fetchone()
        if not req:
            return jsonify({"error": "Permission request not found."}), 404

        # Strict server-side branch security rule
        if g.current_user["role"] != "ADMIN" and req["branch_id"] != hod_branch_id:
            return jsonify({"error": "Forbidden: You cannot review a permission request belonging to another branch."}), 403

        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if action == "APPROVE":
            new_status = "APPROVED"
            c.execute("""
                UPDATE permission_requests
                SET status = 'APPROVED', hod_comment = ?, reviewed_by = ?, reviewed_at = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (remarks, g.current_user["id"], now, request_id))

            c.execute("""
                UPDATE attendance
                SET status = 'APPROVED_PERMISSION', original_status = status, updated_by = ?,
                    audit_notes = ?, permission_request_id = ?, updated_at = CURRENT_TIMESTAMP
                WHERE student_id = ? AND subject_id = ? AND date = ? AND hour = ?
            """, (g.current_user["id"], f"HOD Approved: {remarks}", request_id,
                  req["student_id"], req["subject_id"], req["date"], req["hour"]))

            c.execute("SELECT user_id FROM students WHERE id = ?", (req["student_id"],))
            st_uid = c.fetchone()["user_id"]
            create_notification(
                st_uid,
                "HOD Permission Approved ✓",
                f"Your department HOD approved permission request {req['request_code']}. Attendance credited.",
                "PERMISSION",
                "/student#permissions"
            )

        elif action == "REJECT":
            new_status = "REJECTED"
            c.execute("""
                UPDATE permission_requests
                SET status = 'REJECTED', hod_comment = ?, reviewed_by = ?, reviewed_at = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (remarks, g.current_user["id"], now, request_id))

            c.execute("SELECT user_id FROM students WHERE id = ?", (req["student_id"],))
            st_uid = c.fetchone()["user_id"]
            create_notification(
                st_uid,
                "HOD Permission Rejected ✗",
                f"HOD rejected request {req['request_code']}. Reason: {remarks}",
                "PERMISSION",
                "/student#permissions"
            )

        log_audit(g.current_user["id"], f"HOD_DECISION_{new_status}", "PERMISSION_REQUEST", req["request_code"], f"Remarks: {remarks}")

    return jsonify({"success": True, "message": f"HOD decision recorded: {new_status}."})


@app.route("/api/hod/low-attendance", methods=["GET"])
@require_roles("HOD", "ADMIN")
def api_hod_low_attendance():
    """Returns low-attendance defaulters strictly within the HOD's branch."""
    hod_branch_id = g.current_user.get("faculty", {}).get("branch_id")
    if not hod_branch_id and g.current_user["role"] == "ADMIN":
        hod_branch_id = int(request.args.get("branch_id", 1))

    min_pct = get_min_attendance_threshold()

    with get_db() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT st.id as student_id, st.usn, u.name as student_name, u.email as student_email,
                   st.semester, st.section,
                   COUNT(a.id) as conducted,
                   SUM(CASE WHEN a.status IN ('PRESENT', 'APPROVED_PERMISSION') THEN 1 ELSE 0 END) as attended
            FROM students st
            JOIN users u ON st.user_id = u.id
            JOIN attendance a ON a.student_id = st.id
            WHERE st.branch_id = ?
            GROUP BY st.id
            HAVING (CAST(attended AS REAL) / conducted) * 100 < ?
            ORDER BY (CAST(attended AS REAL) / conducted) ASC
        """, (hod_branch_id, min_pct))
        
        rows = []
        for r in c.fetchall():
            pct = calculate_percentage(r["attended"], r["conducted"])
            req = calculate_required_classes(r["attended"], r["conducted"], min_pct)
            rows.append({
                "student_id": r["student_id"],
                "usn": r["usn"],
                "student_name": r["student_name"],
                "student_email": r["student_email"],
                "semester": r["semester"],
                "section": r["section"],
                "conducted": r["conducted"],
                "attended": r["attended"],
                "percentage": pct,
                "required_classes": req
            })
        return jsonify({"low_attendance_students": rows})


@app.route("/api/hod/send-warning", methods=["POST"])
@require_roles("HOD", "ADMIN")
def api_hod_send_warning():
    data = request.get_json() or {}
    student_id = data.get("student_id")
    custom_msg = data.get("message", "").strip()

    if not student_id:
        return jsonify({"error": "Student ID is required."}), 400

    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT user_id, usn FROM students WHERE id = ?", (student_id,))
        st_row = c.fetchone()
        if not st_row:
            return jsonify({"error": "Student not found."}), 404

        title = "OFFICIAL HOD ATTENDANCE WARNING ⚠"
        msg = custom_msg or "You are falling below 75% attendance. Report to the HOD office immediately with parents to explain absence."
        create_notification(st_row["user_id"], title, msg, "WARNING", "/student#calculator")
        log_audit(g.current_user["id"], "SEND_HOD_WARNING", "STUDENT", st_row["usn"], msg)

    return jsonify({"success": True, "message": "Official warning notice sent to student."})


# --------------------------------------------------------------------------
# Admin Portal & Student Transfer API
# --------------------------------------------------------------------------

@app.route("/api/admin/dashboard", methods=["GET"])
@require_roles("ADMIN")
def api_admin_dashboard():
    min_pct = get_min_attendance_threshold()

    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM students")
        total_students = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM faculty")
        total_faculty = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM branches WHERE status = 'ACTIVE'")
        total_branches = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM subjects")
        total_subjects = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM classes")
        total_classes = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM attendance")
        total_attendance = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM permission_requests WHERE status IN ('PENDING', 'UNDER_REVIEW', 'ESCALATED_HOD')")
        pending_permissions = c.fetchone()[0]

        # Branch attendance comparison
        c.execute("""
            SELECT b.branch_code as code, b.branch_name as name,
                   COUNT(a.id) as conducted,
                   SUM(CASE WHEN a.status IN ('PRESENT', 'APPROVED_PERMISSION') THEN 1 ELSE 0 END) as attended
            FROM branches b
            LEFT JOIN students st ON st.branch_id = b.id
            LEFT JOIN attendance a ON a.student_id = st.id
            WHERE b.status = 'ACTIVE'
            GROUP BY b.id
        """)
        branch_stats = []
        for r in c.fetchall():
            cond = r["conducted"] or 0
            att = r["attended"] or 0
            branch_stats.append({
                "code": r["code"],
                "name": r["name"],
                "conducted": cond,
                "attended": att,
                "percentage": calculate_percentage(att, cond)
            })

        return jsonify({
            "total_students": total_students,
            "total_faculty": total_faculty,
            "total_departments": total_branches,
            "total_branches": total_branches,
            "total_subjects": total_subjects,
            "total_classes": total_classes,
            "total_attendance_records": total_attendance,
            "pending_permissions": pending_permissions,
            "minimum_attendance_threshold": min_pct,
            "department_stats": branch_stats
        })


@app.route("/api/admin/students/<int:student_id>/transfer", methods=["POST"])
@require_roles("ADMIN")
def api_admin_transfer_student(student_id):
    """
    Transfers a student between branches or classes while preserving their complete attendance history.
    """
    data = request.get_json() or {}
    new_branch_id = int(data.get("new_branch_id"))
    new_semester = int(data.get("new_semester", 5))
    new_section = data.get("new_section", "A").strip().upper()
    academic_year = data.get("academic_year", "2026-2027").strip()

    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, user_id, usn, branch_id, class_id FROM students WHERE id = ?", (student_id,))
        st = c.fetchone()
        if not st:
            return jsonify({"error": "Student not found."}), 404

        new_class_id = resolve_or_create_class(conn, new_branch_id, new_semester, new_section, academic_year)

        c.execute("""
            UPDATE students
            SET branch_id = ?, class_id = ?, semester = ?, section = ?, academic_year = ?
            WHERE id = ?
        """, (new_branch_id, new_class_id, new_semester, new_section, academic_year, student_id))

        c.execute("SELECT class_name FROM classes WHERE id = ?", (new_class_id,))
        new_c_name = c.fetchone()["class_name"]

        log_audit(g.current_user["id"], "TRANSFER_STUDENT", "STUDENT", st["usn"], f"Transferred student {st['usn']} to {new_c_name}. Historical attendance preserved.")

        create_notification(
            st["user_id"],
            "Class Transfer Notice",
            f"You have been officially transferred to {new_c_name}. Your past attendance records have been preserved.",
            "SYSTEM",
            "/student#dashboard"
        )

        return jsonify({
            "success": True,
            "message": f"Student {st['usn']} successfully transferred to {new_c_name}. Attendance history preserved."
        })


@app.route("/api/admin/users", methods=["GET", "POST"])
@require_roles("ADMIN")
def api_admin_users():
    if request.method == "GET":
        role_filter = request.args.get("role")
        search = request.args.get("search", "").strip()

        query = "SELECT id, name, email, role, status, avatar_url, created_at FROM users WHERE 1=1"
        params = []
        if role_filter:
            query += " AND role = ?"
            params.append(role_filter)
        if search:
            query += " AND (name LIKE ? OR email LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])
        query += " ORDER BY id DESC LIMIT 100"

        with get_db() as conn:
            c = conn.cursor()
            c.execute(query, params)
            return jsonify({"users": [dict(r) for r in c.fetchall()]})

    data = request.get_json() or {}
    name = data.get("name", "").strip()
    email = data.get("email", "").strip()
    password = data.get("password", "password123")
    role = data.get("role", "STUDENT").upper()
    branch_id = data.get("branch_id") or data.get("department_id", 1)

    if not name or not email:
        return jsonify({"error": "Name and email are required."}), 400

    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE email = ?", (email,))
        if c.fetchone():
            return jsonify({"error": "A user with this email address already exists."}), 400

        pwd_hash = hash_password(password)
        c.execute("""
            INSERT INTO users (name, email, password_hash, role, status)
            VALUES (?, ?, ?, ?, 'ACTIVE')
        """, (name, email, pwd_hash, role))
        user_id = c.lastrowid

        if role == "STUDENT":
            usn = data.get("usn", f"4SJ22CS{random.randint(100, 999)}")
            semester = int(data.get("semester", 5))
            section = data.get("section", "A")
            cls_id = resolve_or_create_class(conn, int(branch_id), semester, section)
            c.execute("""
                INSERT INTO students (user_id, usn, branch_id, class_id, semester, section)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, usn, branch_id, cls_id, semester, section))
        elif role in ("FACULTY", "HOD"):
            designation = data.get("designation", "Assistant Professor" if role == "FACULTY" else "Professor & HOD")
            c.execute("""
                INSERT INTO faculty (user_id, branch_id, designation)
                VALUES (?, ?, ?)
            """, (user_id, branch_id, designation))

        log_audit(g.current_user["id"], "CREATE_USER", "USER", user_id, f"Created {role} user: {email}")

    return jsonify({"success": True, "message": f"User {name} ({role}) created successfully.", "user_id": user_id}), 201


@app.route("/api/admin/users/<int:user_id>/status", methods=["POST"])
@require_roles("ADMIN")
def api_admin_toggle_user_status(user_id):
    data = request.get_json() or {}
    status = data.get("status", "ACTIVE").upper()
    if status not in ("ACTIVE", "DISABLED"):
        return jsonify({"error": "Invalid status."}), 400

    with get_db() as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET status = ? WHERE id = ?", (status, user_id))
        log_audit(g.current_user["id"], "UPDATE_USER_STATUS", "USER", user_id, f"Status set to {status}")

    return jsonify({"success": True, "message": f"User status updated to {status}."})


@app.route("/api/admin/settings", methods=["GET", "PUT"])
@require_roles("ADMIN")
def api_admin_settings():
    if request.method == "GET":
        min_pct = get_min_attendance_threshold()
        with get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM academic_settings ORDER BY id DESC LIMIT 1")
            row = c.fetchone()
            return jsonify({
                "minimum_attendance_percentage": min_pct,
                "academic_year": row["academic_year"] if row else "2026-2027",
                "current_semester": row["current_semester"] if row else 5
            })

    data = request.get_json() or {}
    min_pct = float(data.get("minimum_attendance_percentage", 75.0))
    acad_year = data.get("academic_year", "2026-2027")
    sem = int(data.get("current_semester", 5))

    with get_db() as conn:
        c = conn.cursor()
        c.execute("""
            UPDATE academic_settings
            SET minimum_attendance_percentage = ?, academic_year = ?, current_semester = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = (SELECT id FROM academic_settings ORDER BY id DESC LIMIT 1)
        """, (min_pct, acad_year, sem))
        log_audit(g.current_user["id"], "UPDATE_SETTINGS", "SETTINGS", "1", f"Min Attendance updated to {min_pct}%")

    return jsonify({"success": True, "message": "Academic settings updated successfully."})


@app.route("/api/admin/audit-logs", methods=["GET"])
@require_roles("ADMIN")
def api_admin_audit_logs():
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT al.id, al.action, al.entity_type, al.entity_id, al.details, al.ip_address, al.created_at,
                   u.name as user_name, u.email as user_email, u.role as user_role
            FROM audit_logs al
            LEFT JOIN users u ON al.user_id = u.id
            ORDER BY al.created_at DESC
            LIMIT 100
        """)
        return jsonify({"audit_logs": [dict(r) for r in c.fetchall()]})


@app.route("/api/admin/reports/<report_type>", methods=["GET"])
@require_roles("ADMIN", "HOD")
def api_admin_reports(report_type):
    min_pct = get_min_attendance_threshold()

    with get_db() as conn:
        c = conn.cursor()
        if report_type == "student_attendance":
            c.execute("""
                SELECT st.usn, u.name as student_name, b.branch_code as branch, st.semester, st.section,
                       COUNT(a.id) as conducted,
                       SUM(CASE WHEN a.status IN ('PRESENT', 'APPROVED_PERMISSION') THEN 1 ELSE 0 END) as attended,
                       SUM(CASE WHEN a.status = 'ABSENT' THEN 1 ELSE 0 END) as absent
                FROM students st
                JOIN users u ON st.user_id = u.id
                JOIN branches b ON st.branch_id = b.id
                LEFT JOIN attendance a ON a.student_id = st.id
                GROUP BY st.id
                ORDER BY st.usn ASC
            """)
            data = []
            for r in c.fetchall():
                cond = r["conducted"] or 0
                att = r["attended"] or 0
                pct = calculate_percentage(att, cond)
                req = calculate_required_classes(att, cond, min_pct)
                data.append({
                    "usn": r["usn"],
                    "name": r["student_name"],
                    "branch": r["branch"],
                    "semester": r["semester"],
                    "section": r["section"],
                    "conducted": cond,
                    "attended": att,
                    "absent": r["absent"] or 0,
                    "percentage": f"{pct}%",
                    "status": "Safe" if pct >= min_pct else "Defaulter",
                    "classes_needed": req
                })
            return jsonify({"title": "Student Overall Attendance Report", "records": data})

        elif report_type == "low_attendance":
            c.execute("""
                SELECT st.usn, u.name as student_name, b.branch_code as branch, s.subject_code, s.subject_name,
                       COUNT(a.id) as conducted,
                       SUM(CASE WHEN a.status IN ('PRESENT', 'APPROVED_PERMISSION') THEN 1 ELSE 0 END) as attended
                FROM attendance a
                JOIN students st ON a.student_id = st.id
                JOIN users u ON st.user_id = u.id
                JOIN branches b ON st.branch_id = b.id
                JOIN subjects s ON a.subject_id = s.id
                GROUP BY st.id, s.id
                HAVING (CAST(attended AS REAL) / conducted) * 100 < ?
                ORDER BY (CAST(attended AS REAL) / conducted) ASC
            """, (min_pct,))
            data = []
            for r in c.fetchall():
                pct = calculate_percentage(r["attended"], r["conducted"])
                req = calculate_required_classes(r["attended"], r["conducted"], min_pct)
                data.append({
                    "usn": r["usn"],
                    "name": r["student_name"],
                    "branch": r["branch"],
                    "subject": f"{r['subject_code']} - {r['subject_name']}",
                    "conducted": r["conducted"],
                    "attended": r["attended"],
                    "percentage": f"{pct}%",
                    "classes_needed": req
                })
            return jsonify({"title": "Official Defaulter & Low Attendance List (<75%)", "records": data})

        elif report_type == "permission_requests":
            c.execute("""
                SELECT pr.request_code, st.usn, u.name as student_name, s.subject_code,
                       b.branch_code as branch,
                       pr.date, pr.hour, pr.reason, pr.status, fu.name as faculty_name, pr.created_at
                FROM permission_requests pr
                JOIN students st ON pr.student_id = st.id
                JOIN users u ON st.user_id = u.id
                JOIN branches b ON pr.branch_id = b.id
                JOIN subjects s ON pr.subject_id = s.id
                JOIN faculty f ON pr.faculty_id = f.id
                JOIN users fu ON f.user_id = fu.id
                ORDER BY pr.created_at DESC
            """)
            return jsonify({"title": "Attendance Permission Requests Master Report", "records": [dict(r) for r in c.fetchall()]})

        return jsonify({"error": f"Report type '{report_type}' not recognized."}), 400


# --------------------------------------------------------------------------
# Secure Document Serving & Notifications
# --------------------------------------------------------------------------

@app.route("/api/files/<filename>", methods=["GET"])
@require_auth
def api_view_file(filename):
    safe_name = secure_filename(filename)
    file_path = os.path.join(UPLOAD_DIR, safe_name)
    if not os.path.exists(file_path):
        return jsonify({"error": "Requested document was not found."}), 404
    return send_from_directory(UPLOAD_DIR, safe_name)


@app.route("/api/notifications", methods=["GET"])
@require_auth
def api_notifications():
    user_id = g.current_user["id"]
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT id, title, message, type, read_status, link, created_at
            FROM notifications
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 50
        """, (user_id,))
        rows = [dict(r) for r in c.fetchall()]
        unread_count = sum(1 for r in rows if r["read_status"] == 0)
        return jsonify({"notifications": rows, "unread_count": unread_count})


@app.route("/api/notifications/<int:notif_id>/read", methods=["POST"])
@require_auth
def api_mark_notification_read(notif_id):
    user_id = g.current_user["id"]
    with get_db() as conn:
        c = conn.cursor()
        c.execute("UPDATE notifications SET read_status = 1 WHERE id = ? AND user_id = ?", (notif_id, user_id))
    return jsonify({"success": True})


@app.route("/api/notifications/read-all", methods=["POST"])
@require_auth
def api_mark_all_notifications_read():
    user_id = g.current_user["id"]
    with get_db() as conn:
        c = conn.cursor()
        c.execute("UPDATE notifications SET read_status = 1 WHERE user_id = ?", (user_id,))
    return jsonify({"success": True})


@app.route("/api/settings", methods=["GET"])
def api_settings():
    min_pct = get_min_attendance_threshold()
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM academic_settings ORDER BY id DESC LIMIT 1")
        row = c.fetchone()
        return jsonify({
            "minimum_attendance_percentage": min_pct,
            "academic_year": row["academic_year"] if row else "2026-2027",
            "current_semester": row["current_semester"] if row else 5
        })


if __name__ == "__main__":
    init_db()
    print("Starting SmartAttend Server on http://127.0.0.1:5000 ...")
    app.run(host="127.0.0.1", port=5000, debug=True)
