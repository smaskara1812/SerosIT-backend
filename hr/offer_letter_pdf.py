"""Print Offer Letter: the offer letter as a PDF, drawn with ReportLab from the saved letter (header + pay component rows).

Two templates, both onshore (category 4), chosen by the applicant's employment type:
  * employment type 21 "Per Day Rate - INR"  -> the retainer letter (a consolidated day rate = the letter's total salary, no salary table, no ON/OFF cycle);
  * any other type                            -> the Fixed Term Employment letter (salary table, ON/OFF schedule, 13 clauses).
The wording is that of the legacy Crystal Reports templates (taken from three sample PDFs: print Offer letter/*.pdf). Offshore letters (category 5: national and
expat templates) are not built yet; a letter in any other category is refused with a clear message.

What fills the letter, and how it differs from legacy where the page was asked to:
  * Camp Allowance sentence: only when the letter's Camp Allowance row is marked "show in letter"; the amount is the row's amount (not a fixed 3000). It is not in
    the table or its total.
  * Travel (clause 5): the Travel Allowance amount when the letter has one; then the Travel Eligibility text when it has one; with neither, "Not Applicable".
  * The table lists the components that count toward the total and are shown in the letter, in a fixed order; the total is their sum, which must equal the letter's
    total salary (a letter whose pay does not add up is not printed: fix it first).
  * Any other component marked "show in letter" that does not count toward the total is added as one sentence under the table.
  * Letterhead: media/Letterhead Logo/Offer_Letter_Header.jpg (top) and Offer_Letter_Footer.jpg (bottom of every page), the Seros Energy Private Limited header and footer
    (renamed from Header_sepl.jpg / Footer sepl.jpg). Optional: the letter can be printed without them (for pre-printed stationery).
  * The signature image comes from Admin > Document To Sign Mapping, document Offer_Ltr_Onshore, for the signer and the date of joining; no image when none is mapped.
Known gaps in the legacy templates, kept visible here: clause 12 of the fixed-term letter is cut off in the legacy PDFs after "safety" (the text box was too short); it is
finished with CLAUSE12_END below, to be confirmed. The legacy sentence "You will initially be report at" is kept as it was.
"""

import os
from datetime import date
from io import BytesIO

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from core.models import DocToSignMapping
from core.pdf_reportlab import FONT, FONT_BOLD, register_fonts, text

LETTERHEAD_DIR = "Letterhead Logo"
HEADER_FILE, FOOTER_FILE = "Offer_Letter_Header.jpg", "Offer_Letter_Footer.jpg"
SIGN_DOC = "Offer_Ltr_Onshore"
ONSHORE_CATEGORY = 4
PER_DAY_EMP_TYPE = 21
BASIC_ID, TRAVEL_ID, CAMP_ID, DAY_RATE_ID = 1, 4, 34, 33
# the order the salary table lists the plain components in; anything else follows in the master's display order
TABLE_ORDER = [1, 3, 29, 6, 20, 8, 30, 31, 32, 35]
CLAUSE12_END = "rules or applicable laws."  # the legacy PDFs stop at "...Company policies, safety"

FIXED_TERM = "fixed_term"
PER_DAY = "per_day"
TEMPLATE_LABEL = {FIXED_TERM: "Fixed term", PER_DAY: "Per day rate"}


class LetterNotReady(Exception):
    """The letter cannot be printed; the message says why (shown to the person)."""


# ── numbers ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

_ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen",
         "Eighteen", "Nineteen"]
_TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def _below_thousand(n):
    parts = []
    if n >= 100:
        parts.append(_ONES[n // 100] + " Hundred")
        n %= 100
    if n >= 20:
        parts.append(_TENS[n // 10] + ((" " + _ONES[n % 10]) if n % 10 else ""))
    elif n:
        parts.append(_ONES[n])
    return " ".join(parts)


def words_indian(n):
    """21418 -> 'Twenty One Thousand Four Hundred Eighteen' (crore, lakh, thousand)."""
    n = int(n)
    if n == 0:
        return "Zero"
    out = []
    for size, name in ((10_000_000, "Crore"), (100_000, "Lakh"), (1000, "Thousand")):
        if n >= size:
            out.append(_below_thousand(n // size) + " " + name)
            n %= size
    if n:
        out.append(_below_thousand(n))
    return " ".join(out)


def words_western(n):
    n = int(n)
    if n == 0:
        return "Zero"
    out = []
    for size, name in ((1_000_000_000, "Billion"), (1_000_000, "Million"), (1000, "Thousand")):
        if n >= size:
            out.append(_below_thousand(n // size) + " " + name)
            n %= size
    if n:
        out.append(_below_thousand(n))
    return " ".join(out)


def group_indian(n):
    """1200000 -> '12,00,000'."""
    s = str(int(n))
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return ",".join(groups + [tail])


def group_western(n):
    return f"{int(n):,}"


# ── what goes into the letter ──────────────────────────────────────────────────────────────────────────────────────────────────────────────

def _dmy(d):
    return d.strftime("%d/%m/%Y") if d else ""


def _name(user):
    return " ".join((user.user_name or "").split()) if user else ""


def template_for(letter):
    return PER_DAY if letter.fs_new_appl.appl_emp_type_id == PER_DAY_EMP_TYPE else FIXED_TERM


def _currency(letter):
    emp_type = letter.fs_new_appl.appl_emp_type
    return "USD" if emp_type and "USD" in (emp_type.emp_type_name or "").upper() else "INR"


def problems_for(letter):
    """Reasons the letter cannot be printed yet (an empty list when it can)."""
    out = []
    if letter.cr_status != "F" or letter.l1_approval_status != "A":
        out.append("The letter is not approved yet.")
    if letter.fs_new_appl.appl_fs_category_id != ONSHORE_CATEGORY:
        out.append("Only onshore offer letters can be printed for now (the offshore format is not built yet).")
    rows = list(letter.components.all())
    counted = sum(c.amount for c in rows if c.counts_in_total == "Y")
    if template_for(letter) == FIXED_TERM:
        if not any(c.component_id == BASIC_ID and c.amount > 0 for c in rows):
            out.append("The letter has no Basic salary.")
        if counted != letter.salary_amt:
            out.append(f"The pay components that count toward the total add up to {counted:,}, not the total salary {letter.salary_amt:,}. Revise the letter to correct it.")
    elif letter.salary_amt <= 0:
        out.append("The letter has no total salary (the per-day letter states it as the day rate).")
    return out


def warnings_for(letter):
    """Things worth a look that do not stop the letter."""
    out = []
    if not _signature_path(letter):
        out.append("No signature image is mapped for the signer on the joining date (Admin > Document To Sign Mapping, Offer_Ltr_Onshore), so the signature space is blank.")
    if not (letter.rig_location or "").strip():
        out.append("The rig location is empty; the letter prints a blank line for it.")
    if not os.path.isfile(_media(HEADER_FILE)) or not os.path.isfile(_media(FOOTER_FILE)):
        out.append("The letterhead images are missing from the Letterhead Logo folder.")
    return out


def _media(filename):
    return os.path.join(settings.MEDIA_ROOT, LETTERHEAD_DIR, filename)


def _signature_path(letter):
    """Absolute path of the signer's signature image for the joining date, or None."""
    user_id = letter.authority_user_id
    if not user_id:
        return None
    day = letter.fs_offer_letter_doj
    rows = DocToSignMapping.objects.filter(doc_name=SIGN_DOC, user_id=user_id, sign_from__lte=day).order_by("-sign_from")
    for r in rows:
        if (r.sign_to is None or r.sign_to >= day) and r.sign_path:
            path = os.path.join(settings.MEDIA_ROOT, r.sign_path)
            if os.path.isfile(path):
                return path
    return None


def schedule_text(letter):
    if (letter.on_off_desc or "").strip():
        return letter.on_off_desc.strip()
    if letter.on_days and letter.off_days:
        return (f"You shall work on a rotational schedule of {letter.on_days} Days ON followed by {letter.off_days} Days OFF, with 12 hour shift duties during the ON "
                "period. The OFF period shall form part of your overall work cycle.")
    return "Your work schedule will be as per the operational requirements of the project and the client."


def travel_lines(letter, rows):
    """Clause 5: the Travel Allowance amount, then the eligibility text; with neither, Not Applicable."""
    lines = []
    amount = next((c.amount for c in rows if c.component_id == TRAVEL_ID and c.amount > 0 and c.show_in_letter == "Y"), 0)
    eligibility = (letter.travel_class or "").strip()
    # HR often types the same sentence into the eligibility text as the allowance row makes ("You are entitled to receive Rs.1000/- as Travelling Allowance"):
    # it is then printed once, from the text.
    if amount and not (eligibility and str(amount) in eligibility.replace(",", "")):
        lines.append(f"You are entitled to receive Rs.{amount}/- as Travelling Allowance")
    if eligibility:
        lines.append(eligibility)
    return lines or ["Not Applicable"]


def _table_rows(rows):
    shown = [c for c in rows if c.counts_in_total == "Y" and c.show_in_letter == "Y" and c.amount > 0]
    rank = {cid: i for i, cid in enumerate(TABLE_ORDER)}
    return sorted(shown, key=lambda c: (rank.get(c.component_id, 100), c.component.ed_order, c.component_id))


def _extra_sentences(rows):
    """Camp Allowance (its fixed sentence) and any other shown component that is not part of the total."""
    out = []
    for c in sorted(rows, key=lambda c: (c.component.ed_order, c.component_id)):
        if c.counts_in_total == "Y" or c.show_in_letter != "Y" or c.amount <= 0 or c.component_id in (TRAVEL_ID, DAY_RATE_ID):
            continue
        if c.component_id == CAMP_ID:
            out.append(f"Apart from the above CTC, you are entitled to receive Rs. {c.amount}/- as Camp Allowance, applicable only for this project/contract and not "
                       "payable upon transfer or relocation to any other project/contract")
        else:
            out.append(f"Apart from the above CTC, you are entitled to receive Rs. {c.amount}/- as {c.component.ed_name}.")
    return out


# ── the page ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

def _styles():
    return {
        "body": ParagraphStyle("body", fontName=FONT, fontSize=9.2, leading=12.4, alignment=4, spaceAfter=3.5),
        "plain": ParagraphStyle("plain", fontName=FONT, fontSize=9.2, leading=12.4, spaceAfter=1.5),
        "bold": ParagraphStyle("bold", fontName=FONT_BOLD, fontSize=9.2, leading=12.1),
        "title": ParagraphStyle("title", fontName=FONT_BOLD, fontSize=12.5, leading=16, alignment=1),
        "head": ParagraphStyle("head", fontName=FONT_BOLD, fontSize=9.8, leading=13, spaceBefore=9, spaceAfter=2.5),
        "cell": ParagraphStyle("cell", fontName=FONT, fontSize=9.2, leading=12),
        "cellb": ParagraphStyle("cellb", fontName=FONT_BOLD, fontSize=9.2, leading=12),
        "cellr": ParagraphStyle("cellr", fontName=FONT, fontSize=9.2, leading=12, alignment=2),
        "cellrb": ParagraphStyle("cellrb", fontName=FONT_BOLD, fontSize=9.2, leading=12, alignment=2),
    }


def _fit_image(path, width):
    w, h = ImageReader(path).getSize()
    return width, width * h / w


def _page_decorator(with_letterhead):
    header, footer = _media(HEADER_FILE), _media(FOOTER_FILE)

    def draw(canvas, doc):
        if not with_letterhead:
            return
        page_w, page_h = A4
        if os.path.isfile(header):
            w, h = _fit_image(header, 44 * mm)
            canvas.drawImage(header, 20 * mm, page_h - 10 * mm - h, width=w, height=h, mask="auto")
        if os.path.isfile(footer):
            w, h = _fit_image(footer, page_w - 40 * mm)
            canvas.drawImage(footer, 20 * mm, 4 * mm, width=w, height=h, mask="auto")

    return draw


def _signature_block(letter, styles, company_line=None):
    """Yours faithfully, (company), the signature image if there is one, the signer's name and designation."""
    block = [Paragraph("Yours faithfully,", styles["plain"])]
    if company_line:
        block.append(Paragraph(text(company_line), styles["plain"]))
    path = _signature_path(letter)
    if path:
        w, h = _fit_image(path, 38 * mm)
        if h > 20 * mm:
            w, h = w * 20 * mm / h, 20 * mm
        img = Image(path, width=w, height=h)
        img.hAlign = "LEFT"
        block += [Spacer(1, 2 * mm), img]
    else:
        block.append(Spacer(1, 16 * mm))
    block += [Paragraph(text(_name(letter.authority_user)), styles["bold"]), Paragraph(text(letter.authority_designation or ""), styles["plain"])]
    return block


def _acceptance(name, styles):
    return [Spacer(1, 5 * mm), Paragraph("Acceptance", styles["bold"]),
            Paragraph(text(f"I, {name}, accept the above terms and conditions."), styles["plain"]), Spacer(1, 4 * mm),
            Paragraph("Signature: ________________________ Date: _____________________________", styles["plain"])]


def _address_block(letter, title_name, styles):
    appl = letter.fs_new_appl
    lines = [Paragraph("To", styles["plain"]), Spacer(1, 1.5 * mm), Paragraph(text(title_name), styles["bold"])]
    if (appl.mailing_addr or "").strip():
        lines.append(Paragraph(text(appl.mailing_addr.strip()), styles["plain"]))
    if (appl.fs_emp_email_pers or "").strip():
        lines.append(Paragraph(text(f"Email: {appl.fs_emp_email_pers.strip()}"), styles["plain"]))
    return lines


def render_offer_letter_pdf(letter, with_letterhead=True):
    """The letter as PDF bytes. Raises LetterNotReady (with the reason) when it cannot be printed."""
    problems = problems_for(letter)
    if problems:
        raise LetterNotReady(" ".join(problems))
    register_fonts()
    s = _styles()
    appl = letter.fs_new_appl
    rows = list(letter.components.select_related("component").all())
    cur = _currency(letter)
    group, words = (group_indian, words_indian) if cur == "INR" else (group_western, words_western)
    title_name = ("Mr." if appl.gender == "M" else "Ms.") + str(appl)
    designation = letter.rank.rank_name
    rig = letter.rig_site_mapping.rig.rig_name
    location = (letter.rig_location or "").strip() or "____"
    camp = (letter.rig_site_mapping.camp_office_addr or "").strip()
    doj, end, dt = _dmy(letter.fs_offer_letter_doj), _dmy(letter.contract_end_dt), _dmy(letter.fs_offer_letter_dt)
    company_name = letter.company.company_name

    story = []

    def P(t, style="body"):
        story.append(Paragraph(t, s[style]))

    def head(t):
        story.append(Paragraph(text(t), s["head"]))

    if template_for(letter) == FIXED_TERM:
        story.append(Paragraph("Fixed Term Employment Offer Letter", s["title"]))
        story.append(Spacer(1, 6 * mm))
        P(text(f"Date:{dt}"), "plain")
        story.append(Spacer(1, 5 * mm))
        story += _address_block(letter, title_name, s)
        story.append(Spacer(1, 5 * mm))
        P(text(f"Dear {title_name}"), "plain")
        story.append(Spacer(1, 3 * mm))
        P(text(f"With reference to your application and subsequent discussions /interview with us, we are pleased to offer you the position of {designation} on a "
               "Fixed Term Employment basis with the Company, subject to the following terms and conditions."))
        head("1. Employment Period")
        P(text(f"Your employment shall commence from your date of joining, i.e., {doj} and shall remain valid up to {end} , or until completion of the project/contract "
               "for which you are engaged with our client, whichever is earlier. The contract may be renewed further based on mutual consent, business requirements, "
               "and continuation of future projects/contracts."))
        head("2. Place of Reporting")
        P(text(f"You will initially be report at: Camp Office : {camp}, as per the details below:"))
        P(text(f"Contact Person : {letter.contact_person or ''}          Mobile No.: {letter.contact_tel_no or ''}"), "plain")
        P(text(f"Appointed Rig Name: {rig}          Rig Location: {location}"), "plain")
        P(text("You may be transferred to any Rig, project site, base, office, or operational location across India depending upon business and operational requirements."))
        head("3. Work Schedule")
        P(text(schedule_text(letter)))
        comp_head = Paragraph(text("4. Compensation"), s["head"])
        total_text = f"{cur} {group(letter.salary_amt)}({'Rupees' if cur == 'INR' else 'US Dollars'} {words(letter.salary_amt)} Only)"
        comp_text = Paragraph(text(f"Your Gross Monthly CTC shall be {total_text}, subject to applicable statutory deductions such as Income Tax, Professional Tax, "
                                   "Provident Fund, ESIC (where applicable), and other deductions as per law."), s["body"])
        table_rows = _table_rows(rows)
        data = [[Paragraph("Monthly Salary Component", s["cellb"]), Paragraph(f"Amount in {cur}", s["cellrb"])]]
        data += [[Paragraph(text(c.component.ed_name), s["cell"]), Paragraph(f"{group(c.amount)}/-", s["cellr"])] for c in table_rows]
        data.append([Paragraph("Total", s["cellb"]), Paragraph(f"{group(sum(c.amount for c in table_rows))}/-", s["cellrb"])])
        t = Table(data, colWidths=[78 * mm, 36 * mm], hAlign="CENTER")
        t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.8, colors.black), ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.black), ("LINEABOVE", (0, -1), (-1, -1), 0.8, colors.black),
                               ("LINEBEFORE", (1, 0), (1, -1), 0.8, colors.black), ("TOPPADDING", (0, 0), (-1, -1), 2.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2)]))
        story.append(KeepTogether([comp_head, comp_text, Spacer(1, 2 * mm), t, Spacer(1, 1.5 * mm)]))  # heading, sentence and the whole table stay on one page
        for sentence in _extra_sentences(rows):
            P(text(sentence))
        head("5. Travel & Benefits")
        for line in travel_lines(letter, rows):
            P(text(line))
        head("6. Medical Fitness & Insurance")
        P(text("You shall be required to submit a Pre-Employment Medical Fitness Certificate in prescribed Form-O issued by a Government-recognized medical facility prior to "
               "joining. In case you are unable to arrange the same, the Company may facilitate the medical examination as per Company policy. The Company shall reimburse "
               "medical examination expenses up to INR 2,500/- against submission of valid supporting bills/documents. You shall also be covered under the Company’s "
               "Workmen Compensation Insurance Policy, as applicable. Further, obtaining and maintaining valid PMJJBY/PMSBY Insurance coverage is mandatory as per "
               "project/client requirements, and proof of the same must be submitted prior to joining."))
        head("7. Client Approval & Deployment")
        P(text("Your appointment and deployment under this offer shall be subject to approval by the Client. The Client may conduct a physical interview and/or technical "
               "assessment prior to deployment, as deemed necessary. In the event of non-approval, rejection, or subsequent withdrawal of deployment approval by the Client, "
               "this offer shall stand automatically withdrawn without any liability or obligation on the part of the Company."))
        head("8. Joining Documents")
        P(text("At the time of joining, you are required to submit original documents along with self-attested copies for verification, including educational and technical "
               "certificates, experience certificates, PF/Form-11, ESIC card (if applicable), bank account details, passport size photographs, last salary slip, relieving "
               "certificate, Aadhaar card, PAN card, Police Verification Certificate, and Medical Fitness Certificate in prescribed Form-O. Failure to submit the required "
               "documents may result in delay or cancellation of deployment."))
        head("9. Mandatory Training & Certifications")
        P(text("You shall possess valid trade and safety certifications applicable to your role and client requirements at the time of joining, including, wherever "
               "applicable, IWCF/IADC, MVT, Rig Pass, Fire Fighting, and First Aid certifications. Original certificates must be produced for verification at the time of "
               "joining. In case valid MVT, Rig Pass, Fire Fighting, or First Aid certifications are not available, the Company may arrange the required training programs "
               "as per Company policy and operational requirements."))
        head("10. Background Verification")
        P(text("Your employment shall be subject to satisfactory verification of your credentials, educational qualifications, certifications, previous employment records, "
               "and other background checks. Any discrepancy, suppression of facts, or submission of incorrect information may lead to withdrawal of this offer or "
               "termination of employment without notice."))
        head("11. PAN Card Compliance")
        P(text("Submission of a valid PAN Card at the time of joining is mandatory. In case of non-submission or invalid PAN details, Tax Deducted at Source (TDS) shall be "
               "deducted at higher applicable rates as per Income Tax provisions."))
        head("12. Probation & Termination")
        P(text("You shall be on probation for a period of three (3) working hitches from the date of joining. During the probation period, either party may terminate the "
               "employment by giving one (1) hitch notice or salary in lieu thereof. Upon successful completion of probation and written confirmation of employment, either "
               "party may terminate the employment by giving one (1) month’s notice or salary in lieu thereof. Notwithstanding the above, the Company reserves the right to "
               "terminate your employment with immediate effect without notice or compensation in cases of misconduct, indiscipline, fraud, breach of Company policies, "
               f"safety {CLAUSE12_END}"))
        head("13. Gratuity")
        P(text("Gratuity shall be applicable to eligible fixed-term employees in accordance with the provisions of the Payment of Gratuity Act, 1972, and applicable labour "
               "laws/amendments from time to time."))
        story.append(Spacer(1, 2 * mm))
        closing = [Paragraph(text("Please sign and return a copy of this letter as a token of your acceptance of the above terms and conditions."), s["body"]),
                   Paragraph(text("We welcome you to the Organization and look forward to a long and successful association with you."), s["body"]), Spacer(1, 3 * mm)]
        story.append(KeepTogether(closing + _signature_block(letter, s) + _acceptance(title_name, s)))
    else:
        # legacy kept the day rate in the letter's total salary (its Day_Rate_Amt column is empty on every letter); a Day Rate Amount component, if one is added, wins
        day_rate = next((c.amount for c in rows if c.component_id == DAY_RATE_ID and c.amount > 0), letter.salary_amt)
        story.append(Spacer(1, 6 * mm))
        P(text(f"Date:{dt}"), "plain")
        story.append(Spacer(1, 5 * mm))
        story += _address_block(letter, title_name, s)
        story.append(Spacer(1, 5 * mm))
        P(text(f"Subject: Appointment as Retainer - {designation}"), "bold")
        story.append(Spacer(1, 4 * mm))
        P(text(f"Dear {title_name}"), "plain")
        story.append(Spacer(1, 3 * mm))
        P(text(f"With reference to our discussions, we are pleased to appoint you as {designation} on a Retainer basis for our Drilling Operations at {rig} , "
               f"{location}, under the following terms and conditions:"))
        head("1. Engagement & Contract Period")
        P(text(f"Your engagement will be effective from {doj} to {end}, or until completion of the assigned project/phase, whichever is earlier, unless terminated as per "
               "the terms of this letter.."))
        head("2. Compensation & Working Hours")
        P(text(f"You will be paid a consolidated day rate of {cur} {group(day_rate)}/- ({'Rupees' if cur == 'INR' else 'US Dollars'} {words(day_rate)} Only) for 12 hours of duty, "
               "inclusive of ON/OFF retainer fees."))
        P(text("The number of days and hours worked shall be certified by the site authority, and payment will be processed accordingly upon submission of your retainer "
               "invoice."))
        P(text("During the Rig Commissioning period, the agreed monthly compensation will be paid on a pro-rata basis for the actual days worked. This payment will cover "
               "both ON duty and OFF day components. The ON/OFF Rotation will not apply during the Rig Commissioning period and no separate OFF day salary will be paid "
               "later for this period."))
        P(text("After completion of Rig Commissioning and commencement of regular drilling operations, the employee will be placed on the applicable equal ON/OFF Rotation. "
               "Thereafter, ON duty and OFF day compensation will be paid based on the applicable monthly basic salary as per Company policy."))
        head("3. Invoicing & Payment")
        P(text("You are required to raise invoices at the end of each month. Payment will be released subject to certification by the site authority and applicable "
               "statutory deductions."))
        head("4. Work Schedule")
        P(text("Your duty schedule will be 12-hour shifts, and deployment will be determined by the Company based on operational requirements."))
        head("5. Travel Allowance")
        for line in travel_lines(letter, rows):
            P(text(line))
        head("6. Boarding & Lodging")
        P(text("Free boarding and lodging will be provided by the Company during your deployment at site."))
        head("7. Other Benefits")
        P(text("You shall not be entitled to any other benefits, unless specifically stated in writing."))
        head("8. Confidentiality")
        P(text("You are required to maintain strict confidentiality regarding all Company information. Any breach may lead to immediate termination without notice."))
        head("9. Statutory Compliance")
        P(text("You are expected to comply with all applicable statutory rules, safety standards, and company policies during your engagement."))
        head("10. Taxation")
        P(text("All payments shall be subject to applicable taxes as per the Income Tax Act, 1961 and other relevant laws. Submission of a valid PAN card and GST certificate "
               "(if applicable) is mandatory."))
        head("11. Termination")
        P(text("The employee may terminate this engagement by giving one week’s written notice or payment in lieu thereof. However, the Company reserves the right to "
               "terminate this engagement at its sole discretion, without prior notice, based on project requirements or performance under the retainer engagement."))
        head("12. Reporting Details")
        P(text("You are requested to report at the following address:"))
        P(text(camp), "plain")
        story.append(Spacer(1, 1.5 * mm))
        P(text(f"Rig Location : {location}"), "plain")
        P(text(f"Contact Person: {letter.contact_person or ''} - {letter.contact_tel_no or ''}"), "plain")
        story.append(Spacer(1, 3 * mm))
        P(text("Kindly sign and return a copy of this letter as a token of your acceptance."))
        story.append(Spacer(1, 2 * mm))
        story.append(KeepTogether(_signature_block(letter, s, company_line=company_name) + _acceptance(title_name, s)))

    top = 33 * mm if with_letterhead else 18 * mm
    bottom = 42 * mm if with_letterhead else 16 * mm
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=top, bottomMargin=bottom, title=f"Offer letter - {appl}",
                            author=company_name)
    decorate = _page_decorator(with_letterhead)
    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
    return buf.getvalue()


def file_name(letter):
    return f"Offer Letter - {str(letter.fs_new_appl)}.pdf"
