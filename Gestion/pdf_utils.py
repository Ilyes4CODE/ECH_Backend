"""
ReportLab-based PDF generation for ECH SAHARA ERP.

Pure-Python — no external programs required.
Install: pip install reportlab
"""

import io
import os
import base64
from decimal import Decimal
from datetime import datetime

import qrcode
from PIL import Image as PILImage

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm, mm
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Image, KeepTogether,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from django.conf import settings
from django.utils import timezone


# ─────────────────────────────────────────────────────────────────────────────
# Logo paths (project root)
# ─────────────────────────────────────────────────────────────────────────────
_LOGO_DIR = getattr(settings, 'BASE_DIR', os.path.dirname(os.path.dirname(__file__)))
LOGO_SARL = os.path.join(_LOGO_DIR, 'SARL.png')
LOGO_SCK  = os.path.join(_LOGO_DIR, 'SCK.png')
LOGO_ISO  = os.path.join(_LOGO_DIR, 'ISO.png')


def _safe_image(path, width=None, height=None):
    """
    Return a ReportLab Image if the path exists; otherwise an empty Spacer.

    If only one of (width, height) is provided, the missing dimension is
    derived from the image's native aspect ratio using PIL. This avoids
    ReportLab's default behavior of using the raw pixel size as a point
    measurement, which produces wildly stretched/squashed logos.
    """
    try:
        if os.path.exists(path):
            # If width and height are not both supplied, read natural size
            # from the PNG and compute the missing dimension to preserve
            # aspect ratio.
            if width is None or height is None:
                try:
                    with PILImage.open(path) as im:
                        nat_w, nat_h = im.size
                    if width is None and height is None:
                        # Default: cap at 1.5 cm height
                        height = 1.5 * cm
                        width = height * (nat_w / nat_h)
                    elif width is None:
                        width = height * (nat_w / nat_h)
                    elif height is None:
                        height = width * (nat_h / nat_w)
                except Exception:
                    # Fallback to safe square if PIL fails for any reason
                    width = width or (height or 1.5 * cm)
                    height = height or width
            return Image(path, width=width, height=height)
    except Exception:
        pass
    return Spacer(width or 1, height or 1)


def _logo_dims(path, height):
    """
    Return (width, height) for the given logo file scaled to the requested
    height while preserving its native aspect ratio. Falls back to (height,
    height) — i.e. a square — if PIL cannot read the file.
    """
    try:
        with PILImage.open(path) as im:
            nat_w, nat_h = im.size
        return height * (nat_w / nat_h), height
    except Exception:
        return height, height


# ─────────────────────────────────────────────────────────────────────────────
# Amount → French words ("cinquante mille Dinars Algériens")
# ─────────────────────────────────────────────────────────────────────────────

_UNITS = ['', 'un', 'deux', 'trois', 'quatre', 'cinq', 'six', 'sept', 'huit',
          'neuf', 'dix', 'onze', 'douze', 'treize', 'quatorze', 'quinze',
          'seize', 'dix-sept', 'dix-huit', 'dix-neuf']
_TENS  = ['', '', 'vingt', 'trente', 'quarante', 'cinquante', 'soixante',
          'soixante', 'quatre-vingt', 'quatre-vingt']


def _num_below_100(n):
    if n < 20:
        return _UNITS[n]
    t, u = divmod(n, 10)
    if t in (7, 9):
        base = _TENS[t]
        u += 10
        return base + ('-' if u != 11 or t != 7 else ' et ') + _UNITS[u]
    if u == 0:
        return _TENS[t] + ('s' if t == 8 else '')
    if u == 1 and t in (2, 3, 4, 5, 6):
        return _TENS[t] + ' et un'
    return _TENS[t] + '-' + _UNITS[u]


def _num_below_1000(n):
    if n < 100:
        return _num_below_100(n)
    h, r = divmod(n, 100)
    if h == 1:
        return 'cent' + ((' ' + _num_below_100(r)) if r else '')
    suffix = '' if r else 's'
    return _UNITS[h] + ' cent' + suffix + ((' ' + _num_below_100(r)) if r else '')


def num_to_french_words(amount):
    """Convert a number to French words (integer part only)."""
    try:
        n = int(Decimal(str(amount)))
    except Exception:
        return ''
    if n == 0:
        return 'zéro'
    if n < 0:
        return 'moins ' + num_to_french_words(-n)

    parts = []
    billion, n  = divmod(n, 1_000_000_000)
    million, n  = divmod(n, 1_000_000)
    thousand, r = divmod(n, 1_000)

    if billion:
        parts.append((_num_below_1000(billion) + ' milliard' + ('s' if billion > 1 else '')))
    if million:
        parts.append((_num_below_1000(million) + ' million' + ('s' if million > 1 else '')))
    if thousand:
        if thousand == 1:
            parts.append('mille')
        else:
            w = _num_below_1000(thousand)
            # "mille" never takes 's'
            if w.endswith('cents'):
                w = w[:-1]
            parts.append(w + ' mille')
    if r:
        parts.append(_num_below_1000(r))

    return ' '.join(parts).strip()

# ─────────────────────────────────────────────────────────────────────────────
# Colour palette
# ─────────────────────────────────────────────────────────────────────────────
NAVY       = colors.HexColor('#1B3A6B')
NAVY_LIGHT = colors.HexColor('#2452A0')
ORANGE     = colors.HexColor('#E97316')
ROW_GRAY   = colors.HexColor('#F7F9FC')
BORDER     = colors.HexColor('#E2E8F0')
TEXT_GRAY  = colors.HexColor('#64748B')
GREEN      = colors.HexColor('#16A34A')
RED        = colors.HexColor('#DC2626')
WHITE      = colors.white
BLACK      = colors.black


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def fmt_amount(value):
    try:
        return '{:,.2f} DA'.format(float(value)).replace(',', ' ')
    except (TypeError, ValueError):
        return '0.00 DA'


def fmt_date(value):
    if value is None:
        return '—'
    if hasattr(value, 'strftime'):
        return value.strftime('%d/%m/%Y')
    return str(value)


def generate_qr_png(data: str) -> io.BytesIO:
    """Return a BytesIO containing the QR code as PNG."""
    qr = qrcode.QRCode(version=1, box_size=8, border=3,
                       error_correction=qrcode.constants.ERROR_CORRECT_L)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf


# ─────────────────────────────────────────────────────────────────────────────
# Shared styles
# ─────────────────────────────────────────────────────────────────────────────

def _style(name, **kw):
    base = dict(fontName='Helvetica', fontSize=10, leading=14,
                textColor=BLACK, alignment=TA_LEFT)
    base.update(kw)
    return ParagraphStyle(name, **base)


STYLES = {
    'h1':      _style('h1', fontName='Helvetica-Bold', fontSize=16,
                      textColor=WHITE, alignment=TA_CENTER, leading=20),
    'h2':      _style('h2', fontName='Helvetica-Bold', fontSize=13,
                      textColor=NAVY, leading=16),
    'sub':     _style('sub', fontSize=9, textColor=TEXT_GRAY, leading=12),
    'body':    _style('body', fontSize=10, leading=14),
    'bold':    _style('bold', fontName='Helvetica-Bold', fontSize=10, leading=14),
    'small':   _style('small', fontSize=8, textColor=TEXT_GRAY, leading=11),
    'amount':  _style('amount', fontName='Helvetica-Bold', fontSize=11,
                      textColor=NAVY, alignment=TA_RIGHT),
    'center':  _style('center', alignment=TA_CENTER),
    'right':   _style('right', alignment=TA_RIGHT),
    'th':      _style('th', fontName='Helvetica-Bold', fontSize=9,
                      textColor=WHITE, alignment=TA_CENTER, leading=12),
    'td':      _style('td', fontSize=9, leading=12),
    'td_c':    _style('td_c', fontSize=9, leading=12, alignment=TA_CENTER),
    'td_r':    _style('td_r', fontSize=9, leading=12, alignment=TA_RIGHT),
    'green':   _style('green', fontName='Helvetica-Bold', textColor=GREEN),
    'red':     _style('red',   fontName='Helvetica-Bold', textColor=RED),
}

TABLE_HEADER_STYLE = TableStyle([
    ('BACKGROUND',  (0, 0), (-1, 0), NAVY),
    ('TEXTCOLOR',   (0, 0), (-1, 0), WHITE),
    ('FONTNAME',    (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE',    (0, 0), (-1, 0), 9),
    ('ALIGN',       (0, 0), (-1, 0), 'CENTER'),
    ('VALIGN',      (0, 0), (-1, -1), 'MIDDLE'),
    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, ROW_GRAY]),
    ('FONTSIZE',    (0, 1), (-1, -1), 9),
    ('GRID',        (0, 0), (-1, -1), 0.5, BORDER),
    ('LEFTPADDING',  (0, 0), (-1, -1), 8),
    ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ('TOPPADDING',   (0, 0), (-1, -1), 6),
    ('BOTTOMPADDING',(0, 0), (-1, -1), 6),
])


def _totals_row_style(table_style, row_index):
    """Append a navy totals-row style to an existing TableStyle."""
    extra = [
        ('BACKGROUND',  (0, row_index), (-1, row_index), NAVY),
        ('TEXTCOLOR',   (0, row_index), (-1, row_index), WHITE),
        ('FONTNAME',    (0, row_index), (-1, row_index), 'Helvetica-Bold'),
    ]
    cmds = list(table_style._cmds) + extra
    return TableStyle(cmds)


# ─────────────────────────────────────────────────────────────────────────────
# Company header (reusable)
# ─────────────────────────────────────────────────────────────────────────────

def _company_header(subtitle: str = '', city_date: str = None) -> list:
    """
    Letterhead matching DEPENSES.docx:
      ┌──────────────────────────────────────────────────────────┐
      │   [SARL.png]                              [SCK]  [ISO]   │
      │                                                          │
      │                         Ouargla le DD/MM/YYYY            │
      │                                                          │
      │  ─────────────────────────────────────────────────────   │
      │                       SUBTITLE (optional)                │
      └──────────────────────────────────────────────────────────┘
    """
    # Target heights — SARL slightly taller than the badges so the row
    # reads as a logo + two certifications cluster.
    SARL_H = 1.6 * cm
    BADGE_H = 1.3 * cm

    # Compute aspect-correct widths from the source PNGs
    sarl_w, sarl_h = _logo_dims(LOGO_SARL, SARL_H)
    sck_w,  sck_h  = _logo_dims(LOGO_SCK,  BADGE_H)
    iso_w,  iso_h  = _logo_dims(LOGO_ISO,  BADGE_H)

    sarl = _safe_image(LOGO_SARL, width=sarl_w, height=sarl_h)
    sck  = _safe_image(LOGO_SCK,  width=sck_w,  height=sck_h)
    iso  = _safe_image(LOGO_ISO,  width=iso_w,  height=iso_h)

    # Right cluster: SCK + ISO side by side, each column sized to its logo
    # plus a tiny gutter so the two badges sit cleanly next to each other.
    GUTTER = 3  # points
    right_cluster = Table(
        [[sck, iso]],
        colWidths=[sck_w + GUTTER, iso_w + GUTTER],
    )
    right_cluster.setStyle(TableStyle([
        ('ALIGN',  (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING',  (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING',   (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 0),
    ]))

    right_cluster_w = sck_w + iso_w + 2 * GUTTER

    # 3-column header row.
    #  - Left  column: just wide enough for the SARL logo (plus a small pad).
    #  - Right column: just wide enough for the SCK + ISO cluster.
    #  - Middle column: stretches to fill the remaining usable width (~18cm).
    PAGE_CONTENT_W = 18 * cm
    left_col_w = sarl_w + 4
    right_col_w = right_cluster_w + 4
    mid_col_w = max(1 * cm, PAGE_CONTENT_W - left_col_w - right_col_w)

    head = Table(
        [[sarl, '', right_cluster]],
        colWidths=[left_col_w, mid_col_w, right_col_w],
        rowHeights=[SARL_H + 4],
    )
    head.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN',  (0, 0), (0, 0), 'LEFT'),
        ('ALIGN',  (2, 0), (2, 0), 'RIGHT'),
        ('LEFTPADDING',  (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING',   (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 0),
    ]))

    out = [head, Spacer(1, 2 * mm)]

    # City + date line (right-aligned)
    if city_date is None:
        city_date = "Ouargla le " + timezone.now().strftime('%d / %m / %Y')
    out.append(Paragraph(city_date,
                         _style('city_date', fontSize=10, alignment=TA_RIGHT,
                                textColor=BLACK, leading=13)))

    # Subtitle banner (slimmer)
    if subtitle:
        sub = Table([[Paragraph(subtitle,
                                _style('sub_title', fontName='Helvetica-Bold',
                                       fontSize=12, textColor=WHITE,
                                       alignment=TA_CENTER, leading=14))]],
                    colWidths=[18 * cm])
        sub.setStyle(TableStyle([
            ('BACKGROUND',   (0, 0), (-1, -1), NAVY),
            ('TOPPADDING',   (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING',(0, 0), (-1, -1), 4),
        ]))
        out += [Spacer(1, 3 * mm), sub]

    out += [Spacer(1, 3 * mm),
            HRFlowable(width='100%', thickness=1, color=NAVY),
            Spacer(1, 5 * mm)]
    return out


def _qr_footer(data: str, label: str = '') -> list:
    """Single small QR code centered at the bottom of the document."""
    try:
        buf = generate_qr_png(data)
        qr = Image(buf, width=2.2 * cm, height=2.2 * cm)
    except Exception:
        return []
    centered = Table([[qr]], colWidths=[2.2 * cm])
    centered.setStyle(TableStyle([
        ('ALIGN',  (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING',  (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING',   (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 0),
    ]))
    wrap = Table([[centered]], colWidths=[18 * cm])
    wrap.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN',(0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING',  (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING',   (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 0),
    ]))
    return [Spacer(1, 8 * mm), wrap]


def _build_pdf(flowables: list, pagesize=A4,
               top=1.5*cm, bottom=1.5*cm,
               left=1.5*cm, right=1.5*cm) -> bytes:
    """Compile flowables into a PDF and return the bytes."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=pagesize,
        topMargin=top, bottomMargin=bottom,
        leftMargin=left, rightMargin=right,
    )

    def _footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 7)
        canvas.setFillColor(TEXT_GRAY)
        w, _ = pagesize
        canvas.drawCentredString(
            w / 2, 0.8 * cm,
            f'EURL E.C.H SAHRA  |  Page {doc.page}  |  '
            f'Généré le {timezone.now().strftime("%d/%m/%Y à %H:%M")}'
        )
        canvas.restoreState()

    doc.build(flowables, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


def _info_table(rows: list, col_widths=None) -> Table:
    """Build a two-column key/value info table."""
    if col_widths is None:
        col_widths = [5 * cm, 12.5 * cm]
    data = [[Paragraph(f'<b>{k}</b>', STYLES['td']),
             Paragraph(str(v) if v is not None else '—', STYLES['td'])]
            for k, v in rows]
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ('VALIGN',      (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING',  (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING',(0, 0), (-1, -1), 4),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [WHITE, ROW_GRAY]),
        ('GRID',        (0, 0), (-1, -1), 0.3, BORDER),
    ]))
    return t


# ─────────────────────────────────────────────────────────────────────────────
# 1. Bon de Livraison
# ─────────────────────────────────────────────────────────────────────────────

def generate_bl_pdf(bon) -> bytes:
    qr_data = (f"BL: {bon.bl_number}\nProjet: {bon.project.name}\n"
               f"Date: {fmt_date(bon.created_at)}\n"
               f"Par: {bon.created_by.get_full_name() if bon.created_by else 'N/A'}")
    qr_img = Image(generate_qr_png(qr_data), width=3 * cm, height=3 * cm)

    flowables = _company_header('BON DE LIVRAISON')

    # Header row: info + QR
    info = _info_table([
        ("N° BL",      bon.bl_number),
        ("Projet",     bon.project.name),
        ("Date",       fmt_date(bon.created_at)),
        ("Créé par",   bon.created_by.get_full_name() if bon.created_by else '—'),
    ], col_widths=[4 * cm, 9 * cm])

    header_table = Table([[info, qr_img]], colWidths=[14 * cm, 4 * cm])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    flowables.append(header_table)
    flowables.append(Spacer(1, 6 * mm))

    # Addresses
    addr_data = [
        [Paragraph('<b>Adresse d\'origine</b>', STYLES['th']),
         Paragraph('<b>Adresse de destination</b>', STYLES['th'])],
        [Paragraph(bon.origin_address or '—', STYLES['td']),
         Paragraph(bon.destination_address or '—', STYLES['td'])],
    ]
    addr_table = Table(addr_data, colWidths=[9 * cm, 9 * cm])
    addr_table.setStyle(TableStyle([
        ('BACKGROUND',   (0, 0), (-1, 0), NAVY),
        ('TEXTCOLOR',    (0, 0), (-1, 0), WHITE),
        ('GRID',         (0, 0), (-1, -1), 0.5, BORDER),
        ('TOPPADDING',   (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 6),
        ('LEFTPADDING',  (0, 0), (-1, -1), 8),
    ]))
    flowables.append(addr_table)
    flowables.append(Spacer(1, 6 * mm))

    # Items table
    items_data = [[
        Paragraph('<b>Désignation</b>', STYLES['th']),
        Paragraph('<b>Qté</b>', STYLES['th']),
        Paragraph('<b>P.U. (DA)</b>', STYLES['th']),
        Paragraph('<b>Total (DA)</b>', STYLES['th']),
    ]]
    for item in bon.items.all():
        up = fmt_amount(item.unit_price) if item.unit_price else '—'
        tp = fmt_amount(item.total_price) if item.total_price else '—'
        items_data.append([
            Paragraph(item.product.name, STYLES['td']),
            Paragraph(str(item.quantity), STYLES['td_c']),
            Paragraph(up, STYLES['td_r']),
            Paragraph(tp, STYLES['td_r']),
        ])

    for charge in bon.additional_charges.all():
        items_data.append([
            Paragraph(f'<i>{charge.description}</i>', STYLES['td']),
            Paragraph('', STYLES['td_c']),
            Paragraph('', STYLES['td_r']),
            Paragraph(fmt_amount(charge.amount), STYLES['td_r']),
        ])

    # Totals row
    items_data.append([
        Paragraph('<b>TOTAL</b>', STYLES['th']),
        '', '',
        Paragraph(fmt_amount(bon.total_amount), STYLES['th']),
    ])
    style = _totals_row_style(TABLE_HEADER_STYLE, len(items_data) - 1)
    items_table = Table(items_data, colWidths=[8 * cm, 2 * cm, 4 * cm, 4 * cm])
    items_table.setStyle(style)
    flowables.append(items_table)
    flowables.append(Spacer(1, 6 * mm))

    # Payment info
    mode = bon.get_payment_method_display() if bon.payment_method else '—'
    payment_rows = [("Mode de paiement", mode)]
    if bon.nom_fournisseur:
        payment_rows.append(("Fournisseur", bon.nom_fournisseur))
    if bon.banque:
        payment_rows.append(("Banque", bon.banque))
    if bon.numero_cheque:
        payment_rows.append(("N° chèque", bon.numero_cheque))
    flowables.append(Paragraph('<b>Informations de paiement</b>', STYLES['h2']))
    flowables.append(Spacer(1, 2 * mm))
    flowables.append(_info_table(payment_rows))
    flowables.append(Spacer(1, 1 * cm))

    # Signatures
    sig_data = [['Le fournisseur', 'Le responsable', 'Le directeur'],
                [' ' * 40, ' ' * 40, ' ' * 40]]
    sig_table = Table(sig_data, colWidths=[6 * cm, 6 * cm, 6 * cm])
    sig_table.setStyle(TableStyle([
        ('FONTNAME',     (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN',        (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING',   (0, 1), (-1, 1), 25),
        ('LINEABOVE',    (0, 1), (-1, 1), 0.5, BLACK),
    ]))
    flowables.append(sig_table)

    # QR code at the end
    flowables += _qr_footer(
        f"BL: {bon.bl_number}\nProjet: {bon.project.name}\n"
        f"Total: {fmt_amount(bon.total_amount)}\nDate: {fmt_date(bon.created_at)}"
    )

    return _build_pdf(flowables)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Bon de Commande
# ─────────────────────────────────────────────────────────────────────────────

def generate_bc_pdf(bon) -> bytes:
    qr_data = (f"BC: {bon.bc_number}\nDate: {bon.date_commande}\n"
               f"Total HT: {bon.total_ht} DA")
    qr_img = Image(generate_qr_png(qr_data), width=3 * cm, height=3 * cm)

    flowables = _company_header('BON DE COMMANDE')

    info = _info_table([
        ("N° BC",      bon.bc_number),
        ("Date",       str(bon.date_commande)),
        ("Doit",       bon.doit or '—'),
        ("Créé par",   bon.created_by.username if bon.created_by else '—'),
    ], col_widths=[4 * cm, 9 * cm])
    header_table = Table([[info, qr_img]], colWidths=[14 * cm, 4 * cm])
    header_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                       ('LEFTPADDING', (0, 0), (-1, -1), 0),
                                       ('RIGHTPADDING', (0, 0), (-1, -1), 0)]))
    flowables.append(header_table)
    flowables.append(Spacer(1, 6 * mm))

    items_data = [[
        Paragraph('<b>Désignation</b>', STYLES['th']),
        Paragraph('<b>Qté</b>', STYLES['th']),
        Paragraph('<b>P.U. HT (DA)</b>', STYLES['th']),
        Paragraph('<b>Montant HT (DA)</b>', STYLES['th']),
    ]]
    for item in bon.items.all():
        items_data.append([
            Paragraph(item.designation or item.product.name, STYLES['td']),
            Paragraph(str(item.quantity), STYLES['td_c']),
            Paragraph(fmt_amount(item.prix_unitaire), STYLES['td_r']),
            Paragraph(fmt_amount(item.montant_ht), STYLES['td_r']),
        ])
    items_data.append([
        Paragraph('<b>TOTAL HT</b>', STYLES['th']), '', '',
        Paragraph(fmt_amount(bon.total_ht), STYLES['th']),
    ])
    style = _totals_row_style(TABLE_HEADER_STYLE, len(items_data) - 1)
    items_table = Table(items_data, colWidths=[8 * cm, 2 * cm, 4 * cm, 4 * cm])
    items_table.setStyle(style)
    flowables.append(items_table)
    flowables.append(Spacer(1, 1 * cm))

    sig_data = [['Le fournisseur', 'Le responsable', 'Le directeur'],
                [' ' * 40, ' ' * 40, ' ' * 40]]
    sig_table = Table(sig_data, colWidths=[6 * cm, 6 * cm, 6 * cm])
    sig_table.setStyle(TableStyle([
        ('FONTNAME',  (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN',     (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING',(0, 1), (-1, 1), 25),
        ('LINEABOVE', (0, 1), (-1, 1), 0.5, BLACK),
    ]))
    flowables.append(sig_table)

    # QR code at the end
    flowables += _qr_footer(
        f"BC: {bon.bc_number}\nDoit: {bon.doit or '—'}\n"
        f"Total HT: {fmt_amount(bon.total_ht)}\nDate: {bon.date_commande}"
    )
    return _build_pdf(flowables)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Ordre de Mission
# ─────────────────────────────────────────────────────────────────────────────

def generate_ordre_mission_pdf(mission) -> bytes:
    qr_data = (f"Mission: {mission.numero}\nAgent: {mission.nom_prenom}\n"
               f"Destination: {mission.destination}\nDépart: {mission.date_depart}")
    qr_img = Image(generate_qr_png(qr_data), width=3 * cm, height=3 * cm)

    flowables = _company_header('ORDRE DE MISSION')

    info_rows = [
        ("N°",            mission.numero),
        ("Date",          timezone.now().strftime('%d/%m/%Y')),
        ("Nom & Prénom",  mission.nom_prenom),
        ("Fonction",      mission.fonction),
        ("Adresse",       mission.adresse),
        ("Matricule",     mission.matricule +
                          (f' / {mission.matricule_2}' if mission.matricule_2 else '')),
    ]
    info = _info_table(info_rows, col_widths=[4 * cm, 9 * cm])
    header_table = Table([[info, qr_img]], colWidths=[14 * cm, 4 * cm])
    header_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                       ('LEFTPADDING', (0, 0), (-1, -1), 0),
                                       ('RIGHTPADDING', (0, 0), (-1, -1), 0)]))
    flowables.append(header_table)
    flowables.append(Spacer(1, 6 * mm))
    flowables.append(HRFlowable(width='100%', thickness=1, color=BORDER))
    flowables.append(Spacer(1, 4 * mm))

    date_retour_str = fmt_date(mission.date_retour) if mission.date_retour else 'Non définie'
    date_depart_str = fmt_date(mission.date_depart)
    mission_rows = [
        ("Destination",           mission.destination),
        ("Motif",                 mission.motif),
        ("Moyen de déplacement",  mission.moyen_deplacement),
        ("Date de départ",        date_depart_str),
        ("Date de retour",        date_retour_str),
        ("Accompagné par",        mission.accompagne_par or '—'),
    ]
    # Mission detail box
    mission_box = Table(
        [[Paragraph(f'<b>{k} :</b>', STYLES['td']),
          Paragraph(str(v), STYLES['td'])]
         for k, v in mission_rows],
        colWidths=[5 * cm, 12 * cm]
    )
    mission_box.setStyle(TableStyle([
        ('BACKGROUND',   (0, 0), (-1, -1), ROW_GRAY),
        ('BOX',          (0, 0), (-1, -1), 1, NAVY),
        ('INNERGRID',    (0, 0), (-1, -1), 0.3, BORDER),
        ('VALIGN',       (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING',   (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 6),
        ('LEFTPADDING',  (0, 0), (-1, -1), 10),
    ]))
    flowables.append(mission_box)
    flowables.append(Spacer(1, 1.5 * cm))

    sig_data = [["L'intéressé(e)", 'Le responsable RH', 'Le directeur général'],
                [' ' * 40, ' ' * 40, ' ' * 40]]
    sig_table = Table(sig_data, colWidths=[6 * cm, 6 * cm, 6 * cm])
    sig_table.setStyle(TableStyle([
        ('FONTNAME',  (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN',     (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING',(0, 1), (-1, 1), 28),
        ('LINEABOVE', (0, 1), (-1, 1), 0.5, BLACK),
    ]))
    flowables.append(sig_table)

    # QR code at the end
    flowables += _qr_footer(
        f"Mission: {mission.numero}\nAgent: {mission.nom_prenom}\n"
        f"Destination: {mission.destination}\nDépart: {mission.date_depart}"
    )
    return _build_pdf(flowables)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Caisse History Report
# ─────────────────────────────────────────────────────────────────────────────

def generate_caisse_history_pdf(history_with_context, context_data: dict) -> bytes:
    report_title = context_data.get('report_title', 'Historique des Opérations de Caisse')
    period       = context_data.get('period_display', 'Toutes les opérations')
    generated_by = context_data.get('generated_by')
    total_enc    = context_data.get('total_encaissements', 0)
    total_dec    = context_data.get('total_decaissements', 0)
    solde_net    = context_data.get('solde_net', 0)
    total_ops    = context_data.get('total_operations', 0)
    qr_b64       = context_data.get('qr_code_base64', '')

    flowables = _company_header()

    # Title block
    flowables.append(Paragraph(report_title, STYLES['h2']))
    by_str = ''
    if generated_by:
        by_str = f" par {generated_by.get_full_name() or generated_by.username}"
    flowables.append(Paragraph(
        f'Période : {period}  |  Généré le {timezone.now().strftime("%d/%m/%Y à %H:%M")}{by_str}',
        STYLES['sub']
    ))
    flowables.append(Spacer(1, 5 * mm))

    # Summary stats
    summary_data = [[
        Paragraph('<b>Total encaissements</b>', STYLES['th']),
        Paragraph('<b>Total décaissements</b>', STYLES['th']),
        Paragraph('<b>Solde net</b>', STYLES['th']),
        Paragraph('<b>Nb opérations</b>', STYLES['th']),
    ], [
        Paragraph(fmt_amount(total_enc), STYLES['td_c']),
        Paragraph(fmt_amount(total_dec), STYLES['td_c']),
        Paragraph(fmt_amount(solde_net), STYLES['td_c']),
        Paragraph(str(total_ops), STYLES['td_c']),
    ]]
    summary_table = Table(summary_data, colWidths=[4.5 * cm, 4.5 * cm, 4.5 * cm, 4 * cm])
    summary_table.setStyle(TABLE_HEADER_STYLE)
    flowables.append(summary_table)

    # QR code if available
    if qr_b64:
        try:
            qr_bytes = base64.b64decode(qr_b64)
            qr_img = Image(io.BytesIO(qr_bytes), width=2.5 * cm, height=2.5 * cm)
            flowables.append(Spacer(1, 3 * mm))
            flowables.append(qr_img)
        except Exception:
            pass

    flowables.append(Spacer(1, 5 * mm))

    # Operations table
    ops_data = [[
        Paragraph('<b>N°</b>', STYLES['th']),
        Paragraph('<b>Date</b>', STYLES['th']),
        Paragraph('<b>Type</b>', STYLES['th']),
        Paragraph('<b>Montant</b>', STYLES['th']),
        Paragraph('<b>Solde après</b>', STYLES['th']),
        Paragraph('<b>Description</b>', STYLES['th']),
    ]]
    for item in history_with_context:
        entry = item['entry']
        date_str = fmt_date(entry.date)
        action = str(entry.action).capitalize()
        if entry.action == 'encaissement':
            action_para = Paragraph(f'<font color="#16A34A"><b>{action}</b></font>', STYLES['td_c'])
        else:
            action_para = Paragraph(f'<font color="#DC2626"><b>{action}</b></font>', STYLES['td_c'])
        desc = (entry.description or '—')[:50]
        ops_data.append([
            Paragraph(str(entry.numero), STYLES['td_c']),
            Paragraph(date_str, STYLES['td_c']),
            action_para,
            Paragraph(fmt_amount(entry.amount), STYLES['td_r']),
            Paragraph(fmt_amount(entry.balance_after), STYLES['td_r']),
            Paragraph(desc, STYLES['td']),
        ])

    if len(ops_data) == 1:
        ops_data.append([Paragraph('Aucune opération trouvée', STYLES['td_c'])] + [''] * 5)

    ops_table = Table(ops_data,
                      colWidths=[2 * cm, 2.5 * cm, 3 * cm, 3 * cm, 3 * cm, None])
    ops_table.setStyle(TABLE_HEADER_STYLE)
    flowables.append(ops_table)

    # QR code at the end
    flowables += _qr_footer(
        f"{report_title}\nPériode: {period}\n"
        f"Encaissements: {fmt_amount(total_enc)}\nDécaissements: {fmt_amount(total_dec)}\n"
        f"Solde net: {fmt_amount(solde_net)}"
    )
    return _build_pdf(flowables)


# ─────────────────────────────────────────────────────────────────────────────
# 5. Single Operation Detail
# ─────────────────────────────────────────────────────────────────────────────

def generate_operation_pdf(history_entry, generated_by=None) -> bytes:
    """
    'Bon de Dépense' / 'Bon d'Encaissement' slip matching DEPENSES.docx layout.

    Layout:
      • Header: [SARL.png left]   [SCK + ISO right]
      • "Ouargla le DD / MM / YYYY"  (right-aligned)
      • Banner: "DEPENSE N° XX/YYYY" or "ENCAISSEMENT N° XX/YYYY"
      • Body (left-aligned, line-by-line):
          Bénéficiaire : NAME
          Fonction     : ROLE
          Somme        : 50 000.00 DA
          En lettre    : cinquante mille Dinars Algériens
          Date         : 05/05/2026
          Motif        : ...
          [Projet     : XXX]
      • Signatures: "Donneur." (left) / "Le Bénéficiaire :" (right)
      • Footer: QR code with operation reference
    """
    op = history_entry.operation
    is_enc = history_entry.action == 'encaissement'

    # Extract the document number "100/2026" from the ECH numero if possible
    year = (history_entry.date.year if history_entry.date else timezone.now().year)
    doc_num = history_entry.numero or ''
    if doc_num.upper().startswith('ECH'):
        try:
            doc_num = f"{int(doc_num[3:])}/{year}"
        except (ValueError, TypeError):
            pass

    title = ('ENCAISSEMENT' if is_enc else 'DÉPENSE') + f' N° {doc_num}'
    city_date = "Ouargla le " + (
        history_entry.date.strftime('%d / %m / %Y') if history_entry.date
        else timezone.now().strftime('%d / %m / %Y')
    )

    flowables = _company_header(subtitle=title, city_date=city_date)

    # Beneficiary / function — derive from operation context
    beneficiary = ''
    fonction = ''
    if op:
        if op.nom_fournisseur:
            beneficiary = op.nom_fournisseur
        elif op.dette and getattr(op.dette, 'creditor_name', None):
            beneficiary = op.dette.creditor_name
    if not beneficiary and history_entry.project and history_entry.project.collaborator_name:
        beneficiary = history_entry.project.collaborator_name
    if not beneficiary:
        beneficiary = (history_entry.user.get_full_name()
                       if history_entry.user else '—')

    project_name = history_entry.project.name if history_entry.project else ''
    if project_name and not fonction:
        # Use project as fonction context when nothing else
        fonction = 'Projet ' + project_name

    # Amount formatting
    amount_num = '{:,.2f}'.format(float(history_entry.amount or 0)).replace(',', ' ') + ' DA'
    amount_words = num_to_french_words(history_entry.amount or 0) + ' Dinars Algériens'
    amount_words = amount_words.capitalize()

    date_str = (history_entry.date.strftime('%d/%m/%Y')
                if history_entry.date else '—')

    motif = (history_entry.description or
             (op.description if op else '') or
             ('Avance sur situation' if not is_enc else 'Encaissement'))

    # Field rows — DEPENSES.docx style (key : value, generous spacing)
    label_style = _style('dep_lbl', fontName='Helvetica-Bold', fontSize=12,
                         textColor=BLACK, leading=22)
    value_style = _style('dep_val', fontName='Helvetica', fontSize=12,
                         textColor=BLACK, leading=22)
    amount_style = _style('dep_amount', fontName='Helvetica-Bold', fontSize=13,
                          textColor=NAVY, leading=22)
    words_style = _style('dep_words', fontName='Helvetica-Oblique', fontSize=12,
                         textColor=TEXT_GRAY, leading=20)

    body_rows = [
        [Paragraph('<b>Bénéficiaire :</b>', label_style),
         Paragraph(beneficiary, value_style)],
        [Paragraph('<b>Fonction :</b>', label_style),
         Paragraph(fonction or '—', value_style)],
        [Paragraph('<b>Somme :</b>', label_style),
         Paragraph(amount_num, amount_style)],
        [Paragraph('<b>En lettre :</b>', label_style),
         Paragraph(amount_words, words_style)],
        [Paragraph('<b>Date :</b>', label_style),
         Paragraph(date_str, value_style)],
        [Paragraph('<b>Motif :</b>', label_style),
         Paragraph(motif, value_style)],
    ]
    if project_name:
        body_rows.append([Paragraph('<b>Projet :</b>', label_style),
                          Paragraph(project_name, value_style)])

    if op and op.mode_paiement:
        pay_str = op.get_mode_paiement_display()
        if op.mode_paiement == 'cheque' and op.numero_cheque:
            pay_str += f' (N° {op.numero_cheque}'
            if op.banque: pay_str += f', {op.banque}'
            pay_str += ')'
        elif op.mode_paiement == 'virement' and op.banque:
            pay_str += f' — {op.banque}'
        body_rows.append([Paragraph('<b>Mode :</b>', label_style),
                          Paragraph(pay_str, value_style)])

    body_table = Table(body_rows, colWidths=[4.5 * cm, 12.5 * cm])
    body_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING',   (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 8),
        ('LEFTPADDING',  (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('LINEBELOW',    (0, 0), (-1, -2), 0.3, colors.HexColor('#E5E7EB')),
    ]))
    flowables.append(body_table)

    # Signatures: "Donneur." (left), "Le Bénéficiaire :" (right)
    flowables.append(Spacer(1, 2 * cm))
    sig = Table(
        [[Paragraph('<b>Donneur.</b>', _style('sig', fontSize=12, leading=16)),
          '',
          Paragraph('<b>Le Bénéficiaire :</b>', _style('sig2', fontSize=12, leading=16, alignment=TA_RIGHT))]],
        colWidths=[7 * cm, 4 * cm, 7 * cm]
    )
    sig.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING',  (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    flowables.append(sig)
    flowables.append(Spacer(1, 2 * cm))

    # QR code at the end
    qr_data = (
        f"EURL E.C.H SAHRA\n"
        f"{title}\n"
        f"Bénéficiaire: {beneficiary}\n"
        f"Montant: {amount_num}\n"
        f"Date: {date_str}"
    )
    qr_label = Paragraph(
        f"<b>{title}</b><br/>"
        f"<font size='9'>Bénéficiaire : {beneficiary}</font><br/>"
        f"<font size='9' color='#1B3A6B'><b>{amount_num}</b></font><br/>"
        f"<font size='8' color='#64748B'>Émis le {timezone.now().strftime('%d/%m/%Y à %H:%M')}</font>",
        _style('qrl', fontSize=10, alignment=TA_RIGHT, leading=15)
    )
    flowables += _qr_footer(qr_data, label=None)

    return _build_pdf(flowables)


# ─────────────────────────────────────────────────────────────────────────────
# 6. Project Info PDF  (label / sticker — small page)
# ─────────────────────────────────────────────────────────────────────────────

def generate_project_info_pdf(project) -> bytes:
    from reportlab.lib.pagesizes import landscape
    page = (10 * cm, 7 * cm)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=page,
                            topMargin=0.5*cm, bottomMargin=0.5*cm,
                            leftMargin=0.5*cm, rightMargin=0.5*cm)

    styles = []

    # Banner
    banner = Table([[Paragraph('E.C.H SAHRA  —  FICHE PROJET',
                                _style('bl', fontName='Helvetica-Bold', fontSize=10,
                                       textColor=WHITE, alignment=TA_CENTER))]],
                   colWidths=[9 * cm])
    banner.setStyle(TableStyle([
        ('BACKGROUND',   (0, 0), (-1, -1), NAVY),
        ('TOPPADDING',   (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 6),
    ]))
    styles.append(banner)
    styles.append(Spacer(1, 3 * mm))

    date_debut_str = fmt_date(project.date_debut) if project.date_debut else '—'
    rows = [
        ("Projet",       project.name),
        ("Opération",    project.operation or '—'),
        ("N° op.",       project.numero_operation or '—'),
        ("Début",        date_debut_str),
        ("Durée",        f'{project.period_months or "—"} mois'),
        ("Budget",       fmt_amount(project.estimated_budget)),
        ("Collaborateur",project.collaborator_name or '—'),
    ]
    info = Table(
        [[Paragraph(f'<b>{k}</b>', _style('si', fontSize=8)),
          Paragraph(str(v), _style('sv', fontSize=8))]
         for k, v in rows],
        colWidths=[2.8 * cm, 5.8 * cm]
    )
    info.setStyle(TableStyle([
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [WHITE, ROW_GRAY]),
        ('TOPPADDING',     (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING',  (0, 0), (-1, -1), 2),
        ('LEFTPADDING',    (0, 0), (-1, -1), 4),
        ('GRID',           (0, 0), (-1, -1), 0.3, BORDER),
    ]))
    styles.append(info)

    doc.build(styles)
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# 7. Dette Journal PDF
# ─────────────────────────────────────────────────────────────────────────────

def generate_dette_journal_pdf(dette, payments) -> bytes:
    flowables = _company_header('JOURNAL DE DETTE')

    status_color = '#16A34A' if dette.status == 'completed' else '#DC2626'
    status_label = 'Soldée' if dette.status == 'completed' else 'En cours'
    date_str = fmt_date(dette.date_created) if dette.date_created else '—'

    summary_data = [[
        Paragraph('<b>Créancier</b>', STYLES['th']),
        Paragraph('<b>Statut</b>', STYLES['th']),
        Paragraph('<b>Montant initial</b>', STYLES['th']),
        Paragraph('<b>Restant</b>', STYLES['th']),
    ], [
        Paragraph(dette.creditor_name, STYLES['td_c']),
        Paragraph(f'<font color="{status_color}"><b>{status_label}</b></font>', STYLES['td_c']),
        Paragraph(fmt_amount(dette.original_amount), STYLES['td_r']),
        Paragraph(fmt_amount(dette.remaining_amount), STYLES['td_r']),
    ]]
    summary_table = Table(summary_data, colWidths=[5 * cm, 3.5 * cm, 4.5 * cm, 4.5 * cm])
    summary_table.setStyle(TABLE_HEADER_STYLE)
    flowables.append(summary_table)
    flowables.append(Spacer(1, 4 * mm))
    flowables.append(_info_table([
        ("Projet", dette.project.name if dette.project else '—'),
        ("Date de création", date_str),
    ]))
    flowables.append(Spacer(1, 6 * mm))

    pay_data = [[
        Paragraph('<b>Date</b>', STYLES['th']),
        Paragraph('<b>Montant payé</b>', STYLES['th']),
        Paragraph('<b>Mode</b>', STYLES['th']),
        Paragraph('<b>Description</b>', STYLES['th']),
    ]]
    for p in payments:
        pay_data.append([
            Paragraph(fmt_date(p.payment_date), STYLES['td_c']),
            Paragraph(fmt_amount(p.amount_paid), STYLES['td_r']),
            Paragraph(p.get_mode_paiement_display() if p.mode_paiement else '—', STYLES['td_c']),
            Paragraph(p.description or '—', STYLES['td']),
        ])
    if len(pay_data) == 1:
        pay_data.append([Paragraph('Aucun paiement enregistré', STYLES['td_c'])] + [''] * 3)

    total_paid = dette.original_amount - dette.remaining_amount
    pay_data.append([
        Paragraph('<b>Total payé</b>', STYLES['th']),
        Paragraph(fmt_amount(total_paid), STYLES['th']),
        Paragraph(f'Restant : {fmt_amount(dette.remaining_amount)}', STYLES['th']),
        Paragraph('', STYLES['th']),
    ])
    style = _totals_row_style(TABLE_HEADER_STYLE, len(pay_data) - 1)
    pay_table = Table(pay_data, colWidths=[3 * cm, 4 * cm, 4 * cm, None])
    pay_table.setStyle(style)
    flowables.append(pay_table)

    # QR code at the end
    flowables += _qr_footer(
        f"Dette: {dette.creditor_name}\nMontant: {fmt_amount(dette.original_amount)}\n"
        f"Restant: {fmt_amount(dette.remaining_amount)}"
    )
    return _build_pdf(flowables)


# ─────────────────────────────────────────────────────────────────────────────
# 8. Project Finance Summary PDF
# ─────────────────────────────────────────────────────────────────────────────

def generate_project_finance_pdf(projects) -> bytes:
    flowables = _company_header('BILAN FINANCIER DES PROJETS')
    flowables.append(Paragraph(
        f'Généré le {timezone.now().strftime("%d/%m/%Y à %H:%M")}',
        STYLES['sub']
    ))
    flowables.append(Spacer(1, 5 * mm))

    total_budget = total_dep = total_acc = total_ben = Decimal('0')
    data = [[
        Paragraph('<b>Projet</b>', STYLES['th']),
        Paragraph('<b>Budget</b>', STYLES['th']),
        Paragraph('<b>Dépenses</b>', STYLES['th']),
        Paragraph('<b>Accéances</b>', STYLES['th']),
        Paragraph('<b>Bénéfices</b>', STYLES['th']),
    ]]
    for p in projects:
        ben = p.total_benefices or Decimal('0')
        ben_color = '#16A34A' if ben >= 0 else '#DC2626'
        data.append([
            Paragraph(p.name, STYLES['td']),
            Paragraph(fmt_amount(p.estimated_budget), STYLES['td_r']),
            Paragraph(fmt_amount(p.total_depenses), STYLES['td_r']),
            Paragraph(fmt_amount(p.total_accreance), STYLES['td_r']),
            Paragraph(f'<font color="{ben_color}"><b>{fmt_amount(ben)}</b></font>', STYLES['td_r']),
        ])
        total_budget += p.estimated_budget  or Decimal('0')
        total_dep    += p.total_depenses    or Decimal('0')
        total_acc    += p.total_accreance   or Decimal('0')
        total_ben    += ben

    ben_color = '#16A34A' if total_ben >= 0 else '#DC2626'
    data.append([
        Paragraph('<b>TOTAUX</b>', STYLES['th']),
        Paragraph(fmt_amount(total_budget), STYLES['th']),
        Paragraph(fmt_amount(total_dep), STYLES['th']),
        Paragraph(fmt_amount(total_acc), STYLES['th']),
        Paragraph(f'<font color="{ben_color}"><b>{fmt_amount(total_ben)}</b></font>', STYLES['th']),
    ])
    if len(data) == 1:
        data.append([Paragraph('Aucun projet trouvé', STYLES['td_c'])] + [''] * 4)

    style = _totals_row_style(TABLE_HEADER_STYLE, len(data) - 1)
    table = Table(data, colWidths=[5 * cm, 3.5 * cm, 3.5 * cm, 3.5 * cm, 3 * cm])
    table.setStyle(style)
    flowables.append(table)

    # QR code at the end
    flowables += _qr_footer(
        f"Bilan financier — {len(projects)} projets\n"
        f"Budget total: {fmt_amount(total_budget)}\n"
        f"Bénéfices: {fmt_amount(total_ben)}"
    )
    return _build_pdf(flowables)


# ─────────────────────────────────────────────────────────────────────────────
# Backward-compat helpers expected by views.py
# ─────────────────────────────────────────────────────────────────────────────

def generate_qr_png_b64(data: str) -> str:
    """Return base64-encoded PNG string (kept for views that pass it as context)."""
    buf = generate_qr_png(data)
    return base64.b64encode(buf.read()).decode()


def escape_latex(text):
    """No-op kept for import compatibility — LaTeX is no longer used."""
    return str(text) if text is not None else ''
