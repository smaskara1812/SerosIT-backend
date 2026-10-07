"""QHSE → Training Certificate to Rank Mapping — rebuild of legacy
frmCert_To_Rank_Mapping (which ranks a training certificate applies to).

Rules ported from frmCert_To_Rank_Mapping.aspx(.cs) and its stored procedure:
  - Pick a certificate; its saved ranks load. Add ranks by choosing an active
    Training Group (only to narrow the rank list) and a Category, then
    ticking the ranks wanted. The candidates are that group's ranks in that
    category, minus ranks the certificate already has under it.
  - Nothing is saved until Save: new ranks are inserted (Active by default)
    and changed Active flags are updated, together.
  - A saved rank can be deleted. Legacy had no certificate-level delete.
  - Categories offered are the ones mapped to the signed-in user (an App
    Admin sees all), as on the Training Group page.
Legacy repeats rank 127 under two certificates; kept as imported, and only
new rows are held to the no-repeat rule.
Excel export is an addition.
"""

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from . import audit as _audit
from .models import (
    CertToRankMapping,
    FsCatgToRankMapping,
    HseTrainingGroupDtl,
    HseTrainingGroupHdr,
    MstCert,
    MstFsCategory,
    UserProfile,
)
from .permissions import HasMenuPermission
from .training_group import allowed_category_ids
from .xlsx_export import build_xlsx_response

ENTITY_KEY = "qhse.cert_to_rank_mapping"
TITLE = "Training Certificate to Rank Mapping"
YES_NO = ("Y", "N")


def _row(m, repeat_keys):
    return {
        "id": m.pk,
        "rank": m.rank_id,
        "rank_name": m.rank.rank_name,
        "fs_category": m.fs_category_id,
        "fs_category_name": m.fs_category.fs_category_name,
        "active": m.cert_to_rank_mapping_active,
        "is_repeat": repeat_keys[(m.fs_category_id, m.rank_id)] > 1,
    }


def _detail(cert):
    maps = list(CertToRankMapping.objects.filter(cert=cert).select_related("rank", "fs_category").order_by("rank__rank_name", "pk"))
    counts = {}
    for m in maps:
        counts[(m.fs_category_id, m.rank_id)] = counts.get((m.fs_category_id, m.rank_id), 0) + 1
    return {"cert_id": cert.pk, "cert_name": cert.cert_name, "rows": [_row(m, counts) for m in maps]}


def _uid(request):
    p = UserProfile.objects.filter(user_login_id=request.user.username).first()
    return p.user_id if p else None


class CertToRankMappingViewSet(viewsets.ViewSet):
    entity_key = ENTITY_KEY
    permission_classes = [HasMenuPermission]
    lookup_value_regex = r"\d+"
    # Saving ranks is the page's one Save action, so Add or Edit allows it.
    action_perm_overrides = {"save": ("add", "edit"), "delete_row": ("edit", "delete")}

    def list(self, request):
        qs = (
            MstCert.objects.annotate(
                rank_count=Count("rank_mappings"), active_count=Count("rank_mappings", filter=Q(rank_mappings__cert_to_rank_mapping_active="Y"))
            )
            .filter(rank_count__gt=0)
            .order_by("cert_name")
        )
        search = request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(cert_name__icontains=search)
        return Response(
            [{"cert_id": c.pk, "cert_name": c.cert_name, "rank_count": c.rank_count, "active_count": c.active_count} for c in qs]
        )

    def retrieve(self, request, pk=None):
        cert = MstCert.objects.filter(pk=pk).first()
        if not cert:
            return Response({"detail": "Not found."}, status=404)
        return Response(_detail(cert))

    @action(detail=False, methods=["get"], url_path="certificates")
    def certificates(self, request):
        """Every certificate, flagged when it already has ranks mapped."""
        mapped = set(CertToRankMapping.objects.values_list("cert_id", flat=True))
        return Response([{"id": c.pk, "name": c.cert_name, "has_mappings": c.pk in mapped} for c in MstCert.objects.order_by("cert_name")])

    @action(detail=False, methods=["get"], url_path="groups")
    def groups(self, request):
        qs = HseTrainingGroupHdr.objects.filter(training_group_hdr_active="Y").order_by("training_group_hdr_name")
        return Response([{"id": g.pk, "name": g.training_group_hdr_name} for g in qs])

    @action(detail=False, methods=["get"], url_path="categories")
    def categories(self, request):
        qs = MstFsCategory.objects.order_by("fs_category_name")
        allowed = allowed_category_ids(request)
        if allowed is not None:
            qs = qs.filter(pk__in=allowed)
        return Response([{"id": c.pk, "name": c.fs_category_name} for c in qs])

    @action(detail=False, methods=["get"], url_path="candidates")
    def candidates(self, request):
        p = request.query_params
        cert, group, category = p.get("cert"), p.get("group"), p.get("category")
        if not all(v and v.isdigit() for v in (cert, group, category)):
            return Response({"error": "?cert=, ?group= and ?category= are required"}, status=400)
        allowed = allowed_category_ids(request)
        if allowed is not None and int(category) not in allowed:
            return Response([])
        taken = CertToRankMapping.objects.filter(cert_id=cert, fs_category_id=category).values_list("rank_id", flat=True)
        dtls = (
            HseTrainingGroupDtl.objects.filter(hdr_id=group, fs_category_id=category)
            .exclude(rank_id__in=taken)
            .select_related("rank")
            .order_by("rank__rank_name")
        )
        seen, out = set(), []
        for d in dtls:
            if d.rank_id not in seen:
                seen.add(d.rank_id)
                out.append({"id": d.rank_id, "name": d.rank.rank_name})
        return Response(out)

    @action(detail=False, methods=["post"], url_path="save")
    def save(self, request):
        data = request.data
        cert = MstCert.objects.filter(pk=data.get("cert")).first()
        if not cert:
            return Response({"cert": ["Please choose a certificate."]}, status=400)
        adds, updates = data.get("adds") or [], data.get("updates") or []
        if not adds and not updates:
            return Response({"error": "There is nothing to save."}, status=400)

        allowed = allowed_category_ids(request)
        existing = {(m.fs_category_id, m.rank_id) for m in CertToRankMapping.objects.filter(cert=cert)}
        seen, new_rows = set(), []
        for a in adds:
            cat, rank, active = a.get("category"), a.get("rank"), a.get("active", "Y")
            if active not in YES_NO:
                return Response({"error": "Active must be Yes or No."}, status=400)
            if allowed is not None and cat not in allowed:
                return Response({"error": "You don't have access to one of the chosen categories."}, status=400)
            if not FsCatgToRankMapping.objects.filter(fs_category_id=cat, rank_id=rank).exists():
                return Response({"error": "A chosen rank doesn't belong to its category."}, status=400)
            if (cat, rank) in existing or (cat, rank) in seen:
                return Response({"error": "A chosen rank is already mapped to this certificate under that category."}, status=400)
            seen.add((cat, rank))
            new_rows.append((cat, rank, active))

        changed = []
        for u in updates:
            if u.get("active") not in YES_NO:
                return Response({"error": "Active must be Yes or No."}, status=400)
            m = CertToRankMapping.objects.filter(pk=u.get("id"), cert=cert).select_related("rank").first()
            if not m:
                return Response({"error": "One of the ranks being changed no longer exists. Reload the page."}, status=400)
            if m.cert_to_rank_mapping_active != u["active"]:
                changed.append((m, u["active"]))

        uid, now = _uid(request), timezone.now()
        with transaction.atomic():
            for cat, rank, active in new_rows:
                CertToRankMapping.objects.create(
                    cert=cert, fs_category_id=cat, rank_id=rank, cert_to_rank_mapping_active=active, cr_user_id=uid or 1, cr_dt=now
                )
            for m, active in changed:
                old = m.cert_to_rank_mapping_active
                m.cert_to_rank_mapping_active, m.mod_user_id, m.mod_dt = active, uid, now
                m.save(update_fields=["cert_to_rank_mapping_active", "mod_user_id", "mod_dt"])
        changes = {}
        if new_rows:
            changes["ranks_added"] = {"old": None, "new": len(new_rows)}
        for m, active in changed:
            changes[f"active: {m.rank.rank_name}"] = {"old": "Y" if active == "N" else "N", "new": active}
        _audit.record_action(request, "update" if existing else "create", ENTITY_KEY, cert.pk, f"{TITLE} — {cert.cert_name}", changes or None)
        return Response(_detail(cert))

    @action(detail=False, methods=["delete"], url_path=r"row/(?P<row_id>\d+)")
    def delete_row(self, request, row_id=None):
        m = CertToRankMapping.objects.filter(pk=row_id).select_related("cert", "rank").first()
        if not m:
            return Response({"detail": "Not found."}, status=404)
        label = f"{TITLE} — {m.cert.cert_name} / {m.rank.rank_name}"
        m.delete()
        _audit.record_action(request, "delete", ENTITY_KEY, int(row_id), label)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request):
        qs = CertToRankMapping.objects.select_related("cert", "rank", "fs_category")
        search = request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(cert__cert_name__icontains=search)
        qs = qs.order_by("cert__cert_name", "fs_category__fs_category_name", "rank__rank_name")
        rows = [
            [m.cert.cert_name, m.fs_category.fs_category_name, m.rank.rank_name, "Yes" if m.cert_to_rank_mapping_active == "Y" else "No"]
            for m in qs
        ]
        _audit.record_action(
            request, "export", ENTITY_KEY, record_label=f"{TITLE} export",
            changes={**{k: {"old": None, "new": v} for k, v in request.query_params.items() if v}, "rows_exported": {"old": None, "new": len(rows)}},
        )
        return build_xlsx_response(f"{TITLE}.xlsx", TITLE[:31], [TITLE], ["Certificate", "Category", "Rank", "Active"], rows)
