"""Encrypts the secrets that are still stored as plain text, and reports local password hashes still in the old unsalted format.

    python manage.py encrypt_stored_secrets              # dry run: counts only
    python manage.py encrypt_stored_secrets --apply
    python manage.py encrypt_stored_secrets --apply --rotate    # also re-encrypt everything with the newest key of CREDENTIAL_KEY

  - mst_business_system.mail_user_password, sys_user_mail_credential.password and alert_sender.password: plain text becomes "enc1:..." (core/secret_box.py).
    A legacy reload (import_business_system.sql) brings the plain text back, so reload_from_legacy.py runs this afterwards.
  - mst_user_password: only counted. Old SHA-256 hashes cannot be converted without the password; each one is replaced with a salted PBKDF2 hash
    when its owner next signs in (core/auth_backend.py).
Safe to run again."""

from django.core.management.base import BaseCommand

from core import secret_box
from core.models import AlertSenderDtl, MstBusinessSystem, MstUserPassword, UserMailCredential
from core.passwords import is_legacy_hash


class Command(BaseCommand):
    help = "Encrypt plain-text stored secrets (dry run unless --apply)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--rotate", action="store_true", help="re-encrypt already encrypted values with the first key of CREDENTIAL_KEY")

    def handle(self, *args, **opts):
        apply = opts["apply"]
        n_bs = n_cred = n_rot = 0
        if opts["rotate"]:
            for model, field in ((MstBusinessSystem, "mail_user_password"), (UserMailCredential, "password"), (AlertSenderDtl, "password")):
                for obj in model.objects.all():
                    v = getattr(obj, field)
                    if secret_box.is_encrypted(v):
                        n_rot += 1
                        if apply:
                            model.objects.filter(pk=obj.pk).update(**{field: secret_box.rotate(v)})
        for obj in MstBusinessSystem.objects.exclude(mail_user_password__isnull=True).exclude(mail_user_password=""):
            if not secret_box.is_encrypted(obj.mail_user_password):
                n_bs += 1
                if apply:
                    MstBusinessSystem.objects.filter(pk=obj.pk).update(mail_user_password=secret_box.encrypt(obj.mail_user_password))
        for obj in UserMailCredential.objects.exclude(password=""):
            if not secret_box.is_encrypted(obj.password):
                n_cred += 1
                if apply:
                    UserMailCredential.objects.filter(pk=obj.pk).update(password=secret_box.encrypt(obj.password))
        legacy = sum(1 for h in MstUserPassword.objects.values_list("password_hash", flat=True) if is_legacy_hash(h))
        self.stdout.write(f"{'ENCRYPTED' if apply else 'DRY RUN (nothing changed)'}")
        if opts["rotate"]:
            self.stdout.write(f"  encrypted values re-encrypted with the newest key: {n_rot}")
        self.stdout.write(f"  business system mail passwords in plain text: {n_bs}")
        self.stdout.write(f"  cached user mail passwords in plain text: {n_cred}")
        self.stdout.write(f"  local password hashes still in the old unsalted format: {legacy} (replaced when each user next signs in)")
