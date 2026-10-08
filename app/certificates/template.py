import io
import os
import math
from datetime import date

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import stringWidth
import reportlab


def _register_fonts():
    fonts_dir = os.path.join(
        os.path.dirname(reportlab.__file__),
        "fonts",
    )

    try:
        pdfmetrics.registerFont(
            TTFont("Vera", os.path.join(fonts_dir, "Vera.ttf"))
        )
        pdfmetrics.registerFont(
            TTFont("Vera-Bold", os.path.join(fonts_dir, "VeraBd.ttf"))
        )
        pdfmetrics.registerFont(
            TTFont("Vera-Italic", os.path.join(fonts_dir, "VeraIt.ttf"))
        )

        return "Vera", "Vera-Bold", "Vera-Italic"

    except Exception:
        return (
            "Helvetica",
            "Helvetica-Bold",
            "Helvetica-Oblique",
        )


def certificate_pdf(
    *,
    name: str = "",
    course: str = "",
    org: str = "",
    issue_date: date | None = None,
    certificate_id: str | None = None,
    **kwargs: object,
) -> bytes:
    FONT, FONT_BOLD, FONT_ITALIC = _register_fonts()

    buf = io.BytesIO()
    w, h = landscape(A4)

    c = canvas.Canvas(
        buf,
        pagesize=(w, h),
        pageCompression=1,
    )

    if certificate_id:
        c.setSubject(f"VERIFICATION ID: {certificate_id}")

    # ============================================================
    # COLORS
    # ============================================================

    paper = HexColor("#FBFAF7")
    navy = HexColor("#172554")
    blue = HexColor("#2563EB")
    gold = HexColor("#B88A3B")
    gold_light = HexColor("#D9C18C")
    text = HexColor("#1E293B")
    muted = HexColor("#64748B")
    border = HexColor("#D8D0C0")

    # ============================================================
    # BACKGROUND
    # ============================================================

    c.setFillColor(paper)
    c.rect(0, 0, w, h, fill=1, stroke=0)

    # ============================================================
    # STYLISH DOUBLE BORDER
    # ============================================================

    outer = 20
    inner = 29

    c.setStrokeColor(gold)
    c.setLineWidth(1.8)
    c.roundRect(
        outer,
        outer,
        w - outer * 2,
        h - outer * 2,
        20,
        fill=0,
        stroke=1,
    )

    c.setStrokeColor(border)
    c.setLineWidth(0.7)
    c.roundRect(
        inner,
        inner,
        w - inner * 2,
        h - inner * 2,
        15,
        fill=0,
        stroke=1,
    )

    # ============================================================
    # CURVED CORNER ORNAMENT
    # ============================================================

    def corner_ornament(x, y, sx, sy):
        c.saveState()
        c.translate(x, y)
        c.scale(sx, sy)

        c.setStrokeColor(gold)
        c.setLineWidth(1.1)

        p = c.beginPath()

        p.moveTo(0, 0)
        p.curveTo(5, 25, 25, 30, 45, 30)

        p.moveTo(8, 0)
        p.curveTo(12, 16, 25, 21, 36, 21)

        p.moveTo(0, 8)
        p.curveTo(16, 12, 21, 25, 21, 36)

        c.drawPath(p, stroke=1, fill=0)

        c.setFillColor(gold)
        c.circle(0, 0, 2.5, fill=1, stroke=0)

        c.restoreState()

    corner_ornament(inner + 5, inner + 5, 1, 1)
    corner_ornament(w - inner - 5, inner + 5, -1, 1)
    corner_ornament(inner + 5, h - inner - 5, 1, -1)
    corner_ornament(w - inner - 5, h - inner - 5, -1, -1)

    # ============================================================
    # ORGANIZATION
    # ============================================================

    organization = str(org).strip() or "YOUR ORGANIZATION"

    org_size = 11
    while (
        stringWidth(organization.upper(), FONT_BOLD, org_size)
        > w - 180
        and org_size > 7
    ):
        org_size -= 0.5

    c.setFillColor(navy)
    c.setFont(FONT_BOLD, org_size)
    c.drawCentredString(
        w / 2,
        h - 68,
        organization.upper(),
    )

    # Decorative divider
    c.setStrokeColor(gold)
    c.setLineWidth(1)

    c.line(
        w / 2 - 70,
        h - 84,
        w / 2 - 10,
        h - 84,
    )

    c.line(
        w / 2 + 10,
        h - 84,
        w / 2 + 70,
        h - 84,
    )

    c.setFillColor(gold)
    c.circle(w / 2, h - 84, 3, fill=1, stroke=0)

    # ============================================================
    # TITLE
    # ============================================================

    c.setFillColor(navy)
    c.setFont(FONT_BOLD, 31)

    c.drawCentredString(
        w / 2,
        h - 127,
        "CERTIFICATE",
    )

    c.setFillColor(gold)
    c.setFont(FONT_BOLD, 11)

    c.drawCentredString(
        w / 2,
        h - 147,
        "OF COMPLETION",
    )

    # ============================================================
    # DECORATIVE FLOURISH
    # ============================================================

    c.setStrokeColor(gold)
    c.setLineWidth(0.9)

    flourish = c.beginPath()

    flourish.moveTo(w / 2 - 145, h - 169)
    flourish.curveTo(
        w / 2 - 120, h - 154,
        w / 2 - 100, h - 184,
        w / 2 - 72, h - 169,
    )
    flourish.curveTo(
        w / 2 - 45, h - 184,
        w / 2 - 27, h - 154,
        w / 2, h - 169,
    )
    flourish.curveTo(
        w / 2 + 27, h - 184,
        w / 2 + 45, h - 154,
        w / 2 + 72, h - 169,
    )
    flourish.curveTo(
        w / 2 + 100, h - 184,
        w / 2 + 120, h - 154,
        w / 2 + 145, h - 169,
    )

    c.drawPath(flourish, stroke=1, fill=0)

    # ============================================================
    # INTRODUCTION
    # ============================================================

    c.setFillColor(muted)
    c.setFont(FONT_ITALIC, 10)

    c.drawCentredString(
        w / 2,
        h - 199,
        "This certificate is proudly presented to",
    )

    # ============================================================
    # RECIPIENT NAME
    # ============================================================

    recipient = str(name).strip() or "Recipient Name"

    name_size = 36

    while (
        stringWidth(recipient, FONT_BOLD, name_size)
        > w - 180
        and name_size > 18
    ):
        name_size -= 1

    c.setFillColor(text)
    c.setFont(FONT_BOLD, name_size)

    c.drawCentredString(
        w / 2,
        h - 241,
        recipient,
    )

    # Name underline
    name_width = stringWidth(
        recipient,
        FONT_BOLD,
        name_size,
    )

    underline = min(
        max(name_width * 0.55, 110),
        300,
    )

    c.setStrokeColor(blue)
    c.setLineWidth(1.5)

    c.line(
        w / 2 - underline / 2,
        h - 255,
        w / 2 + underline / 2,
        h - 255,
    )

    # ============================================================
    # COMPLETION TEXT
    # ============================================================

    c.setFillColor(muted)
    c.setFont(FONT, 10.5)

    c.drawCentredString(
        w / 2,
        h - 282,
        "for successfully completing the requirements for",
    )

    # ============================================================
    # COURSE
    # ============================================================

    course_text = str(course).strip() or "Course / Program Name"

    course_size = 22

    while (
        stringWidth(course_text, FONT_BOLD, course_size)
        > w - 200
        and course_size > 13
    ):
        course_size -= 0.5

    c.setFillColor(blue)
    c.setFont(FONT_BOLD, course_size)

    c.drawCentredString(
        w / 2,
        h - 315,
        course_text,
    )

    c.setFillColor(muted)
    c.setFont(FONT_ITALIC, 8.5)

    c.drawCentredString(
        w / 2,
        h - 338,
        "Issued in recognition of successful participation and completion.",
    )

    # ============================================================
    # DATE / SIGNATURE / ID
    # ============================================================

    date_str = (
        issue_date.strftime("%d %B %Y")
        if isinstance(issue_date, date)
        else str(issue_date or "-")
    )

    cert_id = str(certificate_id or "-").strip()

    bottom_y = 73

    # Date
    date_x = w / 2 - 205

    c.setStrokeColor(border)
    c.setLineWidth(0.8)
    c.line(
        date_x - 65,
        bottom_y + 24,
        date_x + 65,
        bottom_y + 24,
    )

    c.setFillColor(muted)
    c.setFont(FONT_BOLD, 6.8)
    c.drawCentredString(
        date_x,
        bottom_y + 10,
        "DATE OF ISSUE",
    )

    c.setFillColor(text)
    c.setFont(FONT_BOLD, 9)
    c.drawCentredString(
        date_x,
        bottom_y - 2,
        date_str,
    )

    # Signature
    signature_x = w / 2

    c.setStrokeColor(border)
    c.line(
        signature_x - 70,
        bottom_y + 24,
        signature_x + 70,
        bottom_y + 24,
    )

    c.setFillColor(muted)
    c.setFont(FONT_BOLD, 6.8)
    c.drawCentredString(
        signature_x,
        bottom_y + 10,
        "AUTHORIZED SIGNATURE",
    )

    # Certificate ID
    id_x = w / 2 + 205

    c.setStrokeColor(border)
    c.line(
        id_x - 75,
        bottom_y + 24,
        id_x + 75,
        bottom_y + 24,
    )

    c.setFillColor(muted)
    c.setFont(FONT_BOLD, 6.8)
    c.drawCentredString(
        id_x,
        bottom_y + 10,
        "CERTIFICATE ID",
    )

    id_size = 8

    while (
        stringWidth(cert_id, FONT_BOLD, id_size) > 145
        and id_size > 6
    ):
        id_size -= 0.5

    c.setFillColor(text)
    c.setFont(FONT_BOLD, id_size)
    c.drawCentredString(
        id_x,
        bottom_y - 2,
        cert_id,
    )

    # ============================================================
    # CENTER DECORATIVE EMBLEM
    # ============================================================

    emblem_y = 48

    c.setStrokeColor(gold)
    c.setLineWidth(1)
    c.circle(
        w / 2,
        emblem_y,
        8,
        fill=0,
        stroke=1,
    )

    c.setFillColor(gold)
    c.circle(
        w / 2,
        emblem_y,
        2.2,
        fill=1,
        stroke=0,
    )

    # ============================================================
    # SAVE
    # ============================================================

    c.save()

    return buf.getvalue()
