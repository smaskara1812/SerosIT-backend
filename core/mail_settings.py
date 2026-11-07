"""The two mail settings an App Admin controls from Admin > Mail Controls, read with the .env as the backup (the same way core/mailer.py reads the mail redirect):

  * who is told when an automatic mail has finally failed ("the error mail"): `error_recipients()`;
  * the Daily Mail Summary: whether it is on, when it goes and who gets it: `summary_state()` / `summary_recipients()`.

A saved page row wins over the .env. Values are cached for a few seconds, because the web server and the scheduler are separate processes; saving on the page clears
the cache of the web server at once, and the scheduler picks the change up within the cache time."""

import re
import time

from django.conf import settings

_CACHE = {"at": 0.0, "row": None}
_TTL = 10
TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


def clear_cache():
    _CACHE["at"] = 0.0


def _row():
    if time.monotonic() - _CACHE["at"] > _TTL:
        from .models import MailSummarySetting

        try:
            row = MailSummarySetting.objects.filter(pk=1).first()
            _CACHE["row"] = (
                {
                    "summary_saved": bool(row.summary_saved), "summary_on": bool(row.summary_on), "send_time": row.send_time or "22:00",
                    "summary_to": _split(row.summary_to), "same_as_error": bool(row.same_as_error), "send_when_quiet": bool(row.send_when_quiet),
                    "grouped": bool(row.grouped), "error_to": None if row.error_to is None else _split(row.error_to),
                    "changed_by": row.changed_by, "changed_at": row.changed_at,
                }
                if row else None
            )
        except Exception:  # the table is not there yet (migration not run): the .env decides
            _CACHE["row"] = None
        _CACHE["at"] = time.monotonic()
    return _CACHE["row"]


def _split(text):
    return [a.strip() for a in (text or "").replace("\n", ",").replace(";", ",").split(",") if a.strip()]


def normal_time(text):
    """'9:5' is not a time; '09:05' is. Returns 'HH:MM' or None."""
    m = TIME_RE.match((text or "").strip())
    return f"{int(m.group(1)):02d}:{m.group(2)}" if m else None


def error_state():
    """-> ([addresses], source). source is "page" when an App Admin chose the people on the Mail Controls page, else "env" (SCHEDULER_ERROR_MAIL_TO)."""
    row = _row()
    if row is not None and row["error_to"] is not None:
        return list(row["error_to"]), "page"
    return list(settings.SCHEDULER_ERROR_MAIL_TO), "env"


def error_recipients():
    return error_state()[0]


def summary_state():
    """The Daily Mail Summary as it is now: {on, time, to, same_as_error, send_when_quiet, grouped, source, changed_by, changed_at}. `to` is what was typed;
    use summary_recipients() for the people it will really go to."""
    row = _row()
    if row is not None and row["summary_saved"]:
        return {"on": row["summary_on"], "time": normal_time(row["send_time"]) or "22:00", "to": list(row["summary_to"]), "same_as_error": row["same_as_error"],
                "send_when_quiet": row["send_when_quiet"], "grouped": row["grouped"], "source": "page", "changed_by": row["changed_by"], "changed_at": row["changed_at"]}
    env_to = list(settings.MAIL_SUMMARY_TO)
    return {"on": bool(settings.MAIL_SUMMARY), "time": normal_time(settings.MAIL_SUMMARY_TIME) or "22:00", "to": env_to, "same_as_error": not env_to,
            "send_when_quiet": True, "grouped": True, "source": "env", "changed_by": row["changed_by"] if row else "", "changed_at": row["changed_at"] if row else None}


def summary_recipients(state=None):
    s = state or summary_state()
    return error_recipients() if s["same_as_error"] else list(s["to"])
