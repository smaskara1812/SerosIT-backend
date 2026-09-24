"""QHSE → Activity Monitor + Activity Closure Analysis.

Rebuild of legacy frmActivity_Monitor.aspx(.cs) — schedules a recurring
Activity against an optional Rig, tracks completion, and (uniquely among
this app's pages) can spawn its own successor row at completion time. See
ActivityMonitorDetailView.patch for that logic; everything else here is
plain read/list/export, matching the drilling_dashboard.py/
drilling_daily_data.py convention of hand-built dicts over DRF serializers
for these business-logic-heavy custom pages.

Deliberate deviations from the legacy page, matching how every other page
in this app already treats a literal legacy quirk vs. real business logic:
  - Completion Gap isn't a stored column (legacy computes it client-side
    and persists it) — it's derived live from scheduled_dt/completion_dt
    instead, same treatment as every other derived value elsewhere in this
    app (Validity, efficiency, ...). Positive = completed early, negative
    = completed late.
  - The blocking "an earlier record for this Activity/Rig is still open"
    check, the Planning-Remark-required-on-reschedule rule, and the
    Next-Schedule-Date > Schedule-Date rule are all real server-side
    validation here (legacy only enforced them in client JS).
"""

from datetime import date, timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from . import audit as _audit
from .models import ActivityMonitor, MstActivity, MstFinancialYear, MstRig, UserProfile
from .permissions import HasMenuPermission
from .xlsx_export import build_xlsx_response

DEFAULT_PAGE_SIZE = 200
MAX_PAGE_SIZE = 500
DRILLDOWN_PAGE_SIZE = 20

# Mst_Activity.Activity_Location codes whose activities need a Rig picked —
# Vessel and Rig; Office/Port activities have no Rig at all.
RIG_REQUIRED_LOCATIONS = {"V", "R"}

GAP_BUCKETS = [
    ("early_gt20", lambda g: g > 20),
    ("early_0_20", lambda g: 0 <= g <= 20),
    ("late_1_15", lambda g: -15 <= g <= -1),
    ("late_16_30", lambda g: -30 <= g <= -16),
    ("late_31_45", lambda g: -45 <= g <= -31),
    ("late_gt45", lambda g: g < -45),
]
BUCKET_ORDER = [key for key, _ in GAP_BUCKETS]
BUCKET_LABELS = {
    "early_gt20": "Completed Early (>20)",
    "early_0_20": "Completed Early (0-20)",
    "late_1_15": "Completed Late (1-15)",
    "late_16_30": "Completed Late (16-30)",
    "late_31_45": "Completed Late (31-45)",
    "late_gt45": "Completed Late (>45)",
}


def _current_user_id(request):
    try:
        return UserProfile.objects.get(user_login_id=request.user.username).user_id
    except UserProfile.DoesNotExist:
        return None


def _suggested_next_dt(activity, from_dt):
    """from_dt + the Activity's own Validity Days — 365 maps to exactly +1
    calendar year (not +365 days, which drifts across leap years),
    matching legacy's DATEADD(YEAR,1,...) special case."""
    if activity.activity_validity_days == 365:
        try:
            return from_dt.replace(year=from_dt.year + 1)
        except ValueError:
            # from_dt is a leap day (Feb 29) and from_dt.year+1 isn't leap.
            return from_dt.replace(month=2, day=28, year=from_dt.year + 1)
    return from_dt + timedelta(days=activity.activity_validity_days)


def _gap_days(m):
    if not m.completion_dt:
        return None
    return (m.scheduled_dt - m.completion_dt).days


def _bucket_for(gap):
    for key, matches in GAP_BUCKETS:
        if matches(gap):
            return key
    return None


def _row_dict(m):
    return {
        "activity_monitor_id": m.activity_monitor_id,
        "activity": m.activity_id,
        "activity_name": m.activity.activity_name,
        "activity_location": m.activity.activity_location,
        "activity_validity_days": m.activity.activity_validity_days,
        "rig": m.rig_id,
        "rig_name": m.rig.rig_name if m.rig_id else "",
        "scheduled_dt": m.scheduled_dt,
        "original_scheduled_dt": m.original_scheduled_dt,
        "planning_remark": m.planning_remark,
        "completion_dt": m.completion_dt,
        "completion_remark": m.completion_remark,
        "completion_gap_days": _gap_days(m),
        "is_completed": m.completion_dt is not None,
        # Pre-fills the Next Schedule Date field the moment an open record
        # loads into Update mode — same as legacy's Next_Monitor_Dt column,
        # computed live off the *current* scheduled_dt, not the completion
        # date, since completion hasn't happened yet.
        "suggested_next_dt": _suggested_next_dt(m.activity, m.scheduled_dt) if m.completion_dt is None else None,
    }


def _blocked_message(activity, rig_name):
    rig_part = f" / Rig [{rig_name}]" if rig_name else ""
    return f"Kindly fill Completion Date for the earlier record for Activity [{activity.activity_name}]{rig_part}."


class ActivityMonitorView(APIView):
    """List (Search) + Create (Add)."""

    entity_key = "qhse.activity_monitor"
    permission_classes = [HasMenuPermission]

    def get(self, request):
        qs = ActivityMonitor.objects.select_related("activity", "rig").order_by("-scheduled_dt", "-activity_monitor_id")

        status_param = request.query_params.get("status")
        if status_param == "open":
            qs = qs.filter(completion_dt__isnull=True)
        elif status_param == "completed":
            qs = qs.filter(completion_dt__isnull=False)

        activity_id = request.query_params.get("activity")
        if activity_id:
            qs = qs.filter(activity_id=activity_id)
        rig_id = request.query_params.get("rig")
        if rig_id:
            qs = qs.filter(rig_id=rig_id)
        search = request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(Q(activity__activity_name__icontains=search) | Q(rig__rig_name__icontains=search))

        try:
            page = max(int(request.query_params.get("page", 1)), 1)
        except ValueError:
            page = 1
        try:
            page_size = min(max(int(request.query_params.get("page_size", DEFAULT_PAGE_SIZE)), 1), MAX_PAGE_SIZE)
        except ValueError:
            page_size = DEFAULT_PAGE_SIZE
        offset = (page - 1) * page_size

        count = qs.count()
        rows = [_row_dict(m) for m in qs[offset : offset + page_size]]
        return Response(
            {
                "rows": rows,
                "count": count,
                "page": page,
                "page_size": page_size,
                "has_more": offset + len(rows) < count,
            }
        )

    def post(self, request):
        data = request.data
        activity_id = data.get("activity")
        if not activity_id:
            return Response({"error": "Activity must be selected."}, status=400)
        try:
            activity = MstActivity.objects.get(pk=activity_id)
        except MstActivity.DoesNotExist:
            return Response({"error": "Activity not found."}, status=400)

        rig_id = data.get("rig") or None
        if activity.activity_location in RIG_REQUIRED_LOCATIONS:
            if not rig_id:
                return Response({"error": "Rig must be selected for this Activity."}, status=400)
        else:
            rig_id = None

        scheduled_dt = data.get("scheduled_dt")
        if not scheduled_dt:
            return Response({"error": "Schedule Date must be entered."}, status=400)

        if ActivityMonitor.objects.filter(activity_id=activity_id, rig_id=rig_id, completion_dt__isnull=True).exists():
            rig_name = MstRig.objects.filter(pk=rig_id).values_list("rig_name", flat=True).first() if rig_id else None
            return Response({"error": _blocked_message(activity, rig_name)}, status=400)

        uid = _current_user_id(request)
        instance = ActivityMonitor.objects.create(
            activity_id=activity_id,
            rig_id=rig_id,
            scheduled_dt=scheduled_dt,
            planning_remark=(data.get("planning_remark") or "").strip() or None,
            cr_user_id=uid or 1,
            cr_dt=timezone.now(),
        )
        instance = ActivityMonitor.objects.select_related("activity", "rig").get(pk=instance.pk)
        _audit.record_action(request, "create", self.entity_key, instance.pk, str(instance), None)
        return Response(_row_dict(instance), status=201)


class ActivityMonitorSuggestView(APIView):
    """Add-mode helper: suggested Schedule Date (last date for this
    Activity+Rig + Validity Days) and whether an open record already
    blocks adding a new one — computed as the user picks Activity/Rig,
    before they've committed to Add."""

    entity_key = "qhse.activity_monitor"
    permission_classes = [HasMenuPermission]

    def get(self, request):
        activity_id = request.query_params.get("activity")
        if not activity_id:
            return Response({"error": "activity is required"}, status=400)
        try:
            activity = MstActivity.objects.get(pk=activity_id)
        except MstActivity.DoesNotExist:
            return Response({"error": "Activity not found."}, status=400)

        rig_required = activity.activity_location in RIG_REQUIRED_LOCATIONS
        rig_id = request.query_params.get("rig") or None
        if not rig_required:
            rig_id = None
        elif not rig_id:
            return Response({"rig_required": True, "suggested_dt": None, "blocked": False, "blocked_message": None})

        qs = ActivityMonitor.objects.filter(activity_id=activity_id, rig_id=rig_id)
        blocked = qs.filter(completion_dt__isnull=True).exists()
        last_dt = qs.order_by("-scheduled_dt").values_list("scheduled_dt", flat=True).first()
        suggested_dt = _suggested_next_dt(activity, last_dt) if last_dt else None
        rig_name = MstRig.objects.filter(pk=rig_id).values_list("rig_name", flat=True).first() if rig_id else None

        return Response(
            {
                "rig_required": rig_required,
                "suggested_dt": suggested_dt,
                "blocked": blocked,
                "blocked_message": _blocked_message(activity, rig_name) if blocked else None,
            }
        )


class ActivityMonitorDetailView(APIView):
    entity_key = "qhse.activity_monitor"
    permission_classes = [HasMenuPermission]

    def get(self, request, pk):
        try:
            m = ActivityMonitor.objects.select_related("activity", "rig").get(pk=pk)
        except ActivityMonitor.DoesNotExist:
            return Response({"error": "Not found."}, status=404)
        return Response(_row_dict(m))

    def patch(self, request, pk):
        try:
            m = ActivityMonitor.objects.select_related("activity", "rig").get(pk=pk)
        except ActivityMonitor.DoesNotExist:
            return Response({"error": "Not found."}, status=404)

        if m.completion_dt is not None:
            return Response({"error": "Activity already completed. Data can not be altered."}, status=400)

        data = request.data

        scheduled_dt_raw = data.get("scheduled_dt")
        if not scheduled_dt_raw:
            return Response({"error": "Schedule Date must be entered."}, status=400)
        try:
            new_scheduled_dt = date.fromisoformat(scheduled_dt_raw)
        except ValueError:
            return Response({"error": "Invalid Schedule Date."}, status=400)

        planning_remark = (data.get("planning_remark") or "").strip() or None
        old_scheduled_dt = m.scheduled_dt
        schedule_changed = new_scheduled_dt != old_scheduled_dt
        if schedule_changed and not planning_remark:
            return Response({"error": "Planning Remark must be entered when Schedule Date changes."}, status=400)

        completion_dt = None
        completion_dt_raw = data.get("completion_dt")
        if completion_dt_raw:
            try:
                completion_dt = date.fromisoformat(completion_dt_raw)
            except ValueError:
                return Response({"error": "Invalid Completion Date."}, status=400)
            if completion_dt > timezone.localdate():
                return Response({"error": "Completion Date must be on or before today."}, status=400)

        completion_remark = (data.get("completion_remark") or "").strip() or None
        if completion_dt and not completion_remark:
            return Response({"error": "Completion Remark must be entered."}, status=400)

        next_scheduled_dt = None
        next_planning_remark = None
        create_next = False
        if completion_dt:
            next_required = data.get("next_schedule_required")
            if next_required not in ("Y", "N"):
                return Response({"error": "Select whether to create Next Schedule (Yes / No)."}, status=400)
            if next_required == "Y":
                next_dt_raw = data.get("next_scheduled_dt")
                if not next_dt_raw:
                    return Response({"error": "Next Schedule Date must be entered."}, status=400)
                try:
                    next_scheduled_dt = date.fromisoformat(next_dt_raw)
                except ValueError:
                    return Response({"error": "Invalid Next Schedule Date."}, status=400)
                if next_scheduled_dt <= new_scheduled_dt:
                    return Response({"error": "Next Schedule Date must be greater than Schedule Date."}, status=400)
                next_planning_remark = (data.get("next_planning_remark") or "").strip() or None
                create_next = True

        uid = _current_user_id(request)
        old_snapshot = {
            "scheduled_dt": m.scheduled_dt,
            "planning_remark": m.planning_remark,
            "completion_dt": m.completion_dt,
            "completion_remark": m.completion_remark,
        }

        next_row = None
        with transaction.atomic():
            if schedule_changed and m.original_scheduled_dt is None:
                m.original_scheduled_dt = old_scheduled_dt
            m.scheduled_dt = new_scheduled_dt
            m.planning_remark = planning_remark
            m.completion_dt = completion_dt
            m.completion_remark = completion_remark
            m.mod_user_id = uid
            m.mod_dt = timezone.now()
            m.save()

            if create_next:
                next_row = ActivityMonitor.objects.create(
                    activity_id=m.activity_id,
                    rig_id=m.rig_id,
                    scheduled_dt=next_scheduled_dt,
                    planning_remark=next_planning_remark,
                    cr_user_id=uid or 1,
                    cr_dt=timezone.now(),
                )
                next_row = ActivityMonitor.objects.select_related("activity", "rig").get(pk=next_row.pk)

            new_snapshot = {
                "scheduled_dt": m.scheduled_dt,
                "planning_remark": m.planning_remark,
                "completion_dt": m.completion_dt,
                "completion_remark": m.completion_remark,
            }
            changes = {
                k: {"old": str(old_snapshot[k]) if old_snapshot[k] is not None else None, "new": str(v) if v is not None else None}
                for k, v in new_snapshot.items()
                if old_snapshot[k] != v
            }
            _audit.record_action(request, "update", self.entity_key, m.pk, str(m), changes or None)
            if next_row:
                _audit.record_action(
                    request,
                    "create",
                    self.entity_key,
                    next_row.pk,
                    str(next_row),
                    {"spawned_from_activity_monitor_id": {"old": None, "new": m.pk}},
                )

        result = _row_dict(m)
        if next_row:
            result["next_row"] = _row_dict(next_row)
        return Response(result)


class ActivityMonitorExportView(APIView):
    entity_key = "qhse.activity_monitor"
    permission_classes = [HasMenuPermission]
    action = "export"

    def get(self, request):
        qs = ActivityMonitor.objects.select_related("activity", "rig").order_by("-scheduled_dt")
        status_param = request.query_params.get("status")
        if status_param == "open":
            qs = qs.filter(completion_dt__isnull=True)
        elif status_param == "completed":
            qs = qs.filter(completion_dt__isnull=False)
        activity_id = request.query_params.get("activity")
        if activity_id:
            qs = qs.filter(activity_id=activity_id)
        rig_id = request.query_params.get("rig")
        if rig_id:
            qs = qs.filter(rig_id=rig_id)

        columns = [
            "Activity", "Rig", "Schedule Date", "Original Date", "Planning Remark",
            "Completion Date", "Completion Remark", "Completion Gap (Days)",
        ]
        rows = [
            [
                m.activity.activity_name, m.rig.rig_name if m.rig_id else "",
                m.scheduled_dt, m.original_scheduled_dt, m.planning_remark,
                m.completion_dt, m.completion_remark, _gap_days(m),
            ]
            for m in qs
        ]
        filename = f"activity-monitor-{date.today().isoformat()}.xlsx"
        return build_xlsx_response(filename, "Activity Monitor", [], columns, rows)


def _closure_filtered_qs(request):
    """Scoped by scheduled_dt (when the activity was DUE), not
    completion_dt — verified against the legacy report's own numbers for
    FY 2014-2015 / Essar Wildcat (22 rows, 13/8/0/0/1/0 across the
    buckets): filtering on completion_dt gave only 9, filtering on
    scheduled_dt matches exactly. Makes sense for what this report is
    actually answering too — "how did activities *due* in this FY end up
    closing", not "what happened to close during this FY" (which would
    also catch activities scheduled years earlier)."""
    params = request.query_params
    qs = ActivityMonitor.objects.filter(completion_dt__isnull=False).select_related("activity", "rig")
    fy_ids = [int(x) for x in params.get("financial_years", "").split(",") if x.strip().isdigit()]
    if fy_ids:
        fys = list(MstFinancialYear.objects.filter(financial_year_id__in=fy_ids))
        if not fys:
            return ActivityMonitor.objects.none()
        date_q = Q()
        for fy in fys:
            date_q |= Q(scheduled_dt__gte=fy.fin_year_from, scheduled_dt__lte=fy.fin_year_to)
        qs = qs.filter(date_q)
    return qs


class ActivityClosureAnalysisView(APIView):
    """Rig x gap-bucket pivot of completed Activity Monitor rows, scoped
    by Financial Year (matched against completion_dt) — rebuild of the
    legacy Activity Closure Analysis grid."""

    entity_key = "qhse.activity_closure_analysis"
    permission_classes = [HasMenuPermission]

    def get(self, request):
        qs = _closure_filtered_qs(request)
        by_rig = {}
        totals = {key: 0 for key in BUCKET_ORDER}
        for m in qs:
            bucket = _bucket_for(_gap_days(m))
            if bucket is None:
                continue
            rig_name = m.rig.rig_name if m.rig_id else "Office/Port"
            row = by_rig.setdefault(rig_name, {key: 0 for key in BUCKET_ORDER})
            row[bucket] += 1
            totals[bucket] += 1

        rows = [
            {"rig": rig_name, "buckets": by_rig[rig_name], "total": sum(by_rig[rig_name].values())}
            for rig_name in sorted(by_rig)
        ]
        return Response(
            {
                "rows": rows,
                "totals": {"buckets": totals, "total": sum(totals.values())},
                "bucket_order": BUCKET_ORDER,
                "bucket_labels": BUCKET_LABELS,
            }
        )


class ActivityClosureDrilldownView(APIView):
    """The list behind one pivot cell (or the whole filtered set, if
    rig/bucket are omitted) — rebuild of the legacy popup's grid."""

    entity_key = "qhse.activity_closure_analysis"
    permission_classes = [HasMenuPermission]

    def get(self, request):
        qs = _closure_filtered_qs(request)
        want_rig = request.query_params.get("rig")
        want_bucket = request.query_params.get("bucket")

        # The bucket a row falls into only exists once scheduled_dt/
        # completion_dt are compared in Python (see _bucket_for), so this
        # can't be a DB-side LIMIT/OFFSET — the full filtered set has to be
        # built here regardless. It's paginated below purely to keep the
        # frontend's DOM/response small, not because building it is itself
        # expensive at this table's size.
        all_rows = []
        for m in qs:
            gap = _gap_days(m)
            bucket = _bucket_for(gap)
            if bucket is None:
                continue
            rig_name = m.rig.rig_name if m.rig_id else "Office/Port"
            if want_rig and rig_name != want_rig:
                continue
            if want_bucket and bucket != want_bucket:
                continue
            all_rows.append(
                {
                    "activity_name": m.activity.activity_name,
                    "rig_name": rig_name,
                    "scheduled_dt": m.scheduled_dt,
                    "completion_dt": m.completion_dt,
                    "planning_remark": m.planning_remark,
                    "completion_remark": m.completion_remark,
                    "gap_days": gap,
                }
            )
        all_rows.sort(key=lambda r: r["scheduled_dt"])

        try:
            page = max(int(request.query_params.get("page", 1)), 1)
        except ValueError:
            page = 1
        try:
            page_size = min(max(int(request.query_params.get("page_size", DRILLDOWN_PAGE_SIZE)), 1), MAX_PAGE_SIZE)
        except ValueError:
            page_size = DRILLDOWN_PAGE_SIZE
        offset = (page - 1) * page_size

        page_rows = all_rows[offset : offset + page_size]
        return Response(
            {
                "rows": page_rows,
                "count": len(all_rows),
                "page": page,
                "page_size": page_size,
                "has_more": offset + len(page_rows) < len(all_rows),
            }
        )


class ActivityClosureAnalysisExportView(APIView):
    entity_key = "qhse.activity_closure_analysis"
    permission_classes = [HasMenuPermission]
    action = "export"

    def get(self, request):
        qs = _closure_filtered_qs(request).order_by("scheduled_dt")
        columns = [
            "Activity", "Rig", "Schedule Date", "Completion Date",
            "Planning Remark", "Completion Remark", "Gap (Days)", "Bucket",
        ]
        rows = []
        for m in qs:
            gap = _gap_days(m)
            bucket = _bucket_for(gap)
            rows.append(
                [
                    m.activity.activity_name, m.rig.rig_name if m.rig_id else "",
                    m.scheduled_dt, m.completion_dt, m.planning_remark, m.completion_remark,
                    gap, BUCKET_LABELS.get(bucket, ""),
                ]
            )
        filename = f"activity-closure-analysis-{date.today().isoformat()}.xlsx"
        return build_xlsx_response(filename, "Activity Closure Analysis", [], columns, rows)
