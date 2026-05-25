"""
Tiger Academy – ReportGeneratorService
=======================================
Generates pixel-perfect, two-page athlete performance PDFs in English and Arabic
using ReportLab canvas (no external HTML renderer required).

Layout mirrors the Tiger Academy wkhtmltopdf design:
  Page 1 – Header · Athlete Banner · Athlete Info + Medical · Attendance + Ratings
  Page 2 – Header · Targets & Strategy · Assessment Table · Sport/Records/Events · Weekly Summary

Drop-in replacement for the original service: all public methods, signatures,
and data contracts are preserved.  Only generate_pdf() is rewritten.

Dependencies
------------
    pip install reportlab arabic-reshaper python-bidi Pillow
"""

from __future__ import annotations

import io
import os
import math
import logging
from datetime import datetime, timedelta
from typing import Any

import arabic_reshaper
from bidi.algorithm import get_display

from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ── Django imports (unchanged from original) ────────────────────────────────
try:
    from django.utils import timezone
    from .models import AthleteInfo, AttendanceRecord, Fitness, Swimming
    from django.db.models import Avg
    _DJANGO = True
except ImportError:                          # allow standalone / test usage
    _DJANGO = False
    timezone = None

logger = logging.getLogger(__name__)

# ── Brand palette ────────────────────────────────────────────────────────────
C_BLACK   = colors.HexColor('#0a0a0a')
C_DARK    = colors.HexColor('#1a1a1a')
C_MID     = colors.HexColor('#4a4a4a')
C_LGRAY   = colors.HexColor('#f5f5f5')
C_BORDER  = colors.HexColor('#dddddd')
C_ACCENT  = colors.HexColor('#c8a94b')
C_ACCENT2 = colors.HexColor('#e8c870')
C_WHITE   = colors.white
C_RED     = colors.HexColor('#c0392b')
C_GREEN   = colors.HexColor('#27ae60')
C_YELLOW  = colors.HexColor('#f39c12')
C_BLUE    = colors.HexColor('#0c5460')

# Badge palette  (bg, text)
BADGE = {
    'green':  (colors.HexColor('#d4edda'), colors.HexColor('#155724')),
    'red':    (colors.HexColor('#f8d7da'), colors.HexColor('#721c24')),
    'yellow': (colors.HexColor('#fff3cd'), colors.HexColor('#856404')),
    'blue':   (colors.HexColor('#d1ecf1'), colors.HexColor('#0c5460')),
}

PAGE_W, PAGE_H = A4          # 595.27 × 841.89 pt
MARGIN = 28                  # left / right margin in pt


# ════════════════════════════════════════════════════════════════════════════
#  Low-level canvas helpers
# ════════════════════════════════════════════════════════════════════════════

def _rect(c: rl_canvas.Canvas, x, y, w, h, fill_color=None, stroke_color=None, lw=0):
    """Draw a filled/stroked rectangle."""
    c.saveState()
    if fill_color:
        c.setFillColor(fill_color)
    if stroke_color:
        c.setStrokeColor(stroke_color)
        c.setLineWidth(lw or 0.5)
    else:
        c.setLineWidth(0)
    c.rect(x, y, w, h,
           fill=1 if fill_color else 0,
           stroke=1 if stroke_color else 0)
    c.restoreState()


def _text(c: rl_canvas.Canvas, x, y, txt, font, size, color=C_DARK, align='left', max_w=None):
    """Draw a single line of text. align: 'left'|'center'|'right'."""
    c.saveState()
    c.setFont(font, size)
    c.setFillColor(color)
    txt = str(txt)
    if max_w:
        # Simple truncation guard
        while c.stringWidth(txt, font, size) > max_w and len(txt) > 4:
            txt = txt[:-1]
    if align == 'center':
        c.drawCentredString(x, y, txt)
    elif align == 'right':
        c.drawRightString(x, y, txt)
    else:
        c.drawString(x, y, txt)
    c.restoreState()


def _wrap_text(c: rl_canvas.Canvas, x, y, txt, font, size, color, max_w, line_h):
    """
    Draw multi-line wrapped text.  Returns the y position AFTER the last line.
    """
    c.saveState()
    c.setFont(font, size)
    c.setFillColor(color)
    words = txt.split()
    line = ''
    for word in words:
        test = (line + ' ' + word).strip()
        if c.stringWidth(test, font, size) <= max_w:
            line = test
        else:
            if line:
                c.drawString(x, y, line)
                y -= line_h
            line = word
    if line:
        c.drawString(x, y, line)
        y -= line_h
    c.restoreState()
    return y


def _progress_bar(c, x, y, w, h, pct, fill_color=C_ACCENT):
    """Draw a progress bar background + fill."""
    _rect(c, x, y, w, h, fill_color=colors.HexColor('#e0e0e0'))
    _rect(c, x, y, w * min(pct / 100, 1.0), h, fill_color=fill_color)


def _badge(c, x, y, label, style='green', font='Helvetica-Bold', font_size=7):
    """Draw a small coloured badge pill."""
    bg, fg = BADGE[style]
    pad_x, pad_y, r_h = 6, 3, 13
    w = c.stringWidth(label, font, font_size) + pad_x * 2
    _rect(c, x, y - r_h + pad_y, w, r_h, fill_color=bg)
    _text(c, x + pad_x, y - r_h + pad_y + 3, label, font, font_size, color=fg)
    return w   # caller can advance x if needed


def _donut(c, cx, cy, r, pct, stroke_w=9):
    """Draw a simple donut / ring chart."""
    # Background ring
    c.saveState()
    c.setStrokeColor(colors.HexColor('#e0e0e0'))
    c.setLineWidth(stroke_w)
    c.circle(cx, cy, r, stroke=1, fill=0)
    # Filled arc
    c.setStrokeColor(C_ACCENT)
    # Normalize percentage and guard against edge cases where angle==0 or 360
    try:
        pct_val = float(pct or 0.0)
    except Exception:
        pct_val = 0.0
    pct_val = max(0.0, min(pct_val, 100.0))

    # If nothing to draw, skip arc to avoid division-by-zero inside ReportLab
    if pct_val <= 0.0:
        # nothing to fill
        pass
    elif pct_val >= 100.0:
        # draw a full accent circle (stroke-only) for 100%
        c.setLineWidth(stroke_w)
        c.circle(cx, cy, r, stroke=1, fill=0)
    else:
        angle = 360.0 * pct_val / 100.0
        from reportlab.graphics.shapes import ArcPath
        # Use beginPath arc approach
        c.setLineCap(1)         # round caps
        # ReportLab arc: angles in degrees, counter-clockwise from 3 o'clock
        start_deg = 90          # 12 o'clock
        c.arc(cx - r, cy - r, cx + r, cy + r, startAng=start_deg, extent=-angle)
    c.restoreState()
    # Centre label
    _text(c, cx, cy - 5, f'{int(pct_val)}%', 'Helvetica-Bold', 11, C_DARK, align='center')


# ════════════════════════════════════════════════════════════════════════════
#  Shared page sections
# ════════════════════════════════════════════════════════════════════════════

def _draw_header(c, data, lang, logo_path=None):
    """
    Black header bar with logo, academy name, and report date.
    Returns the y coordinate immediately below the header.
    
    Logo positioning:
    - English: Top left before TIGER FIT
    - Arabic: Top right before TIGER FIT
    """
    h = 82          # header height
    top = PAGE_H
    _rect(c, 0, top - h, PAGE_W, h, fill_color=C_BLACK)
    # Gold accent line at bottom
    _rect(c, 0, top - h, PAGE_W, 3, fill_color=C_ACCENT)

    fn_bold = _font_bold(lang)
    fn_reg  = _font_reg(lang)
    tagline = 'Elite Athletic Development' if lang == 'en' else 'التطوير الرياضي النخبوي'

    # Logo positioning varies by language
    if lang == 'ar':
        # Arabic: Logo on top right, text on right below logo
        logo_x = PAGE_W - MARGIN - 58  # Right-aligned logo
        if logo_path and os.path.exists(logo_path):
            try:
                img = ImageReader(logo_path)
                c.drawImage(img, logo_x, top - h + 9, width=58, height=58,
                            preserveAspectRatio=True, mask='auto')
            except Exception:
                pass
        
        # TIGER FIT and tagline on the left of logo
        text_x = PAGE_W - MARGIN - 68 - 120
        _text(c, text_x, top - h + 46, _r('TIGER FIT', lang),
              fn_bold, 20, C_WHITE, align='left')
        _text(c, text_x, top - h + 28, _r(tagline, lang),
              fn_reg, 8, C_ACCENT, align='left')
    else:
        # English: Logo on top left, text after logo
        logo_x = MARGIN
        if logo_path and os.path.exists(logo_path):
            try:
                img = ImageReader(logo_path)
                c.drawImage(img, logo_x, top - h + 9, width=58, height=58,
                            preserveAspectRatio=True, mask='auto')
                logo_x += 68
            except Exception:
                pass
        
        _text(c, logo_x, top - h + 48, 'TIGER FIT', fn_bold, 19, C_WHITE)
        _text(c, logo_x, top - h + 31, tagline, fn_reg, 8, C_ACCENT)
    
    # Right-side meta block (report date and label)
    report_lbl  = 'ATHLETE PERFORMANCE REPORT' if lang == 'en' else 'تقرير أداء الرياضي'
    report_date = data.get('report_date', datetime.today().strftime('%B %d, %Y'))

    if lang == 'ar':
        rx = MARGIN
        al = 'left'
    else:
        rx = PAGE_W - MARGIN
        al = 'right'

    _text(c, rx, top - h + 57, _r(report_lbl, lang),  fn_reg,  7, colors.HexColor('#888888'), align=al)
    _text(c, rx, top - h + 43, _r(report_date, lang), fn_bold, 12, C_ACCENT,                  align=al)

    return top - h   # y of bottom of header (= top of accent line)


def _draw_athlete_banner(c, data, lang, top_y):
    """
    Dark gradient banner with athlete name, sport tag, and 4 quick stats.
    Returns y below the banner.
    """
    h = 58
    _rect(c, 0, top_y - h, PAGE_W, h, fill_color=C_DARK)
    # Gold line at bottom
    _rect(c, 0, top_y - h, PAGE_W, 2, fill_color=C_ACCENT)

    fn_bold = _font_bold(lang)
    fn_reg  = _font_reg(lang)

    athlete   = data.get('athlete')
    name      = getattr(athlete, 'name', 'Athlete Name') if athlete else 'Athlete Name'
    sport_tag = data.get('sport_tag', 'Athletics · Sprint Specialist')

    if lang == 'ar':
        # Name on the right
        _text(c, PAGE_W - MARGIN, top_y - 22, _r(name, lang), fn_bold, 17, C_WHITE, align='right')
        _text(c, PAGE_W - MARGIN, top_y - 36, _r(sport_tag, lang), fn_reg, 8, C_BLACK, align='right')
        # sport tag pill
        tag_w = c.stringWidth(_r(sport_tag, lang), fn_reg, 8) + 16
        _rect(c, PAGE_W - MARGIN - tag_w, top_y - 43, tag_w, 13, fill_color=C_ACCENT)
        _text(c, PAGE_W - MARGIN - tag_w + 8, top_y - 41 + 2,
              _r(sport_tag, lang), fn_reg, 7.5, C_BLACK)
    else:
        _text(c, MARGIN, top_y - 22, name, fn_bold, 17, C_WHITE)
        # sport tag pill
        tag_w = c.stringWidth(sport_tag, 'Helvetica', 7.5) + 16
        _rect(c, MARGIN, top_y - 41, tag_w, 13, fill_color=C_ACCENT)
        _text(c, MARGIN + 8, top_y - 41 + 3, sport_tag, 'Helvetica', 7.5, C_BLACK)

    # Quick stats  (4 boxes, right-aligned cluster)
    stats = [
        (str(data.get('avg_rating', '8.7')),   'Session Rating'   if lang == 'en' else 'تقييم الجلسة'),
        (f"{data.get('attendance_rate', 0):.0f}%", 'Attendance'  if lang == 'en' else 'نسبة الحضور'),
        (str(data.get('sessions_per_week', data.get('sessions_count', 4))),
                                                'Sessions/Wk'      if lang == 'en' else 'جلسات/أسبوع'),
        (data.get('program_phase', 'Week 14'),  'Program Phase'   if lang == 'en' else 'مرحلة البرنامج'),
    ]
    box_w   = 72
    gap     = 6
    total_w = len(stats) * box_w + (len(stats) - 1) * gap
    sx      = MARGIN if lang == 'ar' else PAGE_W - MARGIN - total_w

    for val, lbl in stats:
        _text(c, sx + box_w / 2, top_y - 22, _r(val, lang), fn_bold, 15, C_ACCENT, align='center')
        _text(c, sx + box_w / 2, top_y - 34, _r(lbl, lang), fn_reg,  7,  colors.HexColor('#999999'), align='center')
        sx += box_w + gap

    return top_y - h


def _draw_section_title(c, x, y, w, title, lang):
    """Dark bar with left gold accent stripe. Returns y below it."""
    h = 18
    _rect(c, x, y - h, w, h, fill_color=C_DARK)
    stripe_x = x if lang == 'en' else x + w - 4
    _rect(c, stripe_x, y - h, 4, h, fill_color=C_ACCENT)
    fn = _font_bold(lang)
    tx = x + 10 if lang == 'en' else x + w - 10
    al = 'left' if lang == 'en' else 'right'
    _text(c, tx, y - h + 5, _r(title, lang), fn, 8, C_WHITE, align=al)
    return y - h


def _draw_footer(c, data, lang, page_num, total_pages):
    """Black footer bar. Returns nothing."""
    h = 24
    _rect(c, 0, 0, PAGE_W, h, fill_color=C_BLACK)
    _rect(c, 0, h, PAGE_W, 2, fill_color=C_ACCENT)
    fn  = _font_reg(lang)
    fnb = _font_bold(lang)
    academy = 'Tiger Academy · Elite Athletic Development' \
              if lang == 'en' else \
              'أكاديمية النمر · التطوير الرياضي النخبوي '
    _text(c, MARGIN, 8, _r(academy, lang),   fn,  7, colors.HexColor('#666666'))


# ════════════════════════════════════════════════════════════════════════════
#  Page 1 content
# ════════════════════════════════════════════════════════════════════════════

def _draw_page1(c, data, lang, logo_path=None):
    c.setFont('Helvetica', 10)

    y = _draw_header(c, data, lang, logo_path)
    y = _draw_athlete_banner(c, data, lang, y)

    fn_bold = _font_bold(lang)
    fn_reg  = _font_reg(lang)

    # ── SECTION: Athlete Information & Medical Profile ───────────────────────
    y -= 10
    body_w = PAGE_W - 2 * MARGIN
    col_w  = (body_w - 12) / 2

    y = _draw_section_title(c, MARGIN, y, body_w,
                            'Athlete Information & Medical Profile' if lang == 'en'
                            else 'معلومات الرياضي والملف الطبي', lang)
    y -= 8

    # Left column: info table card
    card_h   = 148
    card_x   = MARGIN
    card_y   = y - card_h
    _rect(c, card_x, card_y, col_w, card_h, fill_color=C_LGRAY,
          stroke_color=C_BORDER, lw=0.5)

    athlete = data.get('athlete')
    def av(attr, fallback='—'):
        return str(getattr(athlete, attr, fallback)) if athlete else fallback

    info_rows_en = [
        ('Full Name',     av('name')),
        ('Age',           av('age') + ' Years'),
        ('Gender',        av('gender')),
        ('Date of Birth', av('date_of_birth', '—')),
        ('Height',        av('height', '—')),
        ('Weight',        av('weight', '—')),
        ('Body Type',     av('body_type', '—')),
        ('BMI',           av('bmi', '—')),
        ('Academy Since', av('academy_since', '—')),
    ]
    info_rows_ar = [
        ('الاسم الكامل',      av('name')),
        ('العمر',             av('age') + ' سنة'),
        ('الجنس',            av('gender')),
        ('تاريخ الميلاد',    av('date_of_birth', '—')),
        ('الطول',            av('height', '—')),
        ('الوزن',            av('weight', '—')),
        ('نوع الجسم',        av('body_type', '—')),
        ('مؤشر كتلة الجسم', av('bmi', '—')),
        ('عضو منذ',          av('academy_since', '—')),
    ]
    info_rows = info_rows_ar if lang == 'ar' else info_rows_en

    row_h  = card_h / len(info_rows)
    for i, (lbl, val) in enumerate(info_rows):
        ry = card_y + card_h - (i + 1) * row_h
        if i < len(info_rows) - 1:
            _rect(c, card_x + 4, ry, col_w - 8, 0.5, fill_color=C_BORDER)
        if lang == 'ar':
            _text(c, card_x + col_w - 8, ry + row_h * 0.3,
                  _r(lbl, lang), fn_reg, 8, C_MID, align='right')
            _text(c, card_x + 8, ry + row_h * 0.3,
                  _r(val, lang), fn_bold, 8.5, C_DARK)
        else:
            _text(c, card_x + 8, ry + row_h * 0.3,
                  lbl, 'Helvetica', 7.5, C_MID)
            _text(c, card_x + col_w - 8, ry + row_h * 0.3,
                  val, fn_bold, 8.5, C_DARK, align='right')

    # Right column: injuries + strengths + weaknesses
    rc_x = card_x + col_w + 12
    rc_y = y

    # Injuries card
    inj_h = 60
    _rect(c, rc_x, rc_y - inj_h, col_w, inj_h, fill_color=C_LGRAY,
          stroke_color=C_BORDER, lw=0.5)
    inj_title = 'Active Injuries / Medical Notes' if lang == 'en' else 'الإصابات النشطة / ملاحظات طبية'
    _text(c, rc_x + 8, rc_y - 14, _r(inj_title, lang), fn_bold, 7.5,
          colors.HexColor('#c0392b'), align='left' if lang == 'en' else 'left')
    injuries = data.get('injuries', ['No active injuries reported'])
    iy = rc_y - 26
    for inj in injuries[:3]:
        # red left-border tag
        _rect(c, rc_x + 8, iy - 4, 3, 11, fill_color=C_RED)
        _rect(c, rc_x + 11, iy - 4,
              c.stringWidth(_r(inj, lang), fn_reg, 8) + 12, 11,
              fill_color=colors.HexColor('#f8d7da'))
        _text(c, rc_x + 16, iy, _r(inj, lang), fn_reg, 8,
              colors.HexColor('#721c24'))
        iy -= 14

    # Strengths card
    sw_y = rc_y - inj_h - 6
    sw_h = 44
    _rect(c, rc_x, sw_y - sw_h, col_w, sw_h, fill_color=C_LGRAY,
          stroke_color=C_BORDER, lw=0.5)
    s_title = 'Strengths' if lang == 'en' else 'نقاط القوة'
    _text(c, rc_x + 8, sw_y - 13, _r(s_title, lang), fn_bold, 7.5,
          colors.HexColor('#155724'))
    strengths = data.get('strengths', ['Explosive Start', 'Stride Frequency'])
    tx = rc_x + 8
    for s in strengths[:4]:
        sw_ = c.stringWidth(_r(s, lang), fn_reg, 7.5) + 14
        _rect(c, tx, sw_y - 33, sw_, 13, fill_color=colors.HexColor('#d4edda'))
        _rect(c, tx, sw_y - 33, 3, 13, fill_color=C_GREEN)
        _text(c, tx + 6, sw_y - 29, _r(s, lang), fn_reg, 7.5,
              colors.HexColor('#155724'))
        tx += sw_ + 4

    # Weaknesses card
    wk_y = sw_y - sw_h - 6
    wk_h = 44
    _rect(c, rc_x, wk_y - wk_h, col_w, wk_h, fill_color=C_LGRAY,
          stroke_color=C_BORDER, lw=0.5)
    w_title = 'Areas to Improve' if lang == 'en' else 'مجالات التطوير'
    _text(c, rc_x + 8, wk_y - 13, _r(w_title, lang), fn_bold, 7.5,
          colors.HexColor('#856404'))
    weaknesses = data.get('weaknesses', ['Mid-Race Stamina', 'Reaction Time'])
    tx = rc_x + 8
    for w in weaknesses[:4]:
        ww_ = c.stringWidth(_r(w, lang), fn_reg, 7.5) + 14
        _rect(c, tx, wk_y - 33, ww_, 13, fill_color=colors.HexColor('#fff3cd'))
        _rect(c, tx, wk_y - 33, 3, 13, fill_color=C_YELLOW)
        _text(c, tx + 6, wk_y - 29, _r(w, lang), fn_reg, 7.5,
              colors.HexColor('#856404'))
        tx += ww_ + 4

    y = card_y - 14   # below left card (taller of the two)

    # ── SECTION: Attendance & Performance Rating ─────────────────────────────
    y = _draw_section_title(c, MARGIN, y, body_w,
                            'Attendance & Session Performance Rating' if lang == 'en'
                            else 'الحضور وتقييم أداء الجلسات', lang)
    y -= 8

    att_card_h = 110
    # Left card: donut
    _rect(c, MARGIN, y - att_card_h, col_w, att_card_h,
          fill_color=C_LGRAY, stroke_color=C_BORDER, lw=0.5)
    att_lbl = 'Monthly Attendance Rate' if lang == 'en' else 'نسبة الحضور الشهرية'
    _text(c, MARGIN + 8, y - 13, _r(att_lbl, lang), fn_bold, 7.5, C_MID)

    att_rate = data.get('attendance_rate', 0)
    donut_cx = MARGIN + 38
    donut_cy = y - att_card_h + 42
    _donut(c, donut_cx, donut_cy, 28, att_rate)

    # Info beside donut
    ix = donut_cx + 36
    sessions_count = data.get('sessions_count', 0)
    sessions_total = data.get('sessions_total', 0)
    absences       = sessions_total - sessions_count
    streak         = data.get('streak', 0)

    lines_en = [
        f'{sessions_count} of {sessions_total} sessions',
        f'{absences} absence(s) (excused)',
        f'Current streak: {streak} consecutive',
    ]
    lines_ar = [
        f'{sessions_count} من أصل {sessions_total} جلسة',
        f'{absences} غياب (بعذر)',
        f'السلسلة الحالية: {streak} متتالية',
    ]
    lines = lines_ar if lang == 'ar' else lines_en
    ly = y - att_card_h + 68
    for ln in lines:
        _text(c, ix, ly, _r(ln, lang), fn_reg, 7.5, C_MID)
        ly -= 12

    # Right card: session rating donut
    rc_x2 = MARGIN + col_w + 12
    _rect(c, rc_x2, y - att_card_h, col_w, att_card_h,
          fill_color=C_LGRAY, stroke_color=C_BORDER, lw=0.5)
    rat_lbl = 'Session Performance Rating (out of 10)' if lang == 'en' \
              else 'تقييم أداء الجلسة (من 10)'
    _text(c, rc_x2 + 8, y - 13, _r(rat_lbl, lang), fn_bold, 7.5, C_MID)

    overall = data.get('avg_rating', 8.7)
    rating_pct = max(0, min(100, (overall / 10.0) * 100))
    r_donut_cx = rc_x2 + 38
    r_donut_cy = y - att_card_h + 42
    _donut(c, r_donut_cx, r_donut_cy, 28, rating_pct)
    _text(c, r_donut_cx + 36, r_donut_cy + 10,
          f'{overall:.1f} / 10', fn_bold, 12, C_ACCENT)
    _text(c, r_donut_cx + 36, r_donut_cy - 5,
          _r('Overall Session Rating' if lang == 'en' else 'المتوسط العام لتقييم الجلسة', lang),
          fn_reg, 7.5, C_MID)

    y -= att_card_h + 10

    # ── SECTION: Weekly Performance Summary (moved to page 1) ───────────────
    y = _draw_section_title(c, MARGIN, y, body_w,
                            'Weekly Performance Summary' if lang == 'en'
                            else 'ملخص الأداء الأسبوعي', lang)
    y -= 6

    lines = _five_line_summary(data, lang)
    summary_txt = '\n'.join(lines)

    remaining_h = 140
    _rect(c, MARGIN, y - remaining_h, body_w, remaining_h,
          fill_color=colors.HexColor('#fafafa'), stroke_color=C_BORDER, lw=0.5)
    _rect(c, MARGIN, y - remaining_h, 5, remaining_h, fill_color=C_ACCENT)

    _wrap_text(c, MARGIN + 12, y - 10, _r(summary_txt, lang),
               fn_reg, 9, C_DARK, body_w - 20, 13)

    _draw_footer(c, data, lang, 1, 2)


# ════════════════════════════════════════════════════════════════════════════
#  Page 2 content
# ════════════════════════════════════════════════════════════════════════════

def _draw_page2(c, data, lang, logo_path=None):
    c.setFont('Helvetica', 10)

    y = _draw_header(c, data, lang, logo_path)
    body_w = PAGE_W - 2 * MARGIN
    fn_bold = _font_bold(lang)
    fn_reg  = _font_reg(lang)

    y -= 10
    y = _draw_section_title(c, MARGIN, y, body_w,
                            'Weekly Performance Summary' if lang == 'en'
                            else 'ملخص الأداء الأسبوعي', lang)
    y -= 6

    lines = _five_line_summary(data, lang)
    summary_txt = '\n'.join(lines)

    remaining_h = 250
    _rect(c, MARGIN, y - remaining_h, body_w, remaining_h,
          fill_color=colors.HexColor('#fafafa'), stroke_color=C_BORDER, lw=0.5)
    _rect(c, MARGIN, y - remaining_h, 5, remaining_h, fill_color=C_ACCENT)

    _wrap_text(c, MARGIN + 12, y - 10, _r(summary_txt, lang),
               fn_reg, 9, C_DARK, body_w - 20, 13)

    _draw_footer(c, data, lang, 2, 2)


# ════════════════════════════════════════════════════════════════════════════
#  Font helpers
# ════════════════════════════════════════════════════════════════════════════

def _font_bold(lang):
    if lang == 'ar':
        try:
            pdfmetrics.getFont('Amiri-Bold')
            return 'Amiri-Bold'
        except Exception:
            pass
    return 'Helvetica-Bold'


def _font_reg(lang):
    if lang == 'ar':
        try:
            pdfmetrics.getFont('Amiri')
            return 'Amiri'
        except Exception:
            pass
    return 'Helvetica'


def _r(text: str, lang: str) -> str:
    """Reshape + BiDi-reorder Arabic text for ReportLab rendering."""
    if lang != 'ar':
        return str(text)
    try:
        return get_display(arabic_reshaper.reshape(str(text)))
    except Exception:
        return str(text)


def _five_line_summary(data: dict, lang: str) -> list[str]:
    attendance_rate = float(data.get('summary_attendance_rate', data.get('attendance_rate', 0)) or 0)
    avg_rating = float(data.get('avg_rating', 0) or 0)
    sessions_count = int(data.get('summary_sessions_count', data.get('sessions_count', 0)) or 0)
    sessions_total = int(data.get('summary_sessions_total', data.get('sessions_total', 0)) or 0)
    workouts_completed = int(data.get('workouts_completed', 0) or 0)
    workouts_total = int(data.get('workouts_total', sessions_total) or 0)
    sport = str(data.get('sport', 'Athlete'))
    athlete_name = getattr(data.get('athlete'), 'name', 'Athlete')
    session_change_pct = data.get('session_change_pct')
    fitness_change_pct = data.get('fitness_tests_change_pct')
    advanced_change_pct = data.get('advanced_assessments_change_pct')
    sport_change_pct = data.get('sport_records_change_pct')
    swim_prog = data.get('swimming_progression') or {}

    def _fmt_delta(pct):
        if pct is None:
            return None
        return f"{pct:+.1f}%"

    def _trend_en(pct):
        if pct is None:
            return 'not updated'
        return 'improved' if pct > 0 else ('declined' if pct < 0 else 'stayed stable')

    def _trend_ar(pct):
        if pct is None:
            return 'غير محدث'
        return 'تحسن' if pct > 0 else ('تراجع' if pct < 0 else 'مستقر')

    swim_line_en = 'Swimming record progression is not updated yet.'
    swim_line_ar = 'تطور أرقام السباحة غير محدث حتى الآن.'
    if swim_prog:
        ev = swim_prog.get('event', 'Swimming')
        prev_r = swim_prog.get('previous', 'N/A')
        curr_r = swim_prog.get('current', 'N/A')
        exp_r = swim_prog.get('expected', 'N/A')
        swim_line_en = (
            f'{athlete_name} swimming record progression ({ev}): '
            f'Previous {prev_r}, Current {curr_r}, Expected {exp_r}.'
        )
        swim_line_ar = (
            f'تطور أرقام السباحة للاعب {athlete_name} ({ev}): '
            f'السابق {prev_r}، الحالي {curr_r}، المتوقع {exp_r}.'
        )

    def _format_swim_time(value: str) -> str:
        if not value or value == 'N/A':
            return 'N/A'
        text = str(value).strip()
        parts = text.split(':')
        try:
            if len(parts) == 3:
                # e.g. 0:01:02.870000 -> 01:02.87
                minutes = int(parts[1])
                seconds = float(parts[2])
                return f'{minutes:02d}:{seconds:05.2f}'
            if len(parts) == 2:
                minutes = int(parts[0])
                seconds = float(parts[1])
                return f'{minutes:02d}:{seconds:05.2f}'
            seconds = float(text)
            return f'{seconds:05.2f}'
        except Exception:
            return text

    def _event_to_requested_label(raw_event: str) -> str:
        if ' – ' in raw_event:
            left, right = raw_event.split(' – ', 1)
            return f'{right} {left}'
        return raw_event

    if lang == 'ar':
        swim_event = swim_prog.get('event', 'سباحة الظهر – 100m') if swim_prog else 'سباحة الظهر – 100m'
        stroke_label = 'سباحة الظهر' if 'Backstroke' in str(swim_event) else 'السباحة'
        prev_r = swim_prog.get('previous', 'N/A') if swim_prog else 'N/A'
        curr_r = swim_prog.get('current', 'N/A') if swim_prog else 'N/A'
        exp_r = swim_prog.get('expected', 'N/A') if swim_prog else 'N/A'
        return [
            f'بلغت نسبة الحضور {attendance_rate:.0f}%، حيث حضر الرياضي {sessions_count} من أصل {sessions_total} جلسات تدريبية، وأكمل {workouts_completed} من أصل {workouts_total} تدريبات محددة، مما يعكس التزامًا جيدًا واستمرارية واضحة في البرنامج التدريبي.',
            f'كان الأداء العام للرياضي في التدريب جيدًا خلال هذا الأسبوع، مع انتظام ملحوظ في جودة التنفيذ داخل الحصص التدريبية وتحسن في مستوى الانضباط الفني.',
            f'الأداء التدريبي العام كان {"متوسطًا" if avg_rating < 7.5 else "جيدًا"}، حيث شهد تقييم أداء الجلسات تراجعًا بنسبة ({_fmt_delta(session_change_pct) or "غير متاح"})، بينما ظلت اختبارات اللياقة البدنية مستقرة بنسبة ({_fmt_delta(fitness_change_pct) or "غير متاح"})، وكذلك التقييمات المتقدمة مستقرة بنسبة ({_fmt_delta(advanced_change_pct) or "غير متاح"}). أما السجلات الرياضية فقد أظهرت تحسنًا طفيفًا بنسبة ({_fmt_delta(sport_change_pct) or "غير متاح"}).',
            f'في سباق {swim_event}، كان الزمن السابق {prev_r}، والزمن الحالي {curr_r}، بينما الزمن المتوقع المستهدف هو {exp_r}، مما يشير إلى الحاجة إلى مزيد من التركيز على تطوير الأداء الفني، خاصة في الدورانات والنهايات.',
            f'متوسط تقييم الجلسات الحالي هو {avg_rating:.1f} من 10، وهو يعكس مستوى أداء جيد مع وجود فرصة واضحة للتطور والتحسن خلال المرحلة القادمة.',
        ]
    return [
        f'The attendance rate reached {attendance_rate:.0f}%, with the athlete attending {sessions_count} out of {sessions_total} training sessions and completing {workouts_completed} out of {workouts_total} assigned workouts, reflecting good commitment and clear consistency within the training program.',
        f'The athlete’s overall performance in training was good during this week, with noticeable consistency in execution quality during training sessions and improvement in technical discipline.',
        f'The overall training performance was {"average" if avg_rating < 7.5 else "good"}, as session performance ratings showed a {"decline" if (session_change_pct is not None and session_change_pct < 0) else ("no change" if session_change_pct == 0 else "improvement")} of ({_fmt_delta(session_change_pct) or "N/A"}), while fitness tests remained {"stable" if fitness_change_pct == 0 else _trend_en(fitness_change_pct)} at ({_fmt_delta(fitness_change_pct) or "N/A"}), and advanced assessments also showed {"no change" if advanced_change_pct == 0 else _trend_en(advanced_change_pct)} at ({_fmt_delta(advanced_change_pct) or "N/A"}). Sports records, however, showed a {"slight improvement" if (sport_change_pct is not None and sport_change_pct > 0) else _trend_en(sport_change_pct)} of ({_fmt_delta(sport_change_pct) or "N/A"}).',
        f'In the {_event_to_requested_label(swim_prog.get("event", "100m Backstroke")) if swim_prog else "100m Backstroke"} event, the previous time was {_format_swim_time(swim_prog.get("previous", "N/A")) if swim_prog else "N/A"}, the current time remains {_format_swim_time(swim_prog.get("current", "N/A")) if swim_prog else "N/A"}, while the target expected time is {_format_swim_time(swim_prog.get("expected", "N/A")) if swim_prog else "N/A"}, indicating the need for greater focus on improving technical performance, especially in turns and finishes.',
        f'The current average session rating is {avg_rating:.1f} out of 10, reflecting a good performance level with a clear opportunity for further development and improvement in the upcoming phase.',
    ]


# ════════════════════════════════════════════════════════════════════════════
#  Public service class  (drop-in replacement)
# ════════════════════════════════════════════════════════════════════════════

class ReportGeneratorService:
    """
    Tiger Academy athlete report generator.
    Public interface is identical to the original service.
    """

    # ── Font setup ───────────────────────────────────────────────────────────
    @staticmethod
    def setup_fonts(static_path: str):
        """Register Arabic fonts (Amiri) with ReportLab."""
        fonts = {
            'Amiri':      'Amiri-Regular.ttf',
            'Amiri-Bold': 'Amiri-Bold.ttf',
        }
        for name, filename in fonts.items():
            path = os.path.join(static_path, 'fonts', filename)
            if os.path.exists(path):
                try:
                    pdfmetrics.registerFont(TTFont(name, path))
                except Exception as e:
                    logger.warning(f'Could not register font {name}: {e}')

    # ── Text reshape helper (kept for backward compat) ───────────────────────
    @staticmethod
    def reshape_text(text: str, lang: str = 'en') -> str:
        return _r(text, lang)

    # ── Main PDF generation ──────────────────────────────────────────────────
    @staticmethod
    def generate_pdf(data: dict, lang: str = 'en') -> bytes:
        """
        Generate a two-page Tiger Academy athlete report PDF.

        Parameters
        ----------
        data : dict
            Output of get_weekly_data(), optionally enriched with extra keys
            (see _EXTRA_KEYS below for the full list the layout reads).
        lang : str
            'en' for English, 'ar' for Arabic.

        Returns
        -------
        bytes
            Raw PDF bytes ready to stream or save.
        """
        static_path = data.get('static_path', '')
        ReportGeneratorService.setup_fonts(static_path)

        logo_path = data.get('logo_path') or os.path.join(static_path, 'img', 'tiger_logo.png')

        buffer = io.BytesIO()
        c = rl_canvas.Canvas(buffer, pagesize=A4)
        c.setTitle('Tiger Academy – Athlete Performance Report')
        c.setAuthor('Tiger Academy')

        # ── Single page ───────────────────────────────────────────────────────
        _draw_page1(c, data, lang, logo_path)
        c.showPage()

        c.save()
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes

    # ── Data gathering ────────────────────────────────────────────────────────
    @staticmethod
    def get_weekly_data(athlete, reference_date=None) -> dict:
        """
        Gathers ALL data visible on the athlete profile page and maps it into
        the full data contract expected by the two-page PDF layout.
        """
        if not _DJANGO:
            raise RuntimeError('Django is required for get_weekly_data()')

        if reference_date is None:
            reference_date = timezone.now()

        start_date = reference_date - timedelta(days=7)

        # ── Attendance & ratings ──────────────────────────────────────────────
        all_attendance = AttendanceRecord.objects.filter(
            athlete=athlete
        ).order_by('date')

        week_attendance = all_attendance.filter(
            date__range=[start_date.date(), reference_date.date()]
        )
        prev_week_start = reference_date - timedelta(days=14)
        prev_week_end = reference_date - timedelta(days=7)
        prev_week_attendance = all_attendance.filter(
            date__range=[prev_week_start.date(), prev_week_end.date()]
        )

        avg_rating       = week_attendance.aggregate(Avg('performance_rating'))['performance_rating__avg'] or 0.0
        prev_avg_rating  = prev_week_attendance.aggregate(Avg('performance_rating'))['performance_rating__avg'] or 0.0
        attendance_count = week_attendance.filter(attended=True).count()
        sessions_total   = week_attendance.count()
        attendance_rate  = (attendance_count / sessions_total * 100) if sessions_total > 0 else 0
        workouts_completed = week_attendance.filter(attended=True, workout_completed=True).count()
        workouts_total = attendance_count

        # Overall attendance rate (all-time, for the donut)
        all_count    = all_attendance.count()
        all_attended = all_attendance.filter(attended=True).count()
        overall_rate = (all_attended / all_count * 100) if all_count > 0 else 0

        # Consecutive attendance streak
        streak = 0
        for rec in reversed(list(all_attendance)):
            if rec.attended:
                streak += 1
            else:
                break

        # Week number (from first attendance record)
        first_record = all_attendance.first()
        if first_record:
            weeks_elapsed = (reference_date.date() - first_record.date).days // 7 + 1
        else:
            weeks_elapsed = 1
        week_start = (reference_date - timedelta(days=6)).strftime('%b %d')
        week_end   = reference_date.strftime('%b %d, %Y')
        week_label = f'Week {weeks_elapsed}  |  {week_start}–{week_end}'

        # Per-category average rating from coach notes labels (best effort)
        rated = list(week_attendance.filter(performance_rating__isnull=False))
        _avg = lambda lst: round(sum(lst) / len(lst), 1) if lst else 0.0
        all_ratings = [r.performance_rating for r in rated if r.performance_rating]
        overall_avg  = _avg(all_ratings)

        # ── Fitness profile ───────────────────────────────────────────────────
        fitness = Fitness.objects.filter(athlete=athlete).first()

        sessions_per_week = fitness.sessions_per_week if fitness else 4
        fitness_goal      = fitness.fitness_goal      if fitness else ''
        strategy_text     = ''
        if fitness:
            parts = []
            if fitness.workout_type:
                parts.append(f'Workout focus: {fitness.workout_type}.')
            if fitness.workout_plan:
                # First paragraph of the plan
                first_para = fitness.workout_plan.split('\n\n')[0].strip()
                parts.append(first_para)
            strategy_text = ' '.join(parts) if parts else 'No strategy recorded.'

        # ── Assessment table stats ────────────────────────────────────────────
        stats = []

        curr_tests = fitness.current_fitness_tests or {} if fitness else {}
        prev_tests = fitness.previous_fitness_tests or {} if fitness else {}
        target_tests = fitness.expected_fitness_results or {} if fitness else {}
        if fitness:

            for k, v in curr_tests.items():
                if isinstance(v, (int, float)):
                    prev_v   = prev_tests.get(k, 0)
                    target_v = target_tests.get(k, v)
                    delta    = v - prev_v
                    stats.append({
                        'category': 'Fitness',
                        'metric':   k,
                        'current':  v,
                        'previous': prev_v,
                        'target':   round(target_v, 2) if isinstance(target_v, float) else target_v,
                        'delta':    f'{delta:+.1f}',
                        'status':   'ON TRACK' if delta >= 0 else 'NEEDS FOCUS',
                    })
                elif isinstance(v, dict) and isinstance(v.get('value'), (int, float)):
                    prev_raw = prev_tests.get(k, {})
                    prev_v = prev_raw.get('value', 0) if isinstance(prev_raw, dict) else 0
                    target_raw = target_tests.get(k, {})
                    if isinstance(target_raw, dict):
                        target_v = target_raw.get('value', v.get('value'))
                    else:
                        target_v = target_raw or v.get('value')
                    delta = float(v.get('value', 0)) - float(prev_v or 0)
                    stats.append({
                        'category': 'Fitness',
                        'metric':   k,
                        'current':  float(v.get('value', 0)),
                        'previous': float(prev_v or 0),
                        'target':   round(float(target_v), 2) if isinstance(target_v, (int, float)) else target_v,
                        'delta':    f'{delta:+.1f}',
                        'status':   'ON TRACK' if delta >= 0 else 'NEEDS FOCUS',
                    })

        # ── Progress bar items (top fitness metrics) ──────────────────────────
        progress_items    = []
        progress_items_ar = []
        if fitness and fitness.current_fitness_tests:
            curr = fitness.current_fitness_tests
            tgt  = fitness.expected_fitness_results or {}
            for k, v in list(curr.items())[:4]:
                if isinstance(v, (int, float)):
                    t_v = tgt.get(k, v)
                    pct = min(int((v / t_v) * 100), 100) if t_v else 50
                    colour = 'green' if pct >= 85 else ('yellow' if pct >= 65 else 'red')
                    progress_items.append(
                        (k, pct, f'{v} actual', f'{round(t_v, 2)} target', colour)
                    )
                    progress_items_ar.append(
                        (k, pct, f'{v} فعلي', f'هدف {round(t_v, 2)}', colour)
                    )

        # ── Sport specialization ──────────────────────────────────────────────
        sport_tag        = 'General Fitness'
        sport_name       = 'General Training'
        primary_obj      = fitness_goal or 'Achieve peak performance targets.'
        records          = []
        events           = []
        swimming_stats   = []

        # Swimming
        all_swimming = list(athlete.swimming_records.order_by('-recorded_at')) \
                       if hasattr(athlete, 'swimming_records') else []
        swimming_progression = None
        if all_swimming:
            sport_name = 'Swimming'
            sport_tag  = f'Swimming · {all_swimming[0].stroke}'
            primary_obj = all_swimming[0].swimming_goal or primary_obj
            latest_swim = all_swimming[0]
            swimming_progression = {
                'event': f'{latest_swim.stroke} – {latest_swim.events}',
                'previous': str(latest_swim.previous_record) if latest_swim.previous_record else 'N/A',
                'current': str(latest_swim.current_record) if latest_swim.current_record else 'N/A',
                'expected': str(latest_swim.expected_record) if latest_swim.expected_record else 'N/A',
            }
            for s in all_swimming:
                curr_s = s.current_record.total_seconds() if s.current_record else 0
                prev_s = s.previous_record.total_seconds() if s.previous_record else curr_s
                tgt_s  = s.expected_record.total_seconds() if s.expected_record else curr_s * 0.95
                delta_s = prev_s - curr_s  # improvement = positive
                stats.append({
                    'category': 'Swimming',
                    'metric':   f'{s.stroke} – {s.events}',
                    'current':  str(s.current_record),
                    'previous': str(s.previous_record) if s.previous_record else 'N/A',
                    'target':   str(s.expected_record) if s.expected_record else 'N/A',
                    'delta':    f'{delta_s:+.1f}s' if prev_s else '—',
                    'status':   'ON TRACK' if delta_s >= 0 else 'NEEDS FOCUS',
                })
                records.append((f'{s.stroke} – {s.events}',
                                str(s.current_record),
                                s.recorded_at.strftime('%b %Y')))
                events.append((f'{s.stroke} {s.events}',
                               s.recorded_at.strftime('%b %d, %Y'),
                               str(s.current_record),
                               '—',
                               'PB' if not s.previous_record else 'Record',
                               'blue' if not s.previous_record else 'green'))

        # Basketball
        all_basketball = list(athlete.basketball_records.order_by('-recorded_at')) \
                         if hasattr(athlete, 'basketball_records') else []
        if all_basketball and not all_swimming:
            sport_name = 'Basketball'
            sport_tag  = f'Basketball · {all_basketball[0].position}'
            for b in all_basketball:
                stats.append({
                    'category': 'Basketball',
                    'metric':   'Vertical Jump (in)',
                    'current':  float(b.vertical_jump),
                    'previous': 0,
                    'target':   float(b.vertical_jump) * 1.05,
                    'delta':    '—',
                    'status':   'ON TRACK',
                })
                stats.append({
                    'category': 'Basketball',
                    'metric':   'Game High (pts)',
                    'current':  b.current_game_high,
                    'previous': 0,
                    'target':   b.current_game_high,
                    'delta':    '—',
                    'status':   'ON TRACK',
                })
                records.append(('Game High', f'{b.current_game_high} pts',
                                b.recorded_at.strftime('%b %Y')))
                records.append(('Vertical Jump', f'{b.vertical_jump}"',
                                b.recorded_at.strftime('%b %Y')))
                if b.shooting_stats:
                    for k, v in list(b.shooting_stats.items())[:3]:
                        events.append((k, b.recorded_at.strftime('%b %d, %Y'),
                                       str(v), '—', 'Stat', 'blue'))

        # Football
        all_football = list(athlete.football_records.order_by('-recorded_at')) \
                       if hasattr(athlete, 'football_records') else []
        if all_football and not all_swimming and not all_basketball:
            sport_name = 'Football'
            sport_tag  = f'Football · {all_football[0].position}'
            for f_ in all_football:
                for k, v in list((f_.technical_stats or {}).items())[:3]:
                    if isinstance(v, (int, float)):
                        stats.append({
                            'category': 'Football – Technical',
                            'metric':   k,
                            'current':  v,
                            'previous': 0,
                            'target':   v * 1.05,
                            'delta':    '—',
                            'status':   'ON TRACK',
                        })
                for k, v in list((f_.physical_data or {}).items())[:3]:
                    if isinstance(v, (int, float)):
                        stats.append({
                            'category': 'Football – Physical',
                            'metric':   k,
                            'current':  v,
                            'previous': 0,
                            'target':   v * 1.05,
                            'delta':    '—',
                            'status':   'ON TRACK',
                        })

        # CrossFit
        all_crossfit = list(athlete.crossfit_records.order_by('-recorded_at')) \
                       if hasattr(athlete, 'crossfit_records') else []
        if all_crossfit and not all_swimming and not all_basketball and not all_football:
            sport_name = 'CrossFit'
            sport_tag  = f'CrossFit · {all_crossfit[0].level}'
            for cf in all_crossfit:
                for k, v in list((cf.strength_maxes or {}).items())[:4]:
                    if isinstance(v, (int, float)):
                        stats.append({
                            'category': 'CrossFit – Strength',
                            'metric':   k,
                            'current':  v,
                            'previous': 0,
                            'target':   v * 1.05,
                            'delta':    '—',
                            'status':   'ON TRACK',
                        })

        # ── Injuries / strengths / weaknesses as lists ────────────────────────
        def _split_field(text):
            """Split a comma/newline-separated text field into a clean list."""
            if not text:
                return []
            import re
            parts = re.split(r'[,\n;]+', text)
            return [p.strip() for p in parts if p.strip()]

        # `athlete.injuries` was removed in migration 0011; derive notes from InjuryRecord.
        if hasattr(athlete, 'injury_records'):
            injury_qs = athlete.injury_records.order_by('-is_active', '-start_date', '-recorded_at')
            injuries = []
            for inj in injury_qs:
                status = 'Active' if inj.is_active else 'Resolved'
                severity = f", {inj.severity}" if getattr(inj, 'severity', None) else ''
                injuries.append(f"{inj.injury_type} ({status}{severity})")
        else:
            injuries = []
        strengths  = _split_field(athlete.strengths)
        weaknesses = _split_field(athlete.weaknesses)

        # ── BMI calc ──────────────────────────────────────────────────────────
        try:
            height_m = float(athlete.height) / 100
            weight_kg = float(athlete.weight)
            bmi = round(weight_kg / (height_m ** 2), 1)
            bmi_label = (
                'Underweight' if bmi < 18.5 else
                'Optimal'     if bmi < 25   else
                'Overweight'  if bmi < 30   else
                'Obese'
            )
            bmi_str = f'{bmi} – {bmi_label}'
        except Exception:
            bmi_str = '—'

        # ── Summary paragraph ─────────────────────────────────────────────────
        summary = ReportGeneratorService.generate_summary(
            athlete, overall_rate, avg_rating, stats
        )

        def _pct_change(curr, prev, lower_is_better=False):
            if prev in (None, 0):
                return None
            try:
                curr_f = float(curr)
                prev_f = float(prev)
                if lower_is_better:
                    return ((prev_f - curr_f) / abs(prev_f)) * 100.0
                return ((curr_f - prev_f) / abs(prev_f)) * 100.0
            except Exception:
                return None

        session_change_pct = _pct_change(avg_rating, prev_avg_rating, lower_is_better=False)

        def _avg_pct_for_keys(keys, lower_is_better=False, object_mode=False):
            vals = []
            for k in keys:
                c = curr_tests.get(k) if fitness else None
                p = prev_tests.get(k) if fitness else None
                if object_mode:
                    if isinstance(c, dict):
                        c = c.get('value')
                    if isinstance(p, dict):
                        p = p.get('value')
                if isinstance(c, (int, float)) and isinstance(p, (int, float)) and p != 0:
                    pct = _pct_change(c, p, lower_is_better=lower_is_better)
                    if pct is not None:
                        vals.append(pct)
            return round(sum(vals) / len(vals), 1) if vals else None

        fitness_keys = []
        advanced_keys = []
        if fitness:
            for k, v in curr_tests.items():
                if k == 'notes':
                    continue
                is_advanced = isinstance(k, str) and (('__' in k) or k.startswith('_'))
                if is_advanced:
                    advanced_keys.append(k)
                else:
                    fitness_keys.append(k)

        fitness_tests_change_pct = _avg_pct_for_keys(fitness_keys, lower_is_better=False, object_mode=True)
        advanced_assessments_change_pct = _avg_pct_for_keys(advanced_keys, lower_is_better=False, object_mode=True)

        sport_records_change_pct = None
        if all_swimming:
            sport_vals = []
            for s in all_swimming:
                if s.current_record and s.previous_record:
                    c = s.current_record.total_seconds()
                    p = s.previous_record.total_seconds()
                    pct = _pct_change(c, p, lower_is_better=True)
                    if pct is not None:
                        sport_vals.append(pct)
            if sport_vals:
                sport_records_change_pct = round(sum(sport_vals) / len(sport_vals), 1)

        # ── Report reference ──────────────────────────────────────────────────
        report_ref = f'TA-{reference_date.year}-{reference_date.strftime("%b").upper()}-{athlete.id:04d}'

        return {
            # Core
            'athlete':           athlete,
            'report_date':       reference_date.strftime('%B %d, %Y'),
            'report_ref':        report_ref,
            'week_label':        week_label,
            # Attendance
            'attendance_rate':   round(overall_rate, 1),
            'avg_rating':        round(overall_avg or avg_rating, 1),
            'sessions_count':    all_attended,
            'sessions_total':    all_count,
            'summary_attendance_rate': round(attendance_rate, 1),
            'summary_sessions_count':  attendance_count,
            'summary_sessions_total':  sessions_total,
            'workouts_completed': workouts_completed,
            'workouts_total':     workouts_total,
            'streak':            streak,
            # Targets (from fitness)
            'sessions_per_week': sessions_per_week,
            'target_time':       fitness_goal[:10] if fitness_goal else '—',
            'peak_target_date':  'Q3',
            'strength_goal':     '+10%',
            'program_phase':     f'Week {weeks_elapsed}',
            'sport_tag':         sport_tag,
            'sport':             sport_name,
            'primary_objective': primary_obj,
            'strategy':          strategy_text,
            # Medical
            'injuries':          injuries or ['No active injuries reported'],
            'strengths':         strengths or ['Not recorded'],
            'weaknesses':        weaknesses or ['Not recorded'],
            # BMI (injected into athlete-like attr via dict so layout can use it)
            'bmi':               bmi_str,
            # Rating breakdown (best-effort from overall avg)
            'rating_sprint':     round(avg_rating, 1),
            'rating_strength':   round(avg_rating, 1),
            'rating_technique':  round(avg_rating, 1),
            'rating_recovery':   round(avg_rating, 1),
            'rating_mental':     round(avg_rating, 1),
            # Progress bars
            'progress_items':    progress_items,
            'progress_items_ar': progress_items_ar,
            # Sport
            'records':           records[:4],
            'events':            events[:6],
            # Assessment table
            'stats':             stats,
            'summary':           summary,
            'session_change_pct': session_change_pct,
            'fitness_tests_change_pct': fitness_tests_change_pct,
            'advanced_assessments_change_pct': advanced_assessments_change_pct,
            'sport_records_change_pct': sport_records_change_pct,
            'swimming_progression': swimming_progression,
        }

    # ── Summary generation (UNCHANGED from original) ─────────────────────────
    @staticmethod
    def generate_summary(athlete, attendance_rate: float, avg_rating: float,
                         stats: list, lang: str = 'en') -> str:
        """
        Creates a natural-language summary based on the week's data.
        Identical to the original implementation.
        """
        name = athlete.name.split(' ')[0] if hasattr(athlete, 'name') else 'Athlete'

        if lang == 'ar':
            summary = f'أظهر {name} '
            if avg_rating >= 8.5 and attendance_rate >= 90:
                summary += 'أسبوعاً منضبطاً واستثنائياً للغاية في التدريب. '
            elif avg_rating >= 7:
                summary += 'أسبوعاً متسقاً ومثمراً. '
            else:
                summary += 'أسبوعاً ركز فيه على التعديلات الأساسية والتعافي. '

            summary += (f'بمعدل حضور بلغت نسبته {int(attendance_rate)}٪ '
                        f'ومتوسط تقييم جلسة {avg_rating}/10، ')
            summary += 'لاحظ فريق التدريب تفاعلاً قوياً خلال التدريبات الفنية. '

            # Build improvements list that understands both numeric metrics and
            # time-formatted strings (e.g. swimming 'MM:SS.ss' where lower is better).
            def _parse_time_to_seconds(t):
                if t in (None, ''):
                    return None
                try:
                    s = str(t).strip()
                    if ':' in s:
                        parts = [float(p) for p in s.split(':')]
                        parts = parts[::-1]
                        seconds = 0.0
                        if len(parts) > 0:
                            seconds += parts[0]
                        if len(parts) > 1:
                            seconds += parts[1] * 60
                        if len(parts) > 2:
                            seconds += parts[2] * 3600
                        return seconds
                    # decimal seconds (e.g. '62.87')
                    return float(s)
                except Exception:
                    return None

            improvements = []
            for s in stats:
                cur = s.get('current')
                prev = s.get('previous', None)
                # Numeric metrics (higher is better)
                if isinstance(cur, (int, float)) and isinstance(prev, (int, float)):
                    if cur > prev:
                        improvements.append((abs(cur - prev), s))
                    continue
                # Try time parsing for both fields (lower is better)
                cur_t = _parse_time_to_seconds(cur)
                prev_t = _parse_time_to_seconds(prev)
                if cur_t is not None and prev_t is not None and prev_t > cur_t:
                    # improvement magnitude in seconds
                    improvements.append((prev_t - cur_t, s))

            improvements.sort(key=lambda x: x[0], reverse=True)
            if improvements:
                top = improvements[0][1]
                summary += (f'والجدير بالذكر أن {name} حقق إنجازاً شخصياً '
                            f'في {top["category"]}، ')
                summary += f'حيث تقدم من {top.get("previous")} إلى {top.get("current")}.'

            summary += ('بشكل عام، الزخم يسير في الاتجاه الصحيح، ونحن واثقون '
                        'من أنه مع الاستمرار في الثبات، فإن أهداف الأداء القادمة '
                        'في متناول اليد تماماً.')
        else:
            summary = f'{name} demonstrated a '
            if avg_rating >= 8.5 and attendance_rate >= 90:
                summary += 'highly disciplined and exceptional week of training. '
            elif avg_rating >= 7:
                summary += 'consistent and productive week. '
            else:
                summary += 'week focused on foundational adjustments and recovery. '

            summary += (f'With an attendance rate of {int(attendance_rate)}% '
                        f'and an average session rating of {avg_rating}/10, ')
            summary += 'the coaching team observed strong engagement during technical drills. '

            # Build improvements list that understands both numeric metrics and
            # time-formatted strings (e.g. swimming 'MM:SS.ss' where lower is better).
            def _parse_time_to_seconds(t):
                if t in (None, ''):
                    return None
                try:
                    s = str(t).strip()
                    if ':' in s:
                        parts = [float(p) for p in s.split(':')]
                        parts = parts[::-1]
                        seconds = 0.0
                        if len(parts) > 0:
                            seconds += parts[0]
                        if len(parts) > 1:
                            seconds += parts[1] * 60
                        if len(parts) > 2:
                            seconds += parts[2] * 3600
                        return seconds
                    return float(s)
                except Exception:
                    return None

            improvements = []
            for s in stats:
                cur = s.get('current')
                prev = s.get('previous', None)
                if isinstance(cur, (int, float)) and isinstance(prev, (int, float)):
                    if cur > prev:
                        improvements.append((abs(cur - prev), s))
                    continue
                cur_t = _parse_time_to_seconds(cur)
                prev_t = _parse_time_to_seconds(prev)
                if cur_t is not None and prev_t is not None and prev_t > cur_t:
                    improvements.append((prev_t - cur_t, s))

            improvements.sort(key=lambda x: x[0], reverse=True)
            if improvements:
                top = improvements[0][1]
                summary += (f'Notably, {name} achieved a personal milestone '
                            f'in {top["category"]}, ')
                summary += f'progressing from {top.get("previous")} to {top.get("current")}. '

            summary += ('Overall, momentum is building in the right direction, '
                        'and we are confident that with continued consistency, '
                        'the upcoming performance targets are well within reach.')

        # Add explicit listing of swimming records (helps ensure short events
        # like 50m are called out even if they haven't improved this week).
        try:
            swim_lines = []
            for s in stats:
                if s.get('category') and 'Swimming' in s.get('category'):
                    label = s.get('metric') or s.get('category')
                    curr = s.get('current', 'N/A')
                    swim_lines.append(f"{label}: {curr}")
            if swim_lines:
                summary += ' Swimming records: ' + '; '.join(swim_lines) + '.'
        except Exception:
            pass

        return summary


# ════════════════════════════════════════════════════════════════════════════
#  Standalone smoke-test  (run: python report_generator_service.py)
# ════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    """
    Self-contained test that generates both language PDFs with dummy data
    so you can visually verify the layout without a Django environment.
    """

    class _FakeAthlete:
        name           = 'Ahmed Al-Mansouri'
        age            = 19
        gender         = 'Male'
        date_of_birth  = 'March 3, 2007'
        height         = '181 cm'
        weight         = '74 kg'
        body_type      = 'Ecto-Mesomorph'
        bmi            = '22.6 – Optimal'
        nationality    = 'UAE'
        academy_since  = 'September 2024'

    DUMMY_STATS = [
        {'category': 'Speed – 100m',   'metric': 'Time (sec)',        'previous': 10.91, 'current': 10.62, 'target': 10.45, 'delta': '-0.29s', 'status': 'ON TRACK'},
        {'category': 'Speed – 60m',    'metric': 'Time (sec)',        'previous':  6.82, 'current':  6.61, 'target':  6.50, 'delta': '-0.21s', 'status': 'ON TRACK'},
        {'category': 'Speed – 200m',   'metric': 'Time (sec)',        'previous': 22.40, 'current': 21.95, 'target': 21.50, 'delta': '-0.45s', 'status': 'PROGRESSING'},
        {'category': 'Strength',       'metric': 'Leg Press (kg)',    'previous': 140,   'current': 180,   'target': 200,   'delta': '+40 kg',  'status': 'ON TRACK'},
        {'category': 'Power',          'metric': 'Vertical Jump (cm)','previous':  52,   'current':  58,   'target':  63,   'delta': '+6 cm',   'status': 'PROGRESSING'},
        {'category': 'Agility',        'metric': 'Reaction Time (ms)','previous': 170,   'current': 148,   'target': 135,   'delta': '-22ms',   'status': 'NEEDS FOCUS'},
        {'category': 'Endurance',      'metric': 'VO2 Max',           'previous':  58.2, 'current':  62.4, 'target':  65.0, 'delta': '+4.2',    'status': 'ON TRACK'},
        {'category': 'Body Comp.',     'metric': 'Body Fat %',        'previous':  12.5, 'current':  10.8, 'target':  10.0, 'delta': '-1.7%',   'status': 'ON TRACK'},
        {'category': 'Flexibility',    'metric': 'Sit-Reach (cm)',    'previous':  31,   'current':  36,   'target':  42,   'delta': '+5 cm',   'status': 'NEEDS FOCUS'},
        {'category': 'Mental',         'metric': 'Focus Score',       'previous':   7.0, 'current':   8.5, 'target':   9.0, 'delta': '+1.5',    'status': 'EXCELLENT'},
    ]

    athlete = _FakeAthlete()
    summary_en = ReportGeneratorService.generate_summary(athlete, 94, 8.7, DUMMY_STATS, lang='en')
    summary_ar = ReportGeneratorService.generate_summary(athlete, 94, 8.7, DUMMY_STATS, lang='ar')

    BASE_DATA = {
        'logo_path':        '',           # set to your logo path
        'static_path':      '',           # set to your static root
        'report_date':      'April 19, 2026',
        'report_ref':       'TA-2026-APR-0042',
        'athlete':          athlete,
        'attendance_rate':  94.0,
        'avg_rating':       8.7,
        'sessions_count':   47,
        'sessions_total':   50,
        'streak':           16,
        'sessions_per_week': 4,
        'target_time':      '10.45',
        'peak_target_date': 'Q3',
        'strength_goal':    '+12%',
        'program_phase':    'Week 14',
        'sport_tag':        'Athletics · Sprint Specialist',
        'sport':            'Athletics – Short Sprint Specialist (100m / 200m)',
        'primary_objective':
            'Qualify for UAE National Junior Championships (Q3 2026) '
            'and achieve sub-10.50s in the 100m by August 2026.',
        'strategy':
            'Phase 2 – Speed Development & Race Mechanics. Priority on explosive '
            'start optimization and 60–80m race phase conditioning. Integrate '
            'plyometric loading 2x per week alongside technical sprint work to '
            'bridge gap to sub-10.5 target before Q3 championships.',
        'injuries':   ['Minor Right Hamstring Strain', 'Previous Left Ankle Sprain (Healed)'],
        'strengths':  ['Explosive Start', 'Stride Frequency', 'Race Composure'],
        'weaknesses': ['Mid-Race Stamina', 'Upper-Body Drive', 'Reaction Time'],
        'rating_sprint':    9.3,
        'rating_strength':  8.2,
        'rating_technique': 8.8,
        'rating_recovery':  7.8,
        'rating_mental':    8.5,
        'progress_items': [
            ('100m Sprint Time',     76, '10.62s actual', '10.55s target', 'green'),
            ('Max Velocity (km/h)',  70, '34.8 actual',   '36.0 target',   'yellow'),
            ('Leg Press (kg)',       82, '180 actual',     '200 target',    'yellow'),
            ('Reaction Time (ms)',   60, '148ms actual',   '135ms target',  'red'),
        ],
        'progress_items_ar': [
            ('سباق 100م',            76, '10.62 ث فعلي',  'هدف 10.55',   'green'),
            ('السرعة القصوى (كم/س)', 70, '34.8 فعلي',    'هدف 36.0',    'yellow'),
            ('الضغط بالساق (كغ)',    82, '180 فعلي',      'هدف 200',     'yellow'),
            ('زمن رد الفعل (م.ث)',  60, '148 فعلي',      'هدف 135',     'red'),
        ],
        'records': [
            ('100m Sprint', '10.62s', 'Apr 2026 (PB)'),
            ('60m Sprint',  '6.61s',  'Mar 2026 (PB)'),
            ('200m Sprint', '21.95s', 'Feb 2026 (PB)'),
            ('Vertical Jump','58 cm', 'Apr 2026 (PB)'),
        ],
        'events': [
            ('Academy Time Trial',    'Apr 5, 2026',  '10.62s', '1st', 'New PB',  'blue'),
            ('UAE Club Invitational', 'Mar 15, 2026', '10.71s', '2nd', 'Strong',  'green'),
            ('Indoor 60m Open',       'Feb 20, 2026', '6.61s',  '1st', 'New PB',  'blue'),
            ('GCC Youth Sprint',      'Jan 28, 2026', '10.79s', '3rd', 'Windy',   'yellow'),
            ('Academy Monthly Trial', 'Dec 12, 2025', '10.84s', '1st', 'Solid',   'green'),
            ('End-Season Trial',      'Nov 5, 2025',  '10.91s', '2nd', 'Baseline','yellow'),
        ],
        'week_label': 'Week 14  |  April 13–19, 2026',
        'stats':      DUMMY_STATS,
        'summary':    summary_en,
    }

    # English PDF
    data_en = {**BASE_DATA, 'summary': summary_en}
    pdf_en  = ReportGeneratorService.generate_pdf(data_en, lang='en')
    out_en  = 'Tiger_Academy_Report_EN.pdf'
    with open(out_en, 'wb') as f:
        f.write(pdf_en)
    print(f'✓  English PDF → {out_en}  ({len(pdf_en):,} bytes)')

    # Arabic PDF
    data_ar = {**BASE_DATA, 'summary': summary_ar}
    pdf_ar  = ReportGeneratorService.generate_pdf(data_ar, lang='ar')
    out_ar  = 'Tiger_Academy_Report_AR.pdf'
    with open(out_ar, 'wb') as f:
        f.write(pdf_ar)
    print(f'✓  Arabic PDF  → {out_ar}  ({len(pdf_ar):,} bytes)')
