"""Brings the legacy sender account(s) over into Masters > Alert Senders, from the legacy table Alert_Sender_Dtl in the legacy schema (default
Seros_Data on the development MySQL). Safe to run again: an alert that already has a sender row is left alone.

    python manage.py import_alert_senders              # dry run: lists what would be added (the password is never shown)
    python manage.py import_alert_senders --apply
    python manage.py import_alert_senders --apply --schema Seros_Data

The legacy password was kept as plain text; here it is encrypted with CREDENTIAL_KEY on the way in. The legacy table has no port or security
setting, so port 25 and no encryption are used (the same as the default account); change them on the Alert Senders page if the server needs
otherwise. On SQL Server, where this table is not loaded, add the row by hand on the Alert Senders page instead."""

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.utils import timezone

from core import secret_box
from core.models import AlertSenderDtl, MailAlertDtl


class Command(BaseCommand):
    help = "Import the legacy Alert_Sender_Dtl rows into Alert Senders (dry run unless --apply)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--schema", default="Seros_Data")

    def handle(self, *args, **opts):
        if connection.vendor != "mysql":
            raise CommandError("This reads the legacy schema on the development MySQL. On SQL Server add the sender on the Alert Senders page.")
        schema = opts["schema"]
        if not schema.replace("_", "").isalnum():
            raise CommandError("Bad schema name.")
        with connection.cursor() as cur:
            cur.execute(f"SELECT Alert_Id, Mail_Serv_Name, Mail_From_Address, Mail_User_Name, Mail_User_Password FROM `{schema}`.Alert_Sender_Dtl ORDER BY Alert_Sender_Dtl_Id")
            rows = cur.fetchall()
        added = skipped = 0
        for alert_id, host, from_addr, user, pw in rows:
            alert = MailAlertDtl.objects.filter(pk=alert_id).first()
            if alert is None:
                self.stdout.write(self.style.WARNING(f"alert {alert_id}: not in Mail Alerts, skipped"))
                skipped += 1
                continue
            if AlertSenderDtl.objects.filter(alert=alert).exists():
                self.stdout.write(f"alert {alert_id} ({alert.alert_name}): already has a sender, left alone")
                skipped += 1
                continue
            self.stdout.write(f"alert {alert_id} ({alert.alert_name}): {from_addr} through {host}, user {user or '(none)'}, password {'set' if pw else 'none'}")
            if opts["apply"]:
                AlertSenderDtl.objects.create(alert=alert, mail_host=(host or "").strip(), mail_port=25, mail_security="N", mail_user_name=(user or "").strip(),
                                           password=secret_box.encrypt(pw) if pw else "", from_address=(from_addr or "").strip(), is_active="Y", cr_user_id=0, cr_dt=timezone.now())
                added += 1
        self.stdout.write(("Added " if opts["apply"] else "Would add ") + f"{added if opts['apply'] else len(rows) - skipped}; skipped {skipped}.")
