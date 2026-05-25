#!/usr/bin/env python3
"""
Test script to verify tiger logo setup in reports
Run from: python3 manage.py shell < test_logo.py
"""

from athletes.models import AthleteInfo
from athletes.report_service import ReportGeneratorService
import os
from django.conf import settings

print("🐯 Tiger Academy Logo - Report Test")
print("=" * 50)

# Get first athlete
athlete = AthleteInfo.objects.first()

if not athlete:
    print("❌ No athletes found in database")
    print("   Create an athlete first!")
else:
    print(f"✓ Using athlete: {athlete.name}")
    
    try:
        # Gather report data
        data = ReportGeneratorService.get_weekly_data(athlete)
        static_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static')
        data['static_path'] = static_path
        
        logo_path = os.path.join(static_path, 'img', 'tiger_logo.png')
        
        print(f"\n📁 Logo path: {logo_path}")
        if os.path.exists(logo_path):
            print("   ✓ Logo file exists!")
        else:
            print("   ⚠ Logo file not found")
            print(f"   → Please save your logo to: {logo_path}")
        
        # Generate English report
        print("\n📄 Generating English report...")
        pdf_en = ReportGeneratorService.generate_pdf(data, lang='en')
        output_en = 'test_report_english.pdf'
        with open(output_en, 'wb') as f:
            f.write(pdf_en)
        print(f"   ✓ Created: {output_en}")
        
        # Generate Arabic report
        print("📄 Generating Arabic report...")
        pdf_ar = ReportGeneratorService.generate_pdf(data, lang='ar')
        output_ar = 'test_report_arabic.pdf'
        with open(output_ar, 'wb') as f:
            f.write(pdf_ar)
        print(f"   ✓ Created: {output_ar}")
        
        print("\n" + "=" * 50)
        print("✅ Test Complete!")
        print("\n📋 Check the generated PDFs:")
        print(f"   - {output_en}")
        print(f"   - {output_ar}")
        print("\n✓ Logo should appear:")
        print("   - English: Top left before 'TIGER FIT'")
        print("   - Arabic: Top right before 'TIGER FIT'")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
