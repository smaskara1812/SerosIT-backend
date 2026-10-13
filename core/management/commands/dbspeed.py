"""Shows where the time goes when a big list is read from the database.

    python manage.py dbspeed

Run it on the machine that has the slow exports. It only reads. It answers: is the
link slow per query (round trip), slow per byte (throughput), or is the query itself
slow on the server? The numbers decide whether more code changes can help.
"""
import time

from django.core.management.base import BaseCommand
from django.db import connection

from core.models import HazardCard


def _bytes(v):
    if v is None:
        return 1
    if isinstance(v, (bytes, str)):
        return len(v)
    return 8


class Command(BaseCommand):
    help = "Time the database link: round trip, count, and the hazard-card export read in a few shapes."

    def say(self, text):
        self.stdout.write(text)

    def run(self, label, qs, fetch=2000):
        sql, params = qs.query.sql_with_params()
        t = time.time()
        with connection.cursor() as cur:
            cur.execute(sql, params)
            t_exec = time.time() - t
            rows = size = 0
            while True:
                chunk = cur.fetchmany(fetch)
                if not chunk:
                    break
                rows += len(chunk)
                size += sum(_bytes(v) for r in chunk for v in r)
        total = time.time() - t
        mb = size / 1048576
        self.say(f"  {label:<46} {rows:>6} rows  {mb:6.2f} MB  first row after {t_exec:5.2f}s  done in {total:5.2f}s  ({mb / total if total else 0:.2f} MB/s)")

    def handle(self, *args, **opts):
        self.say(f"Database: {connection.vendor}")
        t = time.time()
        with connection.cursor() as cur:
            for _ in range(30):
                cur.execute("SELECT 1")
                cur.fetchall()
        self.say(f"Round trip: {(time.time() - t) / 30 * 1000:.1f} ms per query (30 x SELECT 1)")

        base = HazardCard.objects.exclude(marked_as_deleted="Y")
        t = time.time()
        n = base.count()
        self.say(f"COUNT of {n} hazard cards: {time.time() - t:.2f}s (server work, almost no data)")

        full = base.values_list(
            "haz_id_card_no", "event_dt", "close_out_dt", "haz_id_card_status", "timeout_for_safety", "hazard_desc",
            "action_taken", "reported_by_name", "rig__rig_name", "haz_type__haz_type_name",
            "work_location__work_location", "resp_dept__vessel_dept_name", "resp_rank__rank_name",
        ).order_by("-event_dt")
        self.run("export columns, newest first (what the CSV reads)", full)
        self.run("same, fetched 200 at a time", full, fetch=200)
        self.run("same, fetched 10000 at a time", full, fetch=10000)
        short = base.values_list("haz_id_card_no", "event_dt", "haz_id_card_status", "timeout_for_safety").order_by("-event_dt")
        self.run("short columns only (4 small columns)", short)
        nosort = base.values_list(
            "haz_id_card_no", "event_dt", "hazard_desc", "action_taken", "rig__rig_name"
        )
        self.run("text columns, no sorting", nosort.order_by())
        self.say(
            "\nHow to read it: if 'short columns' is also slow, the link is slow per row (round trips); "
            "if it is fast and the full read is slow, bytes are the limit (MB/s); "
            "if 'first row after' is large, the server is slow to start (sort or joins)."
        )
