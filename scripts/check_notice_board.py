"""Checks the Notice Board with real requests as people holding exactly the rights named; everything runs in one
transaction that is rolled back.

    cd backend
    .venv/bin/python scripts/check_notice_board.py
"""
import os, sys, django, datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings"); django.setup()
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework.test import APIClient
from core.models import UserProfile, UserPermission, Notice
from core.permissions import invalidate_user_access
from django.utils import timezone

class Rollback(Exception): pass
fails=[]
def ok(name, cond, detail=""):
    print(("ok   " if cond else "FAIL ")+name+(f"  {detail}" if not cond else ""))
    if not cond: fails.append(name)

def mk(n, keys=(), flags=("view",), admin=False):
    U=get_user_model(); u=U.objects.create_user(username=n, password="x")
    uid=(UserProfile.objects.order_by("-user_id").first().user_id or 0)+1
    UserProfile.objects.create(user_id=uid, user_login_id=n, is_app_admin=admin)
    for k in keys:
        UserPermission.objects.create(user_id=uid, menu_key=k, can_view="view" in flags, can_add="add" in flags, can_edit="edit" in flags, can_delete="delete" in flags, can_export=False)
    invalidate_user_access(n)
    c=APIClient(HTTP_HOST="localhost"); c.force_authenticate(u); return c

try:
    with transaction.atomic():
        now=timezone.now().replace(microsecond=0)
        iso=lambda d: d.strftime("%Y-%m-%dT%H:%M:%S")
        admin=mk("zznb0", admin=True)
        poster=mk("zznb1", ["admin.notice_board"], ("view","add","edit","delete"))
        viewer=mk("zznb2", ["admin.notice_board"], ("view",))
        nobody=mk("zznb3")
        good={"title":"Safety stand-down","message":"All rigs: stand-down at 10:00.","kind":"S","is_pinned":"Y","is_published":"Y","starts_at":iso(now-datetime.timedelta(hours=1)),"ends_at":iso(now+datetime.timedelta(days=2)),"link_url":"/qhse/incident-details"}
        r=poster.post("/api/admin/notices/", good, format="json"); ok("a rights-holder can post", r.status_code==201, str(r.content[:200]))
        ok("posted by is the poster, not user 1", r.json().get("posted_by") not in ("", None) and r.json().get("posted_by") != __import__("core.models",fromlist=["MstUser"]).MstUser.objects.filter(user_id=1).values_list("user_name",flat=True).first(), str(r.json().get("posted_by")))
        su=get_user_model().objects.create_superuser(username="zznb9", password="x"); sc=APIClient(HTTP_HOST="localhost"); sc.force_authenticate(su)
        rs=sc.post("/api/admin/notices/", {**good,"title":"From a superuser","link_url":"","is_pinned":"N"}, format="json")
        ok("a Django superuser with no profile is shown by their login, not as user 1", rs.status_code==201 and rs.json().get("posted_by")=="zznb9", str(rs.content[:160]))
        nid=r.json().get("notice_id"); ok("status is live", r.json().get("status")=="live"); ok("link label defaults to Open", r.json().get("link_label")=="Open")
        ok("admin can post", admin.post("/api/admin/notices/", {**good,"title":"Admin one","link_url":"","is_pinned":"N"}, format="json").status_code==201)
        ok("view-only cannot post", viewer.post("/api/admin/notices/", good, format="json").status_code==403)
        ok("no rights cannot list", nobody.get("/api/admin/notices/").status_code==403)
        ok("view-only can list", viewer.get("/api/admin/notices/").status_code==200)
        ok("view-only cannot delete", viewer.delete(f"/api/admin/notices/{nid}/").status_code==403)
        bad=lambda **kw: poster.post("/api/admin/notices/", {**good, **kw}, format="json")
        ok("end is required", bad(ends_at=None).status_code==400)
        ok("end must be after start", bad(ends_at=iso(now-datetime.timedelta(hours=3))).status_code==400)
        ok("javascript: link refused", bad(link_url="javascript:alert(1)").status_code==400)
        ok("protocol-relative link refused", bad(link_url="//evil.example").status_code==400)
        ok("http link refused", bad(link_url="http://x.example").status_code==400)
        ok("https link accepted", bad(link_url="https://seros.example/x", title="https ok", is_pinned="N").status_code==201)
        ok("blank title refused", bad(title="   ").status_code==400)
        ok("title too long refused", bad(title="x"*81).status_code==400)
        # live endpoint: scheduled, expired and draft never show
        mkn=lambda t,s,e,pub="Y",pin="N": Notice.objects.create(title=t,message="m",kind="I",is_pinned=pin,is_published=pub,starts_at=s,ends_at=e,cr_user_id=1,cr_dt=now)
        mkn("sched", now+datetime.timedelta(hours=2), now+datetime.timedelta(days=1)); mkn("old", now-datetime.timedelta(days=3), now-datetime.timedelta(days=1)); mkn("draft", now-datetime.timedelta(hours=1), now+datetime.timedelta(days=1), pub="N")
        live=nobody.get("/api/notices/live/"); titles=[n["title"] for n in live.json()]
        ok("anyone signed in can read live notices", live.status_code==200)
        ok("only live ones are shown", "Safety stand-down" in titles and not ({"sched","old","draft"} & set(titles)), str(titles))
        ok("pinned comes first", titles[0]=="Safety stand-down", str(titles))
        ok("live reply has no author or audit fields", not ({"cr_user_id","posted_by","mod_dt"} & set(live.json()[0])))
        ok("anonymous cannot read live", APIClient(HTTP_HOST="localhost").get("/api/notices/live/").status_code in (401,403))
        for st,exp in (("live",{"Safety stand-down","Admin one","https ok"}),("scheduled",{"sched"}),("expired",{"old"}),("draft",{"draft"})):
            got={n["title"] for n in poster.get(f"/api/admin/notices/?status={st}").json().get("results",[])}
            ok(f"tab {st}", exp<=got and (st!="live" or "sched" not in got), str(got))
        r=poster.patch(f"/api/admin/notices/{nid}/", {"ends_at": iso(now)}, format="json"); ok("end now works", r.status_code==200 and r.json()["status"]=="expired", str(r.content[:150]))
        ok("delete works", poster.delete(f"/api/admin/notices/{nid}/").status_code==204)
        ok("admin notice board is not offered as a dropdown source", nobody.get("/api/admin/notices/?fields=title").status_code==403)
        raise Rollback()
except Rollback: pass
if fails:
    print("\nFAILED:", fails)
    sys.exit(1)
print("\nAll notice checks passed.")
