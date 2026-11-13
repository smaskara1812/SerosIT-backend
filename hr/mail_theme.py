"""The Seros look for the candidate onboarding mails (invite and code): one email layout, table based so every mail program draws it the same.

Colours are the Seros family used across the app (navy, ocean, teal, blue, graphite). The full Seros logo is sent inside the mail (an inline picture,
cid:seros-logo) so it shows even where remote pictures are blocked; it is flattened onto white first, so it also reads in the Email Log's small preview.
"""

import io
import os
from html import escape

from django.conf import settings

NAVY_900, NAVY_800, NAVY_700, NAVY_600 = "#091535", "#0e224e", "#143167", "#1a3f7a"
NAVY_200, NAVY_100, NAVY_50 = "#c7d5ea", "#e4ebf6", "#f3f6fc"
TEAL, OCEAN, BLUE = "#00988a", "#2a93ad", "#2b7cb8"
GRAPHITE_500, GRAPHITE_400, GRAPHITE_700 = "#626978", "#858c9a", "#424242"
PAGE_BG = "#e9eef7"
FONT = "'Segoe UI', 'Helvetica Neue', Helvetica, Arial, sans-serif"

_LOGO_CACHE = {}


def logo_image():
    """[(cid, bytes, subtype)] for the mail's inline picture: the Seros logo on a white ground. Empty if the file is missing."""
    if "logo" not in _LOGO_CACHE:
        result = []
        try:
            from PIL import Image

            path = os.path.join(os.path.dirname(settings.BASE_DIR), "frontend", "public", "branding", "seros-logo.png")
            if not os.path.isfile(path):
                path = os.path.join(settings.BASE_DIR, "core", "banner_logos", "seros-logo.png")
            img = Image.open(path).convert("RGBA")
            img = img.crop((0, 0, img.width - 6, img.height))  # the source file has a faint edge line at the far right
            ground = Image.new("RGBA", img.size, (255, 255, 255, 255))
            ground.alpha_composite(img)
            out = io.BytesIO()
            ground.convert("RGB").save(out, "PNG", optimize=True)
            result = [("seros-logo", out.getvalue(), "png")]
        except Exception:
            result = []
        _LOGO_CACHE["logo"] = result
    return _LOGO_CACHE["logo"]


def button(url, label):
    """A button that survives mail programs: a table cell with its own background and a plain link inside."""
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:26px 0 8px 0;"><tr>'
        f'<td align="center" bgcolor="{NAVY_600}" style="border-radius:12px;background:{NAVY_600};background-image:linear-gradient(180deg,#2a5ca3,{NAVY_600});">'
        f'<a href="{escape(url, quote=True)}" target="_blank" style="display:inline-block;padding:16px 34px;font-family:{FONT};font-size:16px;font-weight:700;'
        f'color:#ffffff;text-decoration:none;border-radius:12px;">{escape(label)}</a></td></tr></table>'
    )


def steps(items):
    """A short numbered list ("what to expect")."""
    rows = "".join(
        "<tr>"
        f'<td width="34" valign="top" style="padding:0 0 14px 0;"><table role="presentation" cellpadding="0" cellspacing="0"><tr>'
        f'<td width="26" height="26" align="center" bgcolor="#ebfaf9" style="border-radius:13px;border:1px solid #a2e2dc;font-family:{FONT};font-size:13px;font-weight:700;color:#008077;">{i}</td>'
        "</tr></table></td>"
        f'<td valign="top" style="padding:3px 0 14px 4px;font-family:{FONT};font-size:14px;line-height:21px;color:{GRAPHITE_700};">{text}</td>'
        "</tr>"
        for i, text in enumerate(items, 1)
    )
    return f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-top:6px;">{rows}</table>'


def code_box(code):
    """The six digits of the code in separate boxes."""
    cells = "".join(
        f'<td width="44" height="56" align="center" bgcolor="{NAVY_50}" style="border:2px solid {NAVY_200};border-radius:10px;font-family:{FONT};'
        f'font-size:28px;font-weight:800;color:{NAVY_900};">{escape(ch)}</td><td width="8"></td>'
        for ch in code
    )
    return f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" align="center" style="margin:22px auto;"><tr>{cells}</tr></table>'


def render(title, body_html, *, preheader="", eyebrow="Rig personnel data request"):
    """The whole mail. `body_html` is already safe HTML (callers escape the parts that came from people). Returns the HTML string."""
    has_logo = bool(logo_image())
    logo = (
        '<img src="cid:seros-logo" alt="Seros" width="170" style="display:block;border:0;outline:none;height:auto;width:170px;">'
        if has_logo
        else f'<span style="font-family:{FONT};font-size:26px;font-weight:800;color:{NAVY_800};letter-spacing:1px;">SEROS</span>'
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light only">
<title>{escape(title)}</title></head>
<body style="margin:0;padding:0;background:{PAGE_BG};">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:{PAGE_BG};">{escape(preheader)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="{PAGE_BG}" style="background:{PAGE_BG};"><tr><td align="center" style="padding:28px 12px;">
  <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:600px;">
    <tr><td bgcolor="{NAVY_900}" align="center" style="background:{NAVY_900};background-image:linear-gradient(160deg,{NAVY_800} 0%,{NAVY_900} 100%);border-radius:20px 20px 0 0;padding:34px 24px 38px 24px;">
      <table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr><td bgcolor="#ffffff" style="background:#ffffff;border-radius:14px;padding:12px 22px;">{logo}</td></tr></table>
      <div style="font-family:{FONT};font-size:11px;font-weight:700;letter-spacing:3px;text-transform:uppercase;color:#8fd3e4;padding-top:22px;">{escape(eyebrow)}</div>
      <div style="font-family:{FONT};font-size:28px;line-height:34px;font-weight:800;color:#ffffff;padding-top:8px;">{escape(title)}</div>
    </td></tr>
    <tr><td style="font-size:0;line-height:0;height:4px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
      <td width="35%" height="4" bgcolor="{TEAL}" style="background:{TEAL};font-size:0;line-height:0;">&nbsp;</td>
      <td width="25%" height="4" bgcolor="{OCEAN}" style="background:{OCEAN};font-size:0;line-height:0;">&nbsp;</td>
      <td width="20%" height="4" bgcolor="{BLUE}" style="background:{BLUE};font-size:0;line-height:0;">&nbsp;</td>
      <td width="20%" height="4" bgcolor="{NAVY_600}" style="background:{NAVY_600};font-size:0;line-height:0;">&nbsp;</td></tr></table></td></tr>
    <tr><td bgcolor="#ffffff" style="background:#ffffff;padding:34px 36px 30px 36px;font-family:{FONT};font-size:15px;line-height:24px;color:{GRAPHITE_700};">
      {body_html}
    </td></tr>
    <tr><td bgcolor="{NAVY_50}" align="center" style="background:{NAVY_50};border-radius:0 0 20px 20px;border-top:1px solid {NAVY_100};padding:22px 28px;font-family:{FONT};font-size:12px;line-height:19px;color:{GRAPHITE_500};">
      <b style="color:{NAVY_700};letter-spacing:2px;">SEROS</b><br>
      This is an automated message, please do not reply to it.<br>
      <span style="color:{GRAPHITE_400};">You received it because Seros HR asked you to share your details.</span>
    </td></tr>
  </table>
</td></tr></table>
</body></html>"""
