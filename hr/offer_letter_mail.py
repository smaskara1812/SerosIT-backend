"""Mailing an offer letter to the applicant (one letter, or many at once): the part that is planned but NOT configured yet.

What is here today: the checks that decide whether a letter can be mailed (`mail_problems`), and the one place the sending will be wired in (`send_offer_letter`),
which for now only says it is not configured. Bulk sending already works up to that point: every selected letter is checked, and each applicant will get his own mail
with his own letter attached, never a shared mail. Wiring it later means writing `send_offer_letter` (subject, body, Cc/Bcc and the people who get a copy are still to be
decided) and setting MAIL_CONFIGURED to True; the Email Log, redirect and logging rules of the other automatic mails (core/mailer.py) are the ones to use.
"""

from hr import offer_letter_pdf

MAIL_CONFIGURED = False
NOT_CONFIGURED = "Sending the offer letter by mail is not configured yet."
MAX_BULK = 200


class MailNotConfigured(Exception):
    pass


def mail_problems(letter):
    """Why this letter cannot be mailed (an empty list when it can): it must be printable, and the applicant must have an e-mail address."""
    out = list(offer_letter_pdf.problems_for(letter))
    if not (letter.fs_new_appl.fs_emp_email_pers or "").strip():
        out.append("The applicant has no e-mail address.")
    return out


def send_offer_letter(letter, pdf_bytes, request):
    """Mails one applicant his offer letter (the PDF attached). Not configured yet."""
    if not MAIL_CONFIGURED:
        raise MailNotConfigured(NOT_CONFIGURED)
    raise NotImplementedError  # the real sending goes here
