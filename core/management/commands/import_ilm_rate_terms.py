"""Fills ILM Rate Terms from the ILM blocks of the Master Rate Sheet workbook (the 'EE01 ILM' style blocks in column K: 'ILM upto 30 KM', 'Extra Per KM').
Only a block whose title names ONE rig that exists is imported, on that rig's current project; a title that appears twice in the sheet (the sheet has two
'SK02 ILM' blocks, one of them next to another rig's rates) is skipped and listed, to be entered by hand. Safe to run again: a rig and project that already
have terms are left alone. The IPM lump sum is not read (it is not in the projection yet).

    python manage.py import_ilm_rate_terms --dry-run
    python manage.py import_ilm_rate_terms
    python manage.py import_ilm_rate_terms --file "../rig operational data/Master Rate Sheet.xlsx"
"""

import datetime
import os
import re

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from openpyxl import load_workbook

from core.daily_operations_update import current_contract
from core.models import IlmRateTerm, MstRig

NOTE = "Imported from the Master Rate Sheet"


class Command(BaseCommand):
    help = "Fill ILM Rate Terms from the Master Rate Sheet."

    def add_arguments(self, parser):
        parser.add_argument("--file", default=os.path.join("..", "rig operational data", "Master Rate Sheet.xlsx"))
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        if not os.path.isfile(opts["file"]):
            raise CommandError(f"File not found: {opts['file']}")
        ws = load_workbook(opts["file"], data_only=True).active
        titles = {}
        for row in range(1, ws.max_row + 1):
            v = ws.cell(row=row, column=11).value  # column K
            m = re.fullmatch(r"\s*([A-Za-z0-9]+)\s+ILM\s*", str(v or ""))
            if m:
                titles.setdefault(m.group(1).upper(), []).append(row)
        rigs = {}
        for r in MstRig.objects.all():
            for n in (r.rig_name, r.rig_short_name):
                if n:
                    rigs.setdefault(re.sub(r"[^A-Z0-9]", "", n.upper()), r)
        made = 0
        with transaction.atomic():
            for title, rows in sorted(titles.items()):
                if len(rows) != 1:
                    self.stdout.write(self.style.WARNING(f"{title} ILM appears {len(rows)} times (rows {rows}): skipped, enter it by hand"))
                    continue
                rig = rigs.get(title)
                if rig is None:
                    self.stdout.write(self.style.WARNING(f"{title} ILM: no rig with that name, skipped"))
                    continue
                upto = flat = extra = None
                for r in range(rows[0] + 1, rows[0] + 6):
                    label, value = str(ws.cell(row=r, column=11).value or ""), ws.cell(row=r, column=12).value
                    km = re.search(r"(\d+(?:\.\d+)?)\s*km", label, re.I)
                    if label.lower().startswith("extra") and isinstance(value, (int, float)):
                        extra = value
                    elif km and isinstance(value, (int, float)):
                        upto, flat = float(km.group(1)), value
                contract = current_contract(rig.rig_id, datetime.date.today())
                if upto is None or extra is None or contract is None:
                    self.stdout.write(self.style.WARNING(f"{title} ILM: could not read the terms or the rig's current project, skipped"))
                    continue
                self.stdout.write(f"{title} ILM -> {rig.rig_name}, project {contract}: flat {flat:,.2f} up to {upto:g} km, then {extra:,.2f} a km")
                if opts["dry_run"] or IlmRateTerm.objects.filter(rig=rig, contract_id=contract).exists():
                    continue
                IlmRateTerm.objects.create(rig=rig, contract_id=contract, upto_km=upto, flat_amount=flat, extra_per_km=extra, note=NOTE, cr_user_id=0, cr_dt=timezone.now())
                made += 1
            if opts["dry_run"]:
                transaction.set_rollback(True)
        self.stdout.write(self.style.SUCCESS("Dry run, nothing written." if opts["dry_run"] else f"Done: {made} rows created"))
