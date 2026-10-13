"""Compliance Radar dashboard and the Home "digest" strip.

Both answer "what is overdue or about to be?", from facts that already live on
separate pages, so there is nothing new to enter:

  certificate        Rig Certificates with a Valid Till date. Only the *latest*
                     certificate of each type on a rig counts: an older one that
                     was renewed is history, not an open obligation.
  survey             Rig Certificate Schedule rows not yet completed
  activity           Activity Monitor rows not yet completed
  incident_action    Incident Actions not yet closed
  corrective_action  Corrective Actions Reporting rows not yet closed

An item is **overdue** when its due date is before today, **due soon** when it
falls within the horizon (30, 60 or 90 days) and **no date** when an action is
still open but has no target date (so it can never become overdue by itself).

Rig scope is the same as every other drilling dashboard (dashboard_access): real
drilling rigs the user is mapped to. Rigs that are no longer active are left out
unless asked for. An item that is not tied to a rig (an office activity, say) is
shown only to a user who sees every rig and has not narrowed the rig filter.

The digest (`ComplianceDigestView`) is a handful of counts for the Home screen.
Each tile is returned only if the user may open the page it links to, and each
link carries the same filter as the number on the tile.
"""

from datetime import timedelta
from urllib.parse import urlencode

from django.db.models import Q
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .dashboard_access import current_contract_by_rig, dashboard_rig_queryset, get_accessible_rig_ids
from .models import (
    ActivityMonitor,
    ApproverMappingDtl,
    DrillingDtl,
    DrillingHdr,
    HazardCard,
    IncidentAction,
    MstItAsset,
    OtherQhseAction,
    RigCert,
    RigCertSchedule,
    UserProfile,
)
from .permissions import HasMenuPermission, get_user_access
from .xlsx_export import build_xlsx_response

ENTITY_KEY = "dashboards.compliance_radar"
HORIZONS = (30, 60, 90)
MAX_ITEMS = 1000
STATES = ("overdue", "due_soon", "no_date")

CATEGORIES = [
    {"key": "certificate", "label": "Rig certificates", "path": "/qhse/rig-certificates", "menu_key": "qhse.rig_certificates"},
    {"key": "survey", "label": "Certificate surveys", "path": "/qhse/rig-certificate-schedule", "menu_key": "qhse.rig_certificate_schedule"},
    {"key": "activity", "label": "Activities", "path": "/qhse/activity-monitor", "menu_key": "qhse.activity_monitor"},
    {"key": "incident_action", "label": "Incident actions", "path": "/qhse/incident-actions", "menu_key": "qhse.incident_actions"},
    {"key": "corrective_action", "label": "Corrective actions", "path": "/qhse/corrective-actions", "menu_key": "qhse.corrective_actions"},
]
CATEGORY_KEYS = [c["key"] for c in CATEGORIES]
_PATH = {c["key"]: c["path"] for c in CATEGORIES}
_MENU = {c["key"]: c["menu_key"] for c in CATEGORIES}

SILENT_DAYS = 3  # same rule as Fleet Operating Picture
CONTRACT_ENDING_DAYS = 30
HAZARD_OPEN_DAYS = 30
DRILLING_APPROVAL_CODE = "DRILLING_DTL"  # same code the Drilling Report workflow uses


def _short(text, n=90):
    text = (text or "").strip()
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def _window(field, today, horizon):
    """Rows due before today or within the horizon (later ones are not listed)."""
    return {f"{field}__isnull": False, f"{field}__lte": today + timedelta(days=horizon)}


def _latest_certificates(qs):
    """The newest certificate of each type on each rig (by issue date, then valid-till, then id).
    An older one that was replaced is history and is not an open obligation."""
    latest = {}
    for c in qs.select_related("rig", "buss_cert").order_by("rig_id", "buss_cert_id", "-cert_date", "-valid_till", "-pk"):
        latest.setdefault((c.rig_id, c.buss_cert_id), c)
    return latest.values()


def collect_items(rig_ids, today, horizon, include_rigless=False, mandatory_only=False):
    """Every overdue / due-soon / no-date item for these rigs, as plain dicts."""
    items = []

    def rig_q(prefix):
        q = Q(**{f"{prefix}rig_id__in": rig_ids})
        if include_rigless:
            q |= Q(**{f"{prefix}rig__isnull": True})
        return q

    def add(category, rig_id, rig_name, title, detail, due, mandatory=False, path=None):
        days = (due - today).days if due else None
        items.append(
            {
                "category": category,
                "rig_id": rig_id,
                "rig_name": rig_name or "No rig",
                "title": title,
                "detail": detail,
                "due_date": due,
                "days": days,
                "state": "no_date" if due is None else ("overdue" if days < 0 else "due_soon"),
                "mandatory": mandatory,
                "path": path or _PATH[category],
            }
        )

    horizon_end = today + timedelta(days=horizon)
    for c in _latest_certificates(RigCert.objects.filter(rig_q(""))):
        if c.valid_till and c.valid_till <= horizon_end:
            add(
                "certificate", c.rig_id, c.rig.rig_name, c.buss_cert.buss_cert_name,
                f"Certificate no. {c.certificate_no}" if c.certificate_no else "", c.valid_till,
                path="/qhse/rig-certificates?" + urlencode({"select": c.pk, "q": c.rig.rig_name}),
            )

    for s in (
        RigCertSchedule.objects.filter(rig_q("rig_cert__"), completion_dt__isnull=True, **_window("scheduled_dt", today, horizon))
        .select_related("rig_cert__rig", "rig_cert__buss_cert")
        .order_by("scheduled_dt")
    ):
        add(
            "survey", s.rig_cert.rig_id, s.rig_cert.rig.rig_name, s.rig_cert.buss_cert.buss_cert_name,
            s.get_schedule_type_display(), s.scheduled_dt,
            path="/qhse/rig-certificate-schedule?" + urlencode({"select": s.pk, "q": s.rig_cert.rig.rig_name}),
        )

    act_qs = ActivityMonitor.objects.filter(rig_q(""), completion_dt__isnull=True, **_window("scheduled_dt", today, horizon))
    if mandatory_only:
        act_qs = act_qs.filter(activity__activity_nature="M")
    for a in act_qs.select_related("rig", "activity").order_by("scheduled_dt"):
        add(
            "activity", a.rig_id, a.rig.rig_name if a.rig_id else None, a.activity.activity_name,
            a.planning_remark or "", a.scheduled_dt, mandatory=a.activity.activity_nature == "M",
            path="/qhse/activity-monitor?"
            + urlencode(
                {"select": a.pk, "activity": a.activity_id, "activity_label": a.activity.activity_name}
                | ({"rig": a.rig_id, "rig_label": a.rig.rig_name} if a.rig_id else {})
            ),
        )

    # Open actions: dated ones through the window, plus any with no target date at all.
    for ia in (
        IncidentAction.objects.filter(rig_q("incident__"))
        .filter(Q(target_date__isnull=True) | Q(target_date__lte=horizon_end))
        .exclude(action_status="CL")
        .exclude(marked_as_deleted="Y")
        .exclude(incident__marked_as_deleted="Y")
        .select_related("incident__rig")
        .order_by("target_date")
    ):
        inc = ia.incident
        add(
            "incident_action", inc.rig_id, inc.rig.rig_name if inc.rig_id else None, _short(ia.action_recommended),
            f"Incident {inc.rig_incident_no or inc.incident_no}" + (f" · {ia.action_party}" if ia.action_party else ""),
            ia.target_date, path="/qhse/incident-actions?" + urlencode({"incident": inc.pk}),
        )

    for oa in (
        OtherQhseAction.objects.filter(rig_q(""))
        .filter(Q(target_date__isnull=True) | Q(target_date__lte=horizon_end))
        .exclude(action_status="CL")
        .select_related("rig")
        .order_by("target_date")
    ):
        add(
            "corrective_action", oa.rig_id, oa.rig.rig_name if oa.rig_id else None, _short(oa.action_recommended),
            f"ICR {oa.icr_no}" + (f" · {oa.action_party}" if oa.action_party else ""),
            oa.target_date, path=f"/qhse/corrective-actions/{oa.pk}/edit",
        )

    # overdue first (most overdue at the top), then due soon (nearest first), then undated
    rank = {"overdue": 0, "due_soon": 1, "no_date": 2}
    items.sort(key=lambda i: (rank[i["state"]], i["days"] if i["days"] is not None else 0))
    return items


def _truthy(v):
    return str(v or "").lower() in ("1", "true", "y", "yes")


def _scope(request):
    """(accessible rig rows, rig ids to read, include rigless, horizon, mandatory_only) from the request."""
    try:
        horizon = int(request.query_params.get("horizon", 30))
    except ValueError:
        horizon = 30
    if horizon not in HORIZONS:
        horizon = 30
    accessible = get_accessible_rig_ids(request)  # None = every rig
    rig_qs = dashboard_rig_queryset()
    if not _truthy(request.query_params.get("inactive")):
        rig_qs = rig_qs.filter(rig_active="Y")
    if accessible is not None:
        rig_qs = rig_qs.filter(rig_id__in=accessible)
    rigs = list(rig_qs.order_by("rig_name").values("rig_id", "rig_name"))
    requested = request.query_params.get("rigs")
    if requested:
        wanted = {int(x) for x in requested.split(",") if x.strip().isdigit()}
        rig_ids = [r["rig_id"] for r in rigs if r["rig_id"] in wanted]
    else:
        rig_ids = [r["rig_id"] for r in rigs]
    include_rigless = accessible is None and not requested
    return rigs, rig_ids, include_rigless, horizon, _truthy(request.query_params.get("mandatory"))


def _narrow(items, request):
    """The list's own filters (type, state, rig), applied before the row cap."""
    cats = {c for c in (request.query_params.get("category") or "").split(",") if c in CATEGORY_KEYS}
    state = request.query_params.get("state")
    rig = request.query_params.get("rig")
    out = items
    if cats:
        out = [i for i in out if i["category"] in cats]
    if state in STATES:
        out = [i for i in out if i["state"] == state]
    if rig and rig.isdigit():
        out = [i for i in out if i["rig_id"] == int(rig)]
    return out


class ComplianceRadarView(APIView):
    permission_classes = [HasMenuPermission]
    entity_key = ENTITY_KEY

    def get(self, request):
        today = timezone.now().date()
        access = get_user_access(request)
        rigs, rig_ids, include_rigless, horizon, mandatory_only = _scope(request)
        items = collect_items(rig_ids, today, horizon, include_rigless, mandatory_only)

        def blank():
            return {c: {"overdue": 0, "due_soon": 0, "no_date": 0} for c in CATEGORY_KEYS}

        summary = blank()
        by_rig = {}
        for it in items:
            summary[it["category"]][it["state"]] += 1
            row = by_rig.setdefault(
                it["rig_id"],
                {"rig_id": it["rig_id"], "rig_name": it["rig_name"], "total_overdue": 0, "total_due_soon": 0, "categories": blank()},
            )
            row["categories"][it["category"]][it["state"]] += 1
            if it["state"] == "overdue":
                row["total_overdue"] += 1
            elif it["state"] == "due_soon":
                row["total_due_soon"] += 1

        # A rig with nothing outstanding still appears, so "all clear" is visible.
        names = {r["rig_id"]: r["rig_name"] for r in rigs}
        for rid in rig_ids:
            by_rig.setdefault(
                rid, {"rig_id": rid, "rig_name": names.get(rid, ""), "total_overdue": 0, "total_due_soon": 0, "categories": blank()}
            )
        matrix = sorted(by_rig.values(), key=lambda r: (-r["total_overdue"], -r["total_due_soon"], r["rig_name"]))

        overdue_days = [-i["days"] for i in items if i["state"] == "overdue"]
        shown = _narrow(items, request)
        return Response(
            {
                "as_of": today,
                "horizon": horizon,
                "categories": [
                    {
                        "key": c["key"],
                        "label": c["label"],
                        "path": c["path"],
                        # A rights holder on the Radar may not hold the source page's own right.
                        "can_open": bool(access["is_admin"] or access["perms"].get(c["menu_key"], {}).get("view")),
                    }
                    for c in CATEGORIES
                ],
                "rigs_filter": rigs,
                "summary": {
                    "by_category": summary,
                    "total_overdue": sum(v["overdue"] for v in summary.values()),
                    "total_due_soon": sum(v["due_soon"] for v in summary.values()),
                    "total_no_date": sum(v["no_date"] for v in summary.values()),
                    "rigs_with_overdue": sum(1 for r in matrix if r["total_overdue"]),
                    "rigs_shown": len(matrix),
                    "oldest_overdue_days": max(overdue_days) if overdue_days else None,
                },
                "rigs": matrix,
                "items": shown[:MAX_ITEMS],
                "items_total": len(shown),
                "items_truncated": len(shown) > MAX_ITEMS,
            }
        )


class ComplianceRadarExportView(APIView):
    """The same items as the page (with the list's own filters applied), as an Excel file."""

    permission_classes = [HasMenuPermission]
    entity_key = ENTITY_KEY
    action = "export"

    def get(self, request):
        today = timezone.now().date()
        _, rig_ids, include_rigless, horizon, mandatory_only = _scope(request)
        items = _narrow(collect_items(rig_ids, today, horizon, include_rigless, mandatory_only), request)
        labels = {c["key"]: c["label"] for c in CATEGORIES}
        state_label = {"overdue": "Overdue", "due_soon": "Due soon", "no_date": "No target date"}
        rows = [
            [
                labels[i["category"]], i["rig_name"], i["title"], i["detail"], "Yes" if i["mandatory"] else "",
                i["due_date"], state_label[i["state"]],
                -i["days"] if i["state"] == "overdue" else i["days"],
            ]
            for i in items
        ]
        columns = ["Type", "Rig", "Item", "Detail", "Mandatory", "Due date", "Status", "Days overdue (negative: days left)"]
        header = [f"Compliance Radar – as of {today.isoformat()}", f"Due-soon window: {horizon} days"]
        return build_xlsx_response(f"compliance-radar-{today.isoformat()}.xlsx", "Compliance Radar", header, columns, rows, wide_columns=(2, 3))


# ── Home digest ───────────────────────────────────────────────────────────

def _can_view(access, *menu_keys):
    return access["is_admin"] or any(access["perms"].get(k, {}).get("view") for k in menu_keys)


class ComplianceDigestView(APIView):
    """A few live exceptions for the Home screen. Open to any signed-in user;
    a tile appears only when the user may open the page it links to."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.now().date()
        access = get_user_access(request)
        accessible = get_accessible_rig_ids(request)
        rig_qs = dashboard_rig_queryset().filter(rig_active="Y")
        if accessible is not None:
            rig_qs = rig_qs.filter(rig_id__in=accessible)
        rig_ids = list(rig_qs.values_list("rig_id", flat=True))
        tiles = []

        # Approvals waiting for this person. Same rule as "Pending for me" on the Drilling Report list:
        # finalized reports, not yet decided, on rigs where this user is a mapped approver with the
        # Approve flag. A user who cannot approve anything gets no tile at all.
        if _can_view(access, "drilling.drilling_report"):
            profile = UserProfile.objects.filter(user_login_id=request.user.username).first()
            approver_rigs = (
                set(
                    ApproverMappingDtl.objects.filter(
                        approver_mapping__approval_code__approval_code=DRILLING_APPROVAL_CODE,
                        approver_mapping__approver_user_id=profile.user_id,
                        approver_mapping__approver_active="Y",
                        approve_yn="Y",
                    ).values_list("rig_id", flat=True)
                )
                if profile
                else set()
            )
            if approver_rigs:
                waiting = (
                    DrillingDtl.objects.filter(rig_id__in=approver_rigs, cr_status="F")
                    .filter(Q(l1_approval_status__isnull=True) | Q(l1_approval_status__in=("", "N")))
                    .count()
                )
                tiles.append(
                    {
                        "key": "reports_to_approve",
                        "label": "Drilling reports to approve",
                        "count": waiting,
                        "sub": "waiting for your approval",
                        "tone": "critical",
                        "path": "/drilling/drilling-report?scope=pending_for_me",
                    }
                )

        # Operations: silent rigs and contracts ending, as on Fleet Operating Picture
        if _can_view(access, "dashboards.fleet_operating_picture"):
            open_rigs = set(
                DrillingHdr.objects.filter(rig_id__in=rig_ids, drilling_completion_dt__isnull=True).values_list("rig_id", flat=True)
            )
            if open_rigs:
                last = {}
                for rid, dt in (
                    DrillingDtl.objects.filter(rig_id__in=open_rigs)
                    .order_by("rig_id", "-drilling_dtl_dt")
                    .values_list("rig_id", "drilling_dtl_dt")
                ):
                    last.setdefault(rid, dt)
                silent = sum(1 for rid in open_rigs if rid not in last or (today - last[rid]).days >= SILENT_DAYS)
                tiles.append(
                    {
                        "key": "silent_rigs",
                        "label": "Silent rigs",
                        "count": silent,
                        "sub": f"open well, no daily report for {SILENT_DAYS}+ days",
                        "tone": "critical",
                        "path": "/dashboards/fleet-operating-picture?status=silent",
                    }
                )
        if _can_view(access, "dashboards.contract_exposure"):
            lines = current_contract_by_rig(rig_ids, today)
            ending = sum(
                1
                for ln in lines.values()
                if ln.rig_active_to and today <= ln.rig_active_to <= today + timedelta(days=CONTRACT_ENDING_DAYS)
            )
            tiles.append(
                {
                    "key": "contracts_ending",
                    "label": "Contracts ending",
                    "count": ending,
                    "sub": f"within {CONTRACT_ENDING_DAYS} days",
                    "tone": "warning",
                    "path": "/dashboards/contract-exposure?status=ending_soon",
                }
            )

        # Compliance: overdue only (what is due soon is on the Radar itself). Every link carries
        # the same type and "overdue" filter as the number on its tile.
        radar_ok = _can_view(access, ENTITY_KEY)
        if radar_ok or any(_can_view(access, c["menu_key"]) for c in CATEGORIES):
            items = [i for i in collect_items(rig_ids, today, 0, include_rigless=accessible is None) if i["state"] == "overdue"]
            counts = {k: 0 for k in CATEGORY_KEYS}
            for it in items:
                counts[it["category"]] += 1
            groups = [
                ("overdue_certs", "Overdue certificates and surveys", ("certificate", "survey")),
                ("overdue_activities", "Overdue activities", ("activity",)),
                ("overdue_actions", "Overdue actions", ("incident_action", "corrective_action")),
            ]
            for key, label, cats in groups:
                if radar_ok:
                    path = "/dashboards/compliance-radar?" + urlencode({"category": ",".join(cats), "state": "overdue"})
                    visible = True
                else:
                    # Without the Radar right, only count and link what the user can open themselves.
                    cats = tuple(c for c in cats if _can_view(access, _MENU[c]))
                    visible = bool(cats)
                    path = _PATH[cats[0]] if visible else None
                if visible:
                    tiles.append(
                        {
                            "key": key,
                            "label": label,
                            "count": sum(counts[c] for c in cats),
                            "sub": "past their due date",
                            "tone": "critical",
                            "path": path,
                        }
                    )

        # Safety: hazard cards still open after 30 days (raised in the last 12 months), for the user's rigs
        if _can_view(access, "qhse.hazard_id_card"):
            newest, oldest = today - timedelta(days=HAZARD_OPEN_DAYS), today - timedelta(days=365)
            n = (
                HazardCard.objects.exclude(marked_as_deleted="Y")
                .exclude(haz_id_card_status="C")
                .filter(rig_id__in=rig_ids, event_dt__date__lt=newest, event_dt__date__gte=oldest)
                .count()
            )
            tiles.append(
                {
                    "key": "open_hazards",
                    "label": "Hazard cards open 30+ days",
                    "count": n,
                    "sub": "raised in the last 12 months",
                    "tone": "warning",
                    "path": "/qhse/hazard-id-card?"
                    + urlencode({"status": "open", "date_from": oldest.isoformat(), "date_to": (newest - timedelta(days=1)).isoformat()}),
                }
            )

        # IT: warranty about to run out. (Expired is not shown: most legacy assets are long out of warranty.)
        if _can_view(access, "dashboards.it_asset_overview", "it_asset.it_assets"):
            n = MstItAsset.objects.filter(
                it_asset_active="Y", it_asset_warranty_upto__gte=today, it_asset_warranty_upto__lte=today + timedelta(days=90)
            ).count()
            tiles.append(
                {
                    "key": "warranty_expiring",
                    "label": "Warranty expiring",
                    "count": n,
                    "sub": "active IT assets, within 90 days",
                    "tone": "warning",
                    "path": "/it-asset/it-assets?warranty_status=expiring_soon&active=Y",
                }
            )

        return Response({"as_of": today, "tiles": tiles})
