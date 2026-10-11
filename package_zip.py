"""
SmartAttend - Package Zip Utility
Creates a clean, portable zip archive of the smartattend project.
"""
import os
import zipfile

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOADS_ZIP = r"C:\Users\VENU\Downloads\smartattend.zip"
SCRATCH_ZIP = os.path.join(os.path.dirname(PROJECT_DIR), "smartattend.zip")
DESKTOP_ZIP = r"C:\Users\VENU\OneDrive\Desktop\smartattend.zip"
ARTIFACT_ZIP = r"C:\Users\VENU\.gemini\antigravity\brain\ef1ba3b6-a050-48eb-8e98-b76366f452a5\smartattend.zip"

EXCLUDE_DIRS = {".git", "__pycache__", ".vscode", ".idea"}
EXCLUDE_EXTS = {".pyc", ".log"}
EXCLUDE_FILES = {"smartattend.zip"}


def make_zip():
    print(f"Archiving SmartAttend...")
    import shutil
    with zipfile.ZipFile(DOWNLOADS_ZIP, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(PROJECT_DIR):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for file in files:
                if any(file.endswith(ext) for ext in EXCLUDE_EXTS) or file in EXCLUDE_FILES:
                    continue
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, PROJECT_DIR)
                zipf.write(full_path, os.path.join("smartattend", rel_path))
    
    for dest in [SCRATCH_ZIP, DESKTOP_ZIP, ARTIFACT_ZIP]:
        dest_dir = os.path.dirname(dest)
        if os.path.exists(dest_dir):
            shutil.copy2(DOWNLOADS_ZIP, dest)
            print(f"Copied archive to: {dest}")

    print("Archive created successfully in Downloads:", DOWNLOADS_ZIP)


if __name__ == "__main__":
    make_zip()
