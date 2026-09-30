@echo off
title SmartAttend - Student Attendance Management System
echo ==============================================================
echo       SmartAttend — Student Attendance Management System
echo       "Track Attendance. Stay Eligible. Stay Informed."
echo ==============================================================
echo.

cd /d "%~dp0"

echo [1/3] Checking Python dependencies...
python -m pip install -r requirements.txt --quiet

echo [2/3] Verifying database and sample seed data...
python seed_data.py

echo.
echo [3/3] Launching SmartAttend College ERP Server...
echo Server running at: http://127.0.0.1:5000
echo.
echo Demo Accounts:
echo   - Student:  student@college.edu  / password123
echo   - Faculty:  faculty@college.edu  / password123
echo   - HOD:      hod@college.edu      / password123
echo   - Admin:    admin@college.edu    / password123
echo.
echo Opening browser...
start http://127.0.0.1:5000

python app.py
pause
