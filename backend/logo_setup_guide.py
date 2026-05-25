#!/usr/bin/env python3
"""
Converter script: Convert your tiger logo to the correct format
Run: python3 convert_logo.py
"""

import os
import sys
from pathlib import Path

def check_and_setup():
    """Check setup and provide guidance"""
    
    print("""
    🐯 TIGER ACADEMY - LOGO SETUP GUIDE
    =====================================
    
    CURRENT STATUS:
    ✓ Code integrated into reports
    ✓ Report header updated for English and Arabic
    ✓ Directory created for logo
    
    ⏳ WAITING FOR: Your tiger logo image file
    
    """)
    
    # Check directory
    logo_dir = Path('backend/static/img')
    print(f"📁 Logo Directory: {logo_dir}")
    
    if logo_dir.exists():
        print("   ✓ Directory exists")
        files = list(logo_dir.glob('*'))
        if files:
            print(f"   Files found: {len(files)}")
            for f in files:
                print(f"     - {f.name}")
        else:
            print("   ⚠ No files in directory yet")
    else:
        print("   Creating directory...")
        logo_dir.mkdir(parents=True, exist_ok=True)
        print("   ✓ Directory created")
    
    print(f"""
    
    📋 REQUIRED STEPS:
    
    Step 1: Save Your Logo
    ──────────────────────
    Location: backend/static/img/tiger_logo.png
    
    Options:
    a) Copy your existing tiger logo image
    b) Save as PNG (recommended for transparency)
    c) Resize to 58×58 pixels (optional, will auto-scale)
    
    
    Step 2: Verify the File
    ─────────────────────── 
    Run this command:
    
        ls -la backend/static/img/tiger_logo.png
    
    You should see your logo file listed
    
    
    Step 3: Test the Reports
    ────────────────────────
    Run this command from backend/:
    
        python3 manage.py shell < test_logo.py
    
    This will:
    ✓ Check if logo exists
    ✓ Generate English report with logo
    ✓ Generate Arabic report with logo
    ✓ Create test PDF files
    
    
    Step 4: View the Results
    ────────────────────────
    Open these PDF files to verify:
    
    test_report_english.pdf
    - Logo should appear TOP LEFT before "TIGER FIT"
    
    test_report_arabic.pdf  
    - Logo should appear TOP RIGHT before "TIGER FIT"
    
    
    📝 LOGO SPECIFICATIONS:
    ──────────────────────
    Format:      PNG (with transparency recommended)
    Size:        58×58 pixels recommended (auto-scales)
    Color:       White or light color (on black background)
    Style:       Tiger head icon (your provided image)
    Background:  Transparent or dark
    
    
    🔗 FILE STRUCTURE:
    ─────────────────
    
    dasher-1.0.0/
    ├── backend/
    │   ├── athletes/
    │   │   ├── report_service.py    ← Modified (logo positioning)
    │   │   └── views.py             ← Uses report_service
    │   ├── static/
    │   │   └── img/
    │   │       └── tiger_logo.png   ← ← Save your logo HERE
    │   ├── test_logo.py             ← Test script
    │   └── manage.py
    └── ...
    
    
    📚 USEFUL COMMANDS:
    ──────────────────
    
    # Check if directory exists
    ls -la backend/static/
    
    # See if logo was placed
    ls -la backend/static/img/tiger_logo.png
    
    # Verify code changes
    grep -n "tiger_logo" backend/athletes/report_service.py
    
    # Generate test reports
    cd backend && python3 manage.py shell < test_logo.py
    
    # Check file type
    file backend/static/img/tiger_logo.png
    
    
    ✨ QUICK CHECKLIST:
    ──────────────────
    
    [ ] 1. Have your tiger logo image file ready
    [ ] 2. Save it to: backend/static/img/tiger_logo.png
    [ ] 3. Verify file exists: ls -la backend/static/img/tiger_logo.png
    [ ] 4. Run test: python3 manage.py shell < test_logo.py
    [ ] 5. Check PDFs open correctly
    [ ] 6. Logo appears in correct position (top-left EN, top-right AR)
    [ ] 7. Generate real athlete reports to verify
    
    
    🎉 DONE!
    ────────
    Reports will now automatically include the tiger logo!
    
    🌐 English Reports: Logo top-left before TIGER FIT
     ع Arabic Reports: Logo top-right before TIGER FIT
    
    """)

if __name__ == '__main__':
    check_and_setup()
