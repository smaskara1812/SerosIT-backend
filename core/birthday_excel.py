"""Excel for the Birthday Mailer's people list: the blank template to download, and the upload.

Columns (the first row that has "Full Name" in it is the header row; extra columns are ignored):
    Full Name      required
    Display Name   optional: what is written on the card (blank = the full name)
    Birth Date     required: a real date, or text such as 15-Mar, 15 March, 15/03/1990, 1990-03-15. Day and month are used; the year is optional.
                   15/03 style is day first. 29 Feb is fine.
    Leaving Date   optional: the last day the person gets a card (blank = still here)

There is NO uniqueness rule. The one safeguard against uploading the same file twice is a tick box on the page ("Skip rows already on the list", on by
default): a row with the same full name and the same birthday (day and month) as someone already on the list, or earlier in the same file, is then
left out and reported. Switch it off and every row is added."""

import calendar
import datetime
import io
import re
import uuid

from django.utils import timezone

from .models import BirthdayPerson

MAX_ROWS = 5000
MAX_BYTES = 2 * 1024 * 1024
MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_abbr) if m}
MONTHS.update({m.lower(): i for i, m in enumerate(calendar.month_name) if m})
HEADERS = {
    "full_name": ("full name", "name", "employee name"),
    "display_name": ("display name", "shown name", "preferred name"),
    "birth": ("birth date", "date of birth", "birthday", "dob", "birth"),
    "leaving": ("leaving date", "exit date", "last working day", "date of leaving"),
}


class UploadError(Exception):
    """The whole file cannot be read (not an Excel file, no header row, too big)."""


def _norm(s):
    return re.sub(r"\s+", " ", str(s or "").strip()).casefold()


def parse_birth(value):
    """-> (month, day, year or None). Raises ValueError with a message for the person."""
    if isinstance(value, datetime.datetime):
        value = value.date()
    if isinstance(value, datetime.date):
        # a cell the user typed as "15-Mar" is stored by Excel as a date in the current year; the year is then not a real birth year
        return value.month, value.day, value.year if 1900 <= value.year <= datetime.date.today().year and value.year != datetime.date.today().year else None
    text = str(value or "").strip()
    if not text:
        raise ValueError("Birth date is required.")
    m = re.fullmatch(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", text)
    if m:
        y, mo, d = int(m[1]), int(m[2]), int(m[3])
    else:
        m = re.fullmatch(r"(\d{1,2})[-/. ]+(\d{1,2})(?:[-/. ]+(\d{2,4}))?", text)
        if m:
            d, mo = int(m[1]), int(m[2])
            y = int(m[3]) if m[3] else None
            if y is not None and y < 100:
                y += 1900 if y > datetime.date.today().year % 100 else 2000
        else:
            m = re.fullmatch(r"(\d{1,2})(?:st|nd|rd|th)?[-/. ]+([A-Za-z]{3,9})\.?(?:[-/. ,]+(\d{2,4}))?", text)
            if not m or m[2].lower() not in MONTHS:
                raise ValueError(f"Birth date '{text}' is not a date. Use a date such as 15-Mar, 15/03/1990 or 1990-03-15.")
            d, mo = int(m[1]), MONTHS[m[2].lower()]
            y = int(m[3]) if m[3] else None
            if y is not None and y < 100:
                y += 1900 if y > datetime.date.today().year % 100 else 2000
    if not 1 <= mo <= 12:
        raise ValueError(f"'{text}': the month must be 1 to 12.")
    if not 1 <= d <= calendar.monthrange(2000, mo)[1]:  # 2000 is a leap year, so 29 Feb is allowed
        raise ValueError(f"'{text}': that month does not have a day {d}.")
    if y is not None and not 1900 <= y <= datetime.date.today().year:
        y = None
    return mo, d, y


def parse_date(value, label):
    if value in (None, ""):
        return None
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    text = str(value).strip()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d-%b-%Y", "%d %b %Y", "%d %B %Y", "%d.%m.%Y"):
        try:
            return datetime.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"{label} '{text}' is not a date. Use a date such as 31/03/2026.")


def build_template():
    """The blank workbook to download: the People sheet (headers only) and an Instructions sheet."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "People"
    heads = ["Full Name", "Display Name", "Birth Date", "Leaving Date"]
    for i, h in enumerate(heads, 1):
        c = ws.cell(row=1, column=i, value=h)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", start_color="1C448A")
        ws.column_dimensions[get_column_letter(i)].width = [30, 26, 16, 16][i - 1]
    ws.freeze_panes = "A2"
    for col in ("C", "D"):
        for r in range(2, 502):
            ws[f"{col}{r}"].number_format = "DD-MMM-YYYY"
    info = wb.create_sheet("Instructions")
    lines = [
        ("Birthday Mailer: people upload", True),
        ("", False),
        ("Fill the People sheet, one person per row, starting on row 2. Delete nothing in row 1.", False),
        ("", False),
        ("Full Name (required): the person's full name.", False),
        ("Display Name (optional): what is written on the birthday card. Leave blank to use the full name.", False),
        ("Birth Date (required): a date. Only the day and the month are used; the year is optional. Accepted: a real Excel date, 15-Mar, 15 March, 15/03/1990 or 1990-03-15. A date such as 15/03 is day first. 29 February is allowed (the card goes out on 28 February in other years).", False),
        ("Leaving Date (optional): the last day the person gets a card. Leave blank while the person is still here.", False),
        ("", False),
        ("There is no unique column: every row is a person. To stop the same file being added twice, the upload page has a tick box 'Skip rows already on the list' (on by default): a row with the same full name and the same birthday as someone on the list, or earlier in the file, is then left out and reported.", False),
        ("The upload shows a report before anything is saved. Rows with a problem are listed with their row number and reason, and are left out; fix them and upload again.", False),
        (f"At most {MAX_ROWS} rows and 2 MB per file.", False),
    ]
    for i, (t, bold) in enumerate(lines, 1):
        c = info.cell(row=i, column=1, value=t)
        c.font = Font(bold=bold, size=13 if bold else 11)
        c.alignment = Alignment(wrap_text=True, vertical="top")
    info.column_dimensions["A"].width = 110
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def _find_columns(rows):
    for ri, row in enumerate(rows):
        cells = {_norm(v): ci for ci, v in enumerate(row) if v not in (None, "")}
        found = {k: next((cells[a] for a in alts if a in cells), None) for k, alts in HEADERS.items()}
        if found["full_name"] is not None:
            return ri, found
    raise UploadError("The header row was not found. The first row of the People sheet must contain 'Full Name' and 'Birth Date'.")


def read_rows(data):
    from openpyxl import load_workbook

    if len(data) > MAX_BYTES:
        raise UploadError("That file is larger than 2 MB.")
    try:
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception:
        raise UploadError("That file could not be read as an Excel (.xlsx) file.")
    ws = wb["People"] if "People" in wb.sheetnames else wb[wb.sheetnames[0]]
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    wb.close()
    head, cols = _find_columns(rows[:20])
    if cols["birth"] is None:
        raise UploadError("There is no 'Birth Date' column in the header row.")
    body = rows[head + 1 :]
    if len(body) > MAX_ROWS + 200:
        raise UploadError(f"That file has more than {MAX_ROWS} rows.")
    return head, cols, body


def process(data, dry_run=True, skip_duplicates=True, user_id=0):
    """Reads the workbook and returns a report. With dry_run=False the valid rows are saved (all in one transaction).

    {"total", "added", "skipped_duplicates", "errors": [{"row", "name", "message"}], "duplicates": [{"row","name","message"}], "preview": [first 20 valid], "batch"}"""
    from django.db import transaction

    head, cols, body = read_rows(data)
    existing = {(_norm(p.full_name), p.birth_month, p.birth_day) for p in BirthdayPerson.objects.all()}
    seen = set(existing)
    good, errors, dups = [], [], []
    for i, row in enumerate(body):
        rownum = head + 2 + i  # the Excel row number
        get = lambda k: row[cols[k]] if cols.get(k) is not None and cols[k] < len(row) else None
        name = " ".join(str(get("full_name") or "").split())
        if not name and not any(v not in (None, "") for v in row):
            continue  # an empty row
        if not name:
            errors.append({"row": rownum, "name": "", "message": "Full name is required."})
            continue
        if len(name) > 100:
            errors.append({"row": rownum, "name": name[:40], "message": "Full name is longer than 100 characters."})
            continue
        shown = " ".join(str(get("display_name") or "").split()) or None
        if shown and len(shown) > 100:
            errors.append({"row": rownum, "name": name, "message": "Display name is longer than 100 characters."})
            continue
        try:
            mo, d, y = parse_birth(get("birth"))
            leaving = parse_date(get("leaving"), "Leaving date")
        except ValueError as exc:
            errors.append({"row": rownum, "name": name, "message": str(exc)})
            continue
        key = (_norm(name), mo, d)
        if skip_duplicates and key in seen:
            dups.append({"row": rownum, "name": name, "message": "Already on the list with the same birthday." if key in existing else "Appears earlier in this file with the same birthday."})
            continue
        seen.add(key)
        good.append({"row": rownum, "full_name": name, "display_name": shown, "birth_month": mo, "birth_day": d, "birth_year": y, "leaving_date": leaving})
    batch = str(uuid.uuid4())
    if not dry_run and good:
        now = timezone.now()
        with transaction.atomic():
            BirthdayPerson.objects.bulk_create([
                BirthdayPerson(full_name=g["full_name"], display_name=g["display_name"], birth_month=g["birth_month"], birth_day=g["birth_day"], birth_year=g["birth_year"],
                               leaving_date=g["leaving_date"], source="excel", upload_batch=batch, cr_user_id=user_id or 1, cr_dt=now)
                for g in good
            ])
    return {
        "dry_run": dry_run, "total": len(good) + len(errors) + len(dups), "added": len(good), "skipped_duplicates": len(dups), "errors": errors[:200], "error_count": len(errors),
        "duplicates": dups[:200], "preview": [{k: (str(v) if isinstance(v, datetime.date) else v) for k, v in g.items()} for g in good[:20]], "batch": batch if not dry_run else "",
    }
