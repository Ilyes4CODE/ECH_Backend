"""
ReportLab-based PDF generation for ECH SAHARA ERP.

Pure-Python — no external programs required.
Install: pip install reportlab
"""

import io
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
from django.utils import timezone

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

def _company_header(subtitle: str = '') -> list:
    """Return a list of flowables for the ECH SAHARA page header."""
    # Navy banner
    banner_data = [[Paragraph('EURL E.C.H SAHRA', STYLES['h1'])]]
    if subtitle:
        banner_data.append(
            [Paragraph(subtitle, _style('sub_white', fontSize=10, textColor=ORANGE,
                                        alignment=TA_CENTER))]
        )
    banner = Table(banner_data, colWidths=[18 * cm])
    banner.setStyle(TableStyle([
        ('BACKGROUND',   (0, 0), (-1, -1), NAVY),
        ('ALIGN',        (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING',   (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 10),
        ('LEFTPADDING',  (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('ROUNDEDCORNERS', [4]),
    ]))
    tagline = Paragraph(
        "Entreprise de Travaux de Construction Hydraulique et Génie Civil",
        _style('tagline', fontSize=8, textColor=TEXT_GRAY, alignment=TA_CENTER)
    )
    return [banner, Spacer(1, 3 * mm), tagline, Spacer(1, 4 * mm),
            HRFlowable(width='100%', thickness=1, color=BORDER), Spacer(1, 4 * mm)]


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
    return _build_pdf(flowables)


# ─────────────────────────────────────────────────────────────────────────────
# 5. Single Operation Detail
# ─────────────────────────────────────────────────────────────────────────────

def generate_operation_pdf(history_entry, generated_by=None) -> bytes:
    qr_data = f"ECH-OP-{history_entry.numero}-{history_entry.date}"
    qr_img = Image(generate_qr_png(qr_data), width=3 * cm, height=3 * cm)

    flowables = _company_header("DÉTAIL D'OPÉRATION")

    action_color = '#16A34A' if history_entry.action == 'encaissement' else '#DC2626'
    info_rows = [
        ("N°",           history_entry.numero),
        ("Date",         fmt_date(history_entry.date)),
        ("Type",         f'<font color="{action_color}"><b>{history_entry.action.capitalize()}</b></font>'),
        ("Montant",      fmt_amount(history_entry.amount)),
        ("Solde avant",  fmt_amount(history_entry.balance_before)),
        ("Solde après",  fmt_amount(history_entry.balance_after)),
        ("Effectué par", history_entry.user.get_full_name() if history_entry.user else '—'),
        ("Projet",       history_entry.project.name if history_entry.project else '—'),
        ("Description",  history_entry.description or '—'),
    ]
    info = Table(
        [[Paragraph(f'<b>{k} :</b>', STYLES['td']),
          Paragraph(str(v), STYLES['td'])]
         for k, v in info_rows],
        colWidths=[4 * cm, 9 * cm]
    )
    info.setStyle(TableStyle([
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [WHITE, ROW_GRAY]),
        ('GRID',           (0, 0), (-1, -1), 0.3, BORDER),
        ('TOPPADDING',     (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING',  (0, 0), (-1, -1), 5),
        ('LEFTPADDING',    (0, 0), (-1, -1), 6),
    ]))

    row = Table([[info, qr_img]], colWidths=[14 * cm, 4 * cm])
    row.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),
                              ('LEFTPADDING', (0, 0), (-1, -1), 0)]))
    flowables.append(row)

    op = history_entry.operation
    if op:
        flowables.append(Spacer(1, 5 * mm))
        flowables.append(HRFlowable(width='100%', thickness=0.5, color=BORDER))
        flowables.append(Spacer(1, 3 * mm))
        flowables.append(Paragraph('<b>Informations de paiement</b>', STYLES['h2']))
        pay_rows = [
            ("Mode",       op.get_mode_paiement_display() if op.mode_paiement else '—'),
            ("Fournisseur",op.nom_fournisseur or '—'),
            ("Banque",     op.banque or '—'),
            ("N° chèque",  op.numero_cheque or '—'),
            ("Source",     op.get_income_source_display() if op.income_source else '—'),
            ("Observation",op.observation or '—'),
        ]
        flowables.append(Spacer(1, 2 * mm))
        flowables.append(_info_table(pay_rows))

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
