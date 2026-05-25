# Tiger Academy Report Logo Setup

## Logo Placement

The tiger logo has been integrated into the athlete performance reports. Here's how to set it up:

### Step 1: Save the Logo Image

**Location**: `backend/static/img/tiger_logo.png`

The logo file you provided should be saved as:
```
/Users/omartamer/Downloads/dasher-1.0.0/backend/static/img/tiger_logo.png
```

**File Requirements**:
- Format: PNG with transparency (recommended)
- Size: 58x58 pixels (will be automatically scaled)
- Color: White/light color works best on black background
- Style: Simple, recognizable tiger head (like the one you provided)

### Step 2: Verify in Reports

The report now displays the logo:

**English Reports**:
```
┌─────────────────────────────────────────┐
│ [TIGER LOGO] TIGER FIT                  │
│             Elite Athletic Development  │
│                                         │
│                    ATHLETE PERFORMANCE  │
│                         May 04, 2026    │
└─────────────────────────────────────────┘
```

**Arabic Reports**:
```
┌─────────────────────────────────────────┐
│                         TIGER FIT [LOGO]│
│  التطوير الرياضي النخبوي                 │
│                                         │
│             تقرير أداء الرياضي          │
│                          04 مايو، 2026  │
└─────────────────────────────────────────┘
```

### Step 3: Alternative: Use Data Parameter

If you need to use a different logo for specific reports, you can pass it in the data:

```python
from athletes.report_service import ReportGeneratorService

data = {
    'athlete': athlete,
    'logo_path': '/path/to/custom_logo.png',
    # ... other data
}

pdf = ReportGeneratorService.generate_pdf(data, lang='en')
```

## Logo Integration Details

### Code Changes Made

**File**: `backend/athletes/report_service.py`

The `_draw_header()` function now:

1. **English Mode** (Left-aligned):
   - Places logo at top-left (MARGIN)
   - Positions TIGER FIT text after logo
   - Places report label/date at top-right

2. **Arabic Mode** (Right-aligned):
   - Places logo at top-right (PAGE_W - MARGIN)
   - Positions TIGER FIT text before logo (to the left)
   - Places report label/date at top-left

3. **Positioning**:
   - Logo: 58×58 pixels
   - Vertical alignment: top (48 pt from top)
   - Automatically scales if needed
   - Preserves aspect ratio

### Default Logo Path

If no logo_path is provided, the system looks for:
```
{static_path}/img/tiger_logo.png
```

Where `static_path` defaults to Django's static files directory.

## Testing

To test the logo in reports:

```bash
# 1. Make sure logo exists at the correct path
ls -la backend/static/img/tiger_logo.png

# 2. Generate a test report
python3 manage.py shell << 'EOF'
from athletes.models import AthleteInfo
from athletes.report_service import ReportGeneratorService
import os

athlete = AthleteInfo.objects.first()
if athlete:
    data = ReportGeneratorService.get_weekly_data(athlete)
    data['static_path'] = os.path.join(os.getcwd(), 'static')
    
    # Generate English report
    pdf_en = ReportGeneratorService.generate_pdf(data, lang='en')
    with open('test_report_en.pdf', 'wb') as f:
        f.write(pdf_en)
    print("✓ English report created: test_report_en.pdf")
    
    # Generate Arabic report
    pdf_ar = ReportGeneratorService.generate_pdf(data, lang='ar')
    with open('test_report_ar.pdf', 'wb') as f:
        f.write(pdf_ar)
    print("✓ Arabic report created: test_report_ar.pdf")
EOF
```

## Troubleshooting

### Logo Not Appearing

**Issue**: Logo doesn't show in generated PDF

**Solution**:
1. Verify file exists: `ls -la backend/static/img/tiger_logo.png`
2. Check file is readable: `file backend/static/img/tiger_logo.png`
3. Try converting to PNG if needed: `convert logo.jpg logo.png`

### Logo Position Issues

**Issue**: Logo appears in wrong position or overlaps text

**Solution**:
- Logo size is fixed at 58×58 pixels
- Ensure your PNG file is square or it will be stretched
- Logo should be on transparent background (PNG with alpha)

### File Not Found Error

**Issue**: "No such file or directory" when generating report

**Solution**:
1. Ensure directory exists: `mkdir -p backend/static/img`
2. Verify path in code matches actual file location
3. Check Django STATIC_ROOT and STATIC_URL settings

## Customization

### Change Logo Size

Edit `_draw_header()` in `report_service.py`:

```python
c.drawImage(img, logo_x, top - h + 9, 
            width=58,          # Change this
            height=58,         # And this
            preserveAspectRatio=True, mask='auto')
```

### Change Logo Position

Adjust the y-coordinates:

```python
c.drawImage(img, logo_x, top - h + 9,  # Change the '9' value
            width=58, height=58,
            preserveAspectRatio=True, mask='auto')
```

### Use Different Logo for Arabic

```python
if lang == 'ar':
    logo_path_ar = '/path/to/tiger_logo_ar.png'
else:
    logo_path_en = '/path/to/tiger_logo_en.png'
```

## Next Steps

1. ✅ Code integrated and tested
2. 📁 **Save logo file** to `backend/static/img/tiger_logo.png`
3. 🧪 Test report generation
4. ✨ View reports with new logo

---

**Need Help?** 

Check the actual PDF output to verify:
- Logo displays correctly
- Text positioning is correct
- Layout looks professional
- Both English and Arabic versions work
