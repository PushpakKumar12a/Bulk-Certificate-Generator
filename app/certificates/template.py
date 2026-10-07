from datetime import date
from html import escape

def certificate_html(
    *,
    name: str,
    course: str,
    org: str,
    issue_date: date,
    number: str | None,
) -> str:
    certificate_number = number or "-"
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    @page {{ size: A4 landscape; margin: 0; }}
    body {{ margin: 0; font-family: sans-serif; color: #17324d; }}
    .certificate {{ box-sizing: border-box; height: 210mm; padding: 35mm;
      text-align: center; border: 8px solid #17324d; }}
    h1 {{ font-size: 34pt; margin: 0 0 18mm; }}
    .name {{ font-size: 28pt; font-weight: bold; margin: 12mm 0; }}
    .course {{ font-size: 18pt; }}
    .meta {{ margin-top: 18mm; font-size: 11pt; }}
  </style>
</head>
<body>
  <main class="certificate">
    <h1>Certificate of Completion</h1>
    <div>This certificate is presented to</div>
    <div class="name">{escape(name)}</div>
    <div class="course">for successfully completing <strong>{escape(course)}</strong></div>
    <div class="meta">{escape(org)} &middot; Issued {issue_date.isoformat()}
      &middot; Certificate {escape(certificate_number)}</div>
  </main>
</body>
</html>"""

def certificate_pdf(**kwargs: object) -> bytes:
    from weasyprint import HTML

    return HTML(string=certificate_html(**kwargs)).write_pdf()
