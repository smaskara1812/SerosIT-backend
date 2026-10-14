"""Diagnostic for the "records created since" warning. Prints what the database really holds.

    cd backend
    python scripts/debug_dependents.py

Works in a transaction that is rolled back, so nothing is saved.
"""

import os
import sys
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.db import connection, transaction
from django.utils import timezone

from core import audit_revert as ar
from core.models import MstRigSubtype, MstRigType


def main():
    print("vendor:", connection.vendor, "| python now:", timezone.now())
    with transaction.atomic():
        t = MstRigType.objects.create(rig_type_name="ZZ Dbg", cr_user_id=1, cr_dt=timezone.now())
        since = timezone.now()
        new = MstRigSubtype.objects.create(rig_subtype_name="ZZ New", rig_type_id=t.pk, cr_user_id=1, cr_dt=since + timedelta(seconds=1))
        old = MstRigSubtype.objects.create(rig_subtype_name="ZZ Old", rig_type_id=t.pk, cr_user_id=1, cr_dt=since - timedelta(days=2))
        print("since:", since)
        for s in (new, old):
            back = MstRigSubtype.objects.get(pk=s.pk)
            print(" ", s.rig_subtype_name, "cr_dt written:", s.cr_dt, "| read back:", repr(back.cr_dt))
        print("subtypes of the type, no date filter:", MstRigSubtype.objects.filter(rig_type=t).count())
        print("with cr_dt >= since:", MstRigSubtype.objects.filter(rig_type=t, cr_dt__gte=since).count())
        print("with cr_dt >= since - 1 day:", MstRigSubtype.objects.filter(rig_type=t, cr_dt__gte=since - timedelta(days=1)).count())
        errors = []
        print("engine result:", ar._dependents_since(MstRigType, t, since, errors), "errors:", errors)
        print("relations seen:")
        for rel in MstRigType._meta.related_objects:
            print("  ", rel.related_model.__name__, "many_to_many" if rel.many_to_many else "", "cr_dt" in {f.name for f in rel.related_model._meta.fields})
        transaction.set_rollback(True)


if __name__ == "__main__":
    main()
