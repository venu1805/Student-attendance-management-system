"""
SmartAttend - Comprehensive Automated Test Suite
Testing:
1. Calculations & Math Engine
2. Dynamic Branch Creation (+ Add New Branch)
3. Faculty Student Addition & Credentials Return
4. Class Master Data & Class Student Roster
5. Multi-Faculty Shared Class Roster
6. Student Password Management & Strong Validation
7. Forgot Password OTP / Token Reset Flow
8. Strict HOD Branch Data Isolation & Cross-Branch Authorization Guard
9. Admin Student Transfer with Attendance History Preservation
10. Full End-to-End Permission Request Workflow
"""
import unittest
from calculations import (
    calculate_percentage,
    calculate_required_classes,
    calculate_missable_classes,
    get_attendance_status
)
from database import get_db
from auth import (
    hash_password, verify_password, create_token, decode_token,
    validate_password_strength
)
from seed_data import seed_database
from app import app


class TestSmartAttendFull(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        seed_database()

    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_01_calculations_engine(self):
        """Test percentage, required consecutive classes, and edge cases."""
        self.assertEqual(calculate_percentage(68, 100), 68.0)
        self.assertEqual(calculate_required_classes(68, 100, 75.0), 28)
        self.assertEqual(calculate_percentage(25, 35), 71.4)
        self.assertEqual(calculate_required_classes(25, 35, 75.0), 5)
        self.assertEqual(calculate_percentage(82, 100), 82.0)
        self.assertEqual(calculate_required_classes(82, 100, 75.0), 0)
        self.assertEqual(calculate_missable_classes(82, 100, 75.0), 9)

    def test_02_password_validation(self):
        """Test strong password policy validation."""
        valid, msg = validate_password_strength("simple")
        self.assertFalse(valid)
        valid, msg = validate_password_strength("NoSpecial123")
        self.assertFalse(valid)
        valid, msg = validate_password_strength("ValidPass@2026")
        self.assertTrue(valid)

    def test_03_dynamic_branch_creation(self):
        """Test dynamic '+ Add New Branch' (e.g. Computer Science and Business Systems)."""
        fac_token = create_token(3, "FACULTY", "faculty@college.edu", "Prof. Arvind Kumar")
        res = self.app.post("/api/branches", headers={"Authorization": f"Bearer {fac_token}"}, json={
            "branch_name": "Computer Science and Business Systems"
        })
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["branch"]["branch_code"], "CSBS")

        # Verify it is immediately selectable in GET /api/branches
        list_res = self.app.get("/api/branches", headers={"Authorization": f"Bearer {fac_token}"})
        branches = list_res.get_json()["branches"]
        self.assertTrue(any(b["branch_name"] == "Computer Science and Business Systems" for b in branches))

    def test_04_faculty_add_student(self):
        """Test Faculty adding a new student, receiving credentials, and verifying class allocation."""
        fac_token = create_token(3, "FACULTY", "faculty@college.edu", "Prof. Arvind Kumar")
        new_usn = "4SJ23AD099"
        res = self.app.post("/api/faculty/students", headers={"Authorization": f"Bearer {fac_token}"}, json={
            "name": "Karthik Raja",
            "usn": new_usn,
            "email": "karthik.raja@college.edu",
            "phone": "+91 98888 77777",
            "branch_id": 1,  # AI & DS
            "semester": 4,
            "section": "A",
            "academic_year": "2026-2027",
            "roll_no": "99"
        })
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("credentials", data)
        self.assertEqual(data["credentials"]["usn"], new_usn)
        temp_pwd = data["credentials"]["temporary_password"]

        # Verify newly created student can log in
        login_res = self.app.post("/api/auth/login", json={
            "email": "karthik.raja@college.edu",
            "password": temp_pwd
        })
        self.assertEqual(login_res.status_code, 200)

    def test_05_class_student_roster_shared_between_faculty(self):
        """Test class roster availability and allocation across multiple faculty."""
        fac_a_token = create_token(3, "FACULTY", "faculty@college.edu", "Prof. Arvind Kumar")
        fac_b_token = create_token(8, "FACULTY", "sneha.iyer@college.edu", "Prof. Sneha Iyer")

        # Faculty A queries Class 1 (4 AI&DS A)
        res_a = self.app.get("/api/classes/1/students", headers={"Authorization": f"Bearer {fac_a_token}"})
        self.assertEqual(res_a.status_code, 200)
        students_a = res_a.get_json()["students"]
        self.assertGreater(len(students_a), 0)

        # Faculty B queries the exact same class and sees the same students
        res_b = self.app.get("/api/classes/1/students", headers={"Authorization": f"Bearer {fac_b_token}"})
        self.assertEqual(res_b.status_code, 200)
        students_b = res_b.get_json()["students"]
        self.assertEqual(len(students_a), len(students_b))

        # Faculty B assigns those students to a subject
        assign_res = self.app.post("/api/faculty/subjects/8/assign-students", headers={"Authorization": f"Bearer {fac_b_token}"}, json={
            "class_id": 1,
            "student_ids": [s["student_id"] for s in students_b]
        })
        self.assertEqual(assign_res.status_code, 200)
        self.assertTrue(assign_res.get_json()["success"])

    def test_06_student_password_change(self):
        """Test student self-service password change with strong validation."""
        student_token = create_token(9, "STUDENT", "student@college.edu", "Rahul Sharma")
        
        # Test weak password rejection
        fail_res = self.app.post("/api/auth/change-password", headers={"Authorization": f"Bearer {student_token}"}, json={
            "current_password": "password123",
            "new_password": "weak",
            "confirm_password": "weak"
        })
        self.assertEqual(fail_res.status_code, 400)

        # Test successful password change
        succ_res = self.app.post("/api/auth/change-password", headers={"Authorization": f"Bearer {student_token}"}, json={
            "current_password": "password123",
            "new_password": "RahulNewPass@2026",
            "confirm_password": "RahulNewPass@2026"
        })
        self.assertEqual(succ_res.status_code, 200)

        # Verify old password no longer works
        old_login = self.app.post("/api/auth/login", json={
            "email": "student@college.edu",
            "password": "password123"
        })
        self.assertEqual(old_login.status_code, 401)

        # Verify new password logs in
        new_login = self.app.post("/api/auth/login", json={
            "email": "student@college.edu",
            "password": "RahulNewPass@2026"
        })
        self.assertEqual(new_login.status_code, 200)

    def test_07_forgot_password_flow(self):
        """Test forgot-password OTP generation and identity-verified password reset."""
        # 1. Request reset code
        req_res = self.app.post("/api/auth/forgot-password/request", json={
            "email": "venu.aids@college.edu"
        })
        self.assertEqual(req_res.status_code, 200)
        otp = req_res.get_json()["otp_preview"]

        # 2. Reset password using OTP
        reset_res = self.app.post("/api/auth/forgot-password/reset", json={
            "email": "venu.aids@college.edu",
            "otp": otp,
            "new_password": "VenuSecure@2026",
            "confirm_password": "VenuSecure@2026"
        })
        self.assertEqual(reset_res.status_code, 200)

        # 3. Verify new login works
        login_res = self.app.post("/api/auth/login", json={
            "email": "venu.aids@college.edu",
            "password": "VenuSecure@2026"
        })
        self.assertEqual(login_res.status_code, 200)

    def test_08_strict_hod_branch_data_isolation(self):
        """
        Verify that HOD of CSE ONLY sees CSE data and CANNOT review AI&DS permission requests.
        """
        # HOD CSE (Dr. Rajesh Sharma, branch_id = 2)
        cse_hod_token = create_token(2, "HOD", "hod@college.edu", "Dr. Rajesh Sharma")
        cse_perms = self.app.get("/api/hod/permissions", headers={"Authorization": f"Bearer {cse_hod_token}"})
        self.assertEqual(cse_perms.status_code, 200)
        cse_requests = cse_perms.get_json()["requests"]
        # Must only contain CSE requests
        for r in cse_requests:
            self.assertEqual(r["branch_id"], 2)

        # Cross-branch authorization attempt: CSE HOD tries to review AI&DS request 4
        cross_attempt = self.app.post("/api/hod/permissions/4/review", headers={"Authorization": f"Bearer {cse_hod_token}"}, json={
            "action": "APPROVE",
            "remarks": "Illegitimate cross-branch review attempt"
        })
        self.assertEqual(cross_attempt.status_code, 403)
        self.assertIn("Forbidden", cross_attempt.get_json()["error"])

        # Legitimate AI&DS HOD (Dr. K. S. Rao, branch_id = 1) reviews request 4
        aids_hod_token = create_token(7, "HOD", "hod.aids@college.edu", "Dr. K. S. Rao")
        aids_perms = self.app.get("/api/hod/permissions", headers={"Authorization": f"Bearer {aids_hod_token}"})
        self.assertEqual(aids_perms.status_code, 200)
        aids_requests = aids_perms.get_json()["requests"]
        self.assertTrue(any(r["id"] == 4 for r in aids_requests))

        # Legitimate approval succeeds
        succ_review = self.app.post("/api/hod/permissions/4/review", headers={"Authorization": f"Bearer {aids_hod_token}"}, json={
            "action": "APPROVE",
            "remarks": "Sanctioned duty leave as department HOD."
        })
        self.assertEqual(succ_review.status_code, 200)

    def test_09_admin_student_transfer(self):
        """Test admin transferring a student while preserving historical attendance."""
        admin_token = create_token(1, "ADMIN", "admin@college.edu", "ERP Administrator")
        
        # Count pre-transfer attendance records for student 1 (Rahul Sharma)
        with get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM attendance WHERE student_id = 1")
            pre_count = c.fetchone()[0]

        # Transfer student 1 to Section B
        trans_res = self.app.post("/api/admin/students/1/transfer", headers={"Authorization": f"Bearer {admin_token}"}, json={
            "new_branch_id": 2, # CSE
            "new_semester": 5,
            "new_section": "B",
            "academic_year": "2026-2027"
        })
        self.assertEqual(trans_res.status_code, 200)

        # Verify attendance history is 100% preserved
        with get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM attendance WHERE student_id = 1")
            post_count = c.fetchone()[0]
            self.assertEqual(pre_count, post_count)

            # Verify student's section is now B
            c.execute("SELECT section FROM students WHERE id = 1")
            self.assertEqual(c.fetchone()["section"], "B")

    def test_10_get_profile(self):
        """Test GET /api/profile authentication, role metadata, and password hash concealment."""
        # 1. Unauthorized request
        unauth = self.app.get("/api/profile")
        self.assertEqual(unauth.status_code, 401)

        # 2. Student Profile (User 10, Venu Gopal - AI&DS)
        student_token = create_token(10, "STUDENT", "venu.aids@college.edu", "Venu Gopal")
        res = self.app.get("/api/profile", headers={"Authorization": f"Bearer {student_token}"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        profile = data["profile"]
        self.assertEqual(profile["id"], 10)
        self.assertEqual(profile["email"], "venu.aids@college.edu")
        self.assertEqual(profile["role"], "STUDENT")
        self.assertEqual(profile["usn"], "4SJ23AD001")
        self.assertEqual(profile["branch_code"], "AI&DS")
        self.assertEqual(profile["semester"], 4)
        self.assertEqual(profile["section"], "A")
        self.assertEqual(profile["roll_no"], "01")
        self.assertEqual(profile["academic_year"], "2026-2027")
        self.assertNotIn("password_hash", profile)
        self.assertNotIn("password", profile)

        # 3. Faculty Profile (User 3, Prof. Arvind Kumar - CSE)
        fac_token = create_token(3, "FACULTY", "faculty@college.edu", "Prof. Arvind Kumar")
        fac_res = self.app.get("/api/profile", headers={"Authorization": f"Bearer {fac_token}"})
        self.assertEqual(fac_res.status_code, 200)
        fac_profile = fac_res.get_json()["profile"]
        self.assertEqual(fac_profile["role"], "FACULTY")
        self.assertEqual(fac_profile["designation"], "Associate Professor")
        self.assertEqual(fac_profile["branch_code"], "CSE")
        self.assertNotIn("password_hash", fac_profile)

    def test_11_put_profile_editing_and_tamper_resistance(self):
        """Test PUT /api/profile update validation, persistence, and privilege tamper resistance."""
        student_token = create_token(10, "STUDENT", "venu.aids@college.edu", "Venu Gopal")

        # 1. Update permitted fields while attempting unauthorized privilege tampering
        update_res = self.app.put("/api/profile", headers={"Authorization": f"Bearer {student_token}"}, json={
            "name": "Venu Gopal Sharma",
            "phone": "+91 98765 43210",
            "avatar_url": "https://images.unsplash.com/photo-custom-profile?w=150",
            # Malicious tamper attempts that must be ignored
            "role": "ADMIN",
            "usn": "HACKED_USN_999",
            "branch_id": 99,
            "id": 1
        })
        self.assertEqual(update_res.status_code, 200)
        data = update_res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["message"], "Profile updated successfully.")
        
        updated = data["profile"]
        self.assertEqual(updated["name"], "Venu Gopal Sharma")
        self.assertEqual(updated["phone"], "+91 98765 43210")
        self.assertEqual(updated["avatar_url"], "https://images.unsplash.com/photo-custom-profile?w=150")
        # Ensure immutable fields were not tampered
        self.assertEqual(updated["role"], "STUDENT")
        self.assertEqual(updated["usn"], "4SJ23AD001")
        self.assertEqual(updated["id"], 10)

        # 2. Verify database persistence in both users and students tables
        with get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT name, phone, role FROM users WHERE id = 10")
            u_row = c.fetchone()
            self.assertEqual(u_row["name"], "Venu Gopal Sharma")
            self.assertEqual(u_row["phone"], "+91 98765 43210")
            self.assertEqual(u_row["role"], "STUDENT")

            c.execute("SELECT phone, usn FROM students WHERE user_id = 10")
            s_row = c.fetchone()
            self.assertEqual(s_row["phone"], "+91 98765 43210")
            self.assertEqual(s_row["usn"], "4SJ23AD001")

        # 3. Input validation: Empty name rejected
        blank_name_res = self.app.put("/api/profile", headers={"Authorization": f"Bearer {student_token}"}, json={
            "name": "   "
        })
        self.assertEqual(blank_name_res.status_code, 400)
        self.assertIn("Full Name cannot be empty", blank_name_res.get_json()["error"])

        # 4. Input validation: Invalid phone format rejected
        bad_phone_res = self.app.put("/api/profile", headers={"Authorization": f"Bearer {student_token}"}, json={
            "phone": "invalid-alphabetic-phone"
        })
        self.assertEqual(bad_phone_res.status_code, 400)
        self.assertIn("valid phone number", bad_phone_res.get_json()["error"])

    def test_12_put_change_password_full_validation_flow(self):
        """Test PUT /api/profile/change-password endpoint validation, hashing, and re-authentication."""
        student_token = create_token(10, "STUDENT", "venu.aids@college.edu", "Venu Gopal Sharma")
        # Current password for Venu after test_07 is 'VenuSecure@2026'

        # 1. Missing password fields
        missing_res = self.app.put("/api/profile/change-password", headers={"Authorization": f"Bearer {student_token}"}, json={
            "currentPassword": "",
            "newPassword": "ValidPass@2026"
        })
        self.assertEqual(missing_res.status_code, 400)

        # 2. Incorrect current password
        wrong_pwd_res = self.app.put("/api/profile/change-password", headers={"Authorization": f"Bearer {student_token}"}, json={
            "currentPassword": "WrongPassword@123",
            "newPassword": "NewStrongPass@2026",
            "confirmPassword": "NewStrongPass@2026"
        })
        self.assertEqual(wrong_pwd_res.status_code, 400)
        self.assertEqual(wrong_pwd_res.get_json()["error"], "Current password is incorrect.")

        # 3. Weak new password (violates institutional policy: needs uppercase, lowercase, digit, special char, 8+ chars)
        weak_pwd_res = self.app.put("/api/profile/change-password", headers={"Authorization": f"Bearer {student_token}"}, json={
            "currentPassword": "VenuSecure@2026",
            "newPassword": "weakpassword",
            "confirmPassword": "weakpassword"
        })
        self.assertEqual(weak_pwd_res.status_code, 400)
        self.assertIn("Password must", weak_pwd_res.get_json()["error"])

        # 4. New password and confirm password mismatch
        mismatch_res = self.app.put("/api/profile/change-password", headers={"Authorization": f"Bearer {student_token}"}, json={
            "currentPassword": "VenuSecure@2026",
            "newPassword": "NewStrongPass@2026",
            "confirmPassword": "DifferentPassword@2026"
        })
        self.assertEqual(mismatch_res.status_code, 400)
        self.assertEqual(mismatch_res.get_json()["error"], "New passwords do not match.")

        # 5. Successful password change
        succ_res = self.app.put("/api/profile/change-password", headers={"Authorization": f"Bearer {student_token}"}, json={
            "currentPassword": "VenuSecure@2026",
            "newPassword": "VenuUpdated@2026!",
            "confirmPassword": "VenuUpdated@2026!"
        })
        self.assertEqual(succ_res.status_code, 200)
        self.assertTrue(succ_res.get_json()["success"])
        self.assertEqual(succ_res.get_json()["message"], "Password changed successfully.")

        # 6. Verify old password no longer works
        old_login = self.app.post("/api/auth/login", json={
            "email": "venu.aids@college.edu",
            "password": "VenuSecure@2026"
        })
        self.assertEqual(old_login.status_code, 401)

        # 7. Verify new password successfully authenticates
        new_login = self.app.post("/api/auth/login", json={
            "email": "venu.aids@college.edu",
            "password": "VenuUpdated@2026!"
        })
        self.assertEqual(new_login.status_code, 200)
        self.assertIn("token", new_login.get_json())

        # 8. Verify password hash in DB is hashed and never plain text
        with get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT password_hash FROM users WHERE id = 10")
            stored_hash = c.fetchone()["password_hash"]
            self.assertNotEqual(stored_hash, "VenuUpdated@2026!")
            self.assertTrue(verify_password("VenuUpdated@2026!", stored_hash))

    def test_13_profile_avatar_and_security_activity(self):
        """Test profile avatar direct file upload, extra student records, and security audit log endpoint."""
        import io
        student_token = create_token(10, "STUDENT", "venu.aids@college.edu", "Venu Gopal Sharma")

        # 1. Test direct avatar image upload
        fake_png = io.BytesIO(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4")
        upload_res = self.app.post("/api/profile/avatar", headers={"Authorization": f"Bearer {student_token}"}, data={
            "avatar": (fake_png, "my_avatar.png")
        }, content_type="multipart/form-data")
        self.assertEqual(upload_res.status_code, 200)
        u_data = upload_res.get_json()
        self.assertTrue(u_data["success"])
        self.assertIn("avatar_url", u_data)
        self.assertTrue(u_data["avatar_url"].startswith("/api/files/avatar_10_"))

        # 2. Test enhanced personal profile details (emergency_contact, blood_group, bio)
        enh_res = self.app.put("/api/profile", headers={"Authorization": f"Bearer {student_token}"}, json={
            "emergency_contact": "+91 98888 12345",
            "blood_group": "O+",
            "bio": "Honors student specializing in Deep Learning & NLP."
        })
        self.assertEqual(enh_res.status_code, 200)
        enh_profile = enh_res.get_json()["profile"]
        self.assertEqual(enh_profile["emergency_contact"], "+91 98888 12345")
        self.assertEqual(enh_profile["blood_group"], "O+")
        self.assertEqual(enh_profile["bio"], "Honors student specializing in Deep Learning & NLP.")

        # 3. Test security activity log retrieval
        act_res = self.app.get("/api/profile/activity", headers={"Authorization": f"Bearer {student_token}"})
        self.assertEqual(act_res.status_code, 200)
        act_data = act_res.get_json()
        self.assertTrue(act_data["success"])
        self.assertIsInstance(act_data["activity"], list)
        self.assertGreater(len(act_data["activity"]), 0)
        # Verify action types present in student audit log
        actions = [a["action"] for a in act_data["activity"]]
        self.assertTrue(any(a in ("UPDATE_PROFILE", "UPDATE_AVATAR", "CHANGE_PASSWORD") for a in actions))


if __name__ == "__main__":
    unittest.main()


