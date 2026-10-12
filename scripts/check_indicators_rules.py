"""Checks the Leading and Lagging Indicators header rules through the real API.

    cd backend
    .venv/bin/python scripts/check_indicators_rules.py

Runs every request inside one transaction that is rolled back at the end, so
nothing is saved. Needs the normal dev data. Exits with status 1 if any check fails.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

import datetime

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework.test import APIClient

from core.models import LaggingIndicatorsHdr, LeadingIndicatorsHdr, MstCompany, MstRig

FAILED = []


def check(name, ok, detail=""):
    print(("  ok    " if ok else "  FAIL  ") + name + (f"  {detail}" if detail and not ok else ""))
    if not ok:
        FAILED.append(name)


def keys(resp):
    try:
        return set(resp.json().keys())
    except Exception:
        return set()


def run():
    client = APIClient(HTTP_HOST="localhost")
    client.force_authenticate(get_user_model().objects.filter(is_superuser=True).first())
    rigs = list(MstRig.objects.all()[:2])
    companies = list(MstCompany.objects.all()[:2])
    today = datetime.date.today()
    this_month = f"{today.year}-{today.month:02d}"
    next_month = f"{today.year + (today.month == 12)}-{(today.month % 12) + 1:02d}"

    for name, url, model in (
        ("Leading", "/api/qhse/leading-indicators/", LeadingIndicatorsHdr),
        ("Lagging", "/api/qhse/lagging-indicators/", LaggingIndicatorsHdr),
    ):
        print(name)

        def post(n=[0], **over):
            n[0] += 1
            data = {"company": companies[0].pk, "rig": rigs[0].pk, "report_no": f"ZZ{n[0]:03d}", "period_month": "2019-01"}
            data.update(over)
            return client.post(url, data, format="json")

        check("a valid report is accepted", post().status_code == 201)
        r = post(period_month=next_month)
        check("a month after the current one is refused", r.status_code == 400 and "period_month" in keys(r))
        check("the current month is accepted", post(period_month=this_month).status_code == 201)
        r = post()
        check("the same company, rig and period again is refused", r.status_code == 400 and "period_month" in keys(r), r.content[:150])
        check("another company for the same rig and period is accepted", post(company=companies[1].pk).status_code == 201)
        check("another rig for the same company and period is accepted", post(rig=rigs[1].pk).status_code == 201)
        check("another period for the same company and rig is accepted", post(period_month="2019-02").status_code == 201)
        r = client.post(url, {"company": companies[0].pk, "rig": rigs[0].pk, "report_no": "ZZ-DUP", "period_month": "2018-05"}, format="json")
        r2 = client.post(url, {"company": companies[0].pk, "rig": rigs[1].pk, "report_no": "ZZ-DUP", "period_month": "2018-05"}, format="json")
        check("a repeated Report No. is refused", r.status_code == 201 and r2.status_code == 400 and "report_no" in keys(r2))
        check("a blank Report No. is refused", post(report_no="  ", period_month="2018-06").status_code == 400)
        check("a Report No. over 12 characters is refused", post(report_no="X" * 13, period_month="2018-07").status_code == 400)
        r = client.post(url, {"company": companies[0].pk, "report_no": "ZZ-NR", "period_month": "2018-08"}, format="json")
        check("a missing rig is refused", r.status_code == 400 and "rig" in keys(r))
        check("an invalid period is refused", post(period_month="2018-13").status_code == 400)


if __name__ == "__main__":
    with transaction.atomic():
        run()
        transaction.set_rollback(True)
    print()
    print("FAILED: " + ", ".join(FAILED) if FAILED else "All checks passed. Nothing was saved.")
    sys.exit(1 if FAILED else 0)
