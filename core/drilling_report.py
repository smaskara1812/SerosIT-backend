"""Django port of the legacy TRG_Drilling_Dtl_Ops_Insert_Delete trigger —
kept as a visible, testable function called after every Ops row add/edit/
delete, rather than reproduced as an invisible DB trigger.

Bucket mapping, confirmed against the real trigger body (not the legacy
form's own on-screen legend, which turned out to describe "Others" too
broadly — the trigger's `Rate LIKE 'Other%'` only ever matches literal
Other-1/2/3/4, never Force Majeure/FM/MOB/KMS, which the trigger simply
doesn't sum into any of the six buckets at all):

    Operating Hrs   : R1
    Standby Hrs     : R2, ILM-R2
    Service Hrs     : Other-1, Other-2, Other-3, Other-4  ("Others" — a
                      literal LIKE 'Other%' prefix match, not a catch-all)
    Repair Rate Hrs : R3
    Zero Rate Hrs   : R0
    Rig Move Hrs    : IPM, IPM - Adjacent, IPM - Lateral, ILM
    (not summed)    : Force majeure, FM, FM 2/3, FM 1/3, MOB, KMS,
                      Meterage 12-1/4", Meterage 8-1/2" — these rows keep
                      their own real Duration, it just never rolls up

Drilling_Meterage is unrelated to rate code entirely — it's
SUM(ABS(Depth_To - Depth_From)) over ops rows whose *Operation* is
"Drill actual" (Mst_Drilling_Operations id 2), any rate.
"""

from decimal import Decimal

from django.db.models import Q, Sum
from django.utils import timezone

STANDBY_CODES = {"R2", "ILM-R2"}
RIG_MOVE_CODES = {"IPM", "IPM - Adjacent", "IPM - Lateral", "ILM"}
DOWNTIME_TRIGGER_CODES = {"R0", "R3"}
DRILL_ACTUAL_OPS_ID = 2


def _zero():
    return Decimal("0.00")


def resolve_drilling_hdr(rig_id, report_date):
    """The Drilling Report form only picks Rig + Date — the well
    (DrillingHdr) is resolved from whichever record is active for that rig
    covering that date, same as the legacy form's auto-populated
    Location/Spud Date fields."""
    from .models import DrillingHdr

    ongoing_or_covers_date = Q(drilling_completion_dt__isnull=True) | Q(drilling_completion_dt__date__gte=report_date)
    return (
        DrillingHdr.objects.filter(rig_id=rig_id, first_anchor_down_dt__date__lte=report_date)
        .filter(ongoing_or_covers_date)
        .order_by("-first_anchor_down_dt")
        .first()
    )


def recompute_dtl_totals(dtl, user_id=None):
    """Recomputes dtl's six hour buckets + Drilling_Meterage from its own
    ops rows, clears Downtime_Reason when no R0/R3 rows remain, and stamps
    Mod_User_Id/Mod_Dt — all in one save, same fields the legacy trigger
    touches in one pass."""
    ops = list(dtl.ops.select_related("prj_drilling_rate__drilling_rate", "drilling_ops"))

    buckets = {"operating": _zero(), "standby": _zero(), "service": _zero(), "repair_rate": _zero(), "zero_rate": _zero(), "rig_move": _zero()}
    has_downtime_rate = False

    for op in ops:
        code = op.prj_drilling_rate.drilling_rate.rate_code
        duration = op.duration or _zero()
        if code == "R1":
            buckets["operating"] += duration
        elif code in STANDBY_CODES:
            buckets["standby"] += duration
        elif code.startswith("Other"):
            buckets["service"] += duration
        elif code == "R3":
            buckets["repair_rate"] += duration
            has_downtime_rate = True
        elif code == "R0":
            buckets["zero_rate"] += duration
            has_downtime_rate = True
        elif code in RIG_MOVE_CODES:
            buckets["rig_move"] += duration
        # else: Force Majeure/MOB/KMS/Meterage — logged, not bucketed.

    meterage = sum(
        (abs(op.depth_to - op.depth_from) for op in ops if op.drilling_ops_id == DRILL_ACTUAL_OPS_ID),
        _zero(),
    )

    dtl.operating_hrs = buckets["operating"]
    dtl.standby_hrs = buckets["standby"]
    dtl.repair_service_hrs = buckets["service"]
    dtl.repair_rate_hrs = buckets["repair_rate"]
    dtl.zero_rate_hrs = buckets["zero_rate"]
    dtl.rig_move_hrs = buckets["rig_move"]
    dtl.drilling_meterage = meterage
    if not has_downtime_rate:
        dtl.downtime_reason = None
    if user_id is not None:
        dtl.mod_user_id = user_id
    dtl.mod_dt = timezone.now()
    dtl.save()

    if dtl.drilling_hdr_id:
        recompute_hdr_totals(dtl.drilling_hdr_id)


def recompute_hdr_totals(drilling_hdr_id):
    """Rolls every DrillingDtl day under this well up onto DrillingHdr's own
    tot_* columns — same aggregation as the legacy trigger's item 4 update,
    minus Rig Move Hrs (eos_Drilling_Hdr genuinely has no column for it)."""
    from .models import DrillingDtl, DrillingHdr

    totals = DrillingDtl.objects.filter(drilling_hdr_id=drilling_hdr_id).aggregate(
        diesel_c=Sum("consumption_diesel"),
        water_c=Sum("consumption_water"),
        diesel_r=Sum("received_diesel"),
        water_r=Sum("received_water"),
        water_g=Sum("generated_water"),
        op=Sum("operating_hrs"),
        sb=Sum("standby_hrs"),
        svc=Sum("repair_service_hrs"),
        rr=Sum("repair_rate_hrs"),
        zr=Sum("zero_rate_hrs"),
    )
    DrillingHdr.objects.filter(pk=drilling_hdr_id).update(
        tot_consumption_diesel=totals["diesel_c"] or 0,
        tot_consumption_water=totals["water_c"] or 0,
        tot_received_diesel=totals["diesel_r"] or 0,
        tot_received_water=totals["water_r"] or 0,
        tot_generated_water=totals["water_g"] or 0,
        tot_operating_hrs=totals["op"] or 0,
        tot_standby_hrs=totals["sb"] or 0,
        tot_repair_service_hrs=totals["svc"] or 0,
        tot_repair_rate_hrs=totals["rr"] or 0,
        tot_zero_rate_hrs=totals["zr"] or 0,
    )
