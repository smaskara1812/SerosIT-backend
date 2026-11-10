"""Checks Customise Sero (outfits, the daily pick, the banner's Sero section) with real requests as people holding exactly the rights named. Everything runs in one
transaction that is rolled back.

    cd backend
    .venv/bin/python scripts/check_sero_look.py
"""
import os, sys, django, datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings"); django.setup()
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework.test import APIClient
from core.models import UserProfile, UserPermission, BannerEvent, SeroOutfit, SeroSetting
from core.permissions import invalidate_user_access
from core import sero_look as S
from core.banner_events import clean_design, DEFAULT_DESIGN

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

LOOK={"head":{"style":"hardhat","color":"#facc15"},"top":{"style":"kurta","color":"#f59e0b","print":"dots","printColor":"#fde68a","trim":"all","trimColor":"#9a3412"},"neck":{"style":"scarf","color":"#b91c1c","stripe":"#ffffff"},"face":{"style":"shades","color":"#111827"},"extra":{"style":"garland","color":"#f97316"}}

try:
    with transaction.atomic():
        SeroOutfit.objects.all().delete(); SeroSetting.objects.all().delete()
        admin=mk("zzsr0", admin=True)
        owner=mk("zzsr1", ["admin.sero_look"], ("view","add","edit","delete"))
        viewer=mk("zzsr2", ["admin.sero_look"], ("view",))
        banner_ed=mk("zzsr3", ["admin.banner_events"], ("view","add","edit"))
        nobody=mk("zzsr4")

        # --- who may read and write
        ok("a person with no right cannot read outfits", nobody.get("/api/sero/outfits/").status_code==403)
        r=owner.get("/api/sero/outfits/")
        ok("a rights-holder reads outfits", r.status_code==200)
        names=[o["name"] for o in r.json()["outfits"]]
        ok("the ready-made outfits are added once", len(names)==len(S.STARTERS) and "Diwali kurta" in names, names)
        ok("they are not added twice", len(owner.get("/api/sero/outfits/").json()["outfits"])==len(S.STARTERS))
        ok("a banner editor may read the outfits to choose one", banner_ed.get("/api/sero/outfits/").status_code==200)
        ok("a banner editor may not add one", banner_ed.post("/api/sero/outfits/", {"name":"x","look":LOOK}, format="json").status_code==403)
        ok("a viewer may not add one", viewer.post("/api/sero/outfits/", {"name":"x","look":LOOK}, format="json").status_code==403)
        ok("a viewer may not change the settings", viewer.put("/api/sero/settings/", {"weekday_mode":"plain","weekend_mode":"plain"}, format="json").status_code==403)

        # --- creating and validating
        r=owner.post("/api/sero/outfits/", {"name":"Festival gold","look":LOOK,"in_pool":True}, format="json")
        ok("an outfit is created", r.status_code==201, r.content[:200])
        mine=[o for o in r.json()["outfits"] if o["name"]=="Festival gold"][0]
        ok("it keeps its look and pool flag", mine["look"]==S.clean_look(LOOK) and mine["in_pool"] is True)
        bad=lambda look: owner.post("/api/sero/outfits/", {"name":"b","look":look}, format="json").status_code
        ok("an unknown part is refused", bad({**LOOK,"head":{"style":"crown","color":"#facc15"}})==400)
        ok("an unknown print is refused", bad({**LOOK,"top":{**LOOK["top"],"print":"tartan"}})==400)
        ok("a bad colour is refused", bad({**LOOK,"neck":{"style":"scarf","color":"red"}})==400)
        ok("an unknown key is refused", bad({**LOOK,"cape":{}})==400)
        ok("markup in a name is refused", owner.post("/api/sero/outfits/", {"name":"<b>x","look":LOOK}, format="json").status_code==400)
        ok("an empty name is refused", owner.post("/api/sero/outfits/", {"name":" ","look":LOOK}, format="json").status_code==400)
        ok("headphones, a long kurta and shoe colour are accepted", owner.post("/api/sero/outfits/", {"name":"gear","look":{**LOOK,"head":{"style":"headphones","color":"#111827"},"top":{**LOOK["top"],"length":"long"},"shoes":{"color":"#ff0000"}}}, format="json").status_code==201)
        ok("santa hat, party hat, round specs and a necktie are accepted", owner.post("/api/sero/outfits/", {"name":"xmas","look":{**LOOK,"head":{"style":"santa","color":"#dc2626"},"face":{"style":"specs","color":"#111827"},"extra":{"style":"necktie","color":"#16a34a"}}}, format="json").status_code==201 and owner.post("/api/sero/outfits/", {"name":"party","look":{**LOOK,"head":{"style":"party","color":"#ec4899"}}}, format="json").status_code==201)
        ok("cowboy hat, chef hat, dupatta, ID card and medal are accepted", all(owner.post("/api/sero/outfits/", {"name":n,"look":{**LOOK,"head":{"style":h,"color":"#92400e"},"neck":{"style":k,"color":"#7c3aed","stripe":"#fbbf24"},"extra":{"style":e,"color":"#facc15"}}}, format="json").status_code==201 for n,h,k,e in (("w1","cowboy","dupatta","medal"),("w2","chef","idcard","none"))))
        ok("an unknown kurta length is refused", bad({**LOOK,"top":{**LOOK["top"],"length":"tiny"}})==400)
        ok("a bad shoe colour is refused", bad({**LOOK,"shoes":{"color":"red"}})==400)
        ok("an empty look gets the default", S.clean_look(None)["top"]["style"]=="none" and S.clean_look(None)["head"]["style"]=="hardhat")
        r=owner.patch(f"/api/sero/outfits/{mine['id']}/", {"name":"Festival gold 2","in_pool":False}, format="json")
        ok("an outfit is renamed and taken out of the pool", r.status_code==200 and [o for o in r.json()["outfits"] if o["id"]==mine["id"]][0]["in_pool"] is False)
        owner.patch(f"/api/sero/outfits/{mine['id']}/", {"in_pool":True}, format="json")

        # --- the daily pick
        for n in (1,2,3,4,7):
            ids=list(range(10,10+n))
            seq=[S.pool_pick(i, ids) for i in range(n*40)]
            ok(f"pick, pool of {n}: deterministic", seq==[S.pool_pick(i, ids) for i in range(n*40)])
            ok(f"pick, pool of {n}: every outfit once per round", all(sorted(seq[c*n:(c+1)*n])==ids for c in range(40)) if n>2 else set(seq)==set(ids))
            ok(f"pick, pool of {n}: no outfit two days running", n==1 or all(a!=b for a,b in zip(seq, seq[1:])))
        ok("pick, empty pool is nobody", S.pool_pick(5, []) is None)
        ok("the pick does not depend on the order ids are given", S.pool_pick(9,[3,1,2,5])==S.pool_pick(9,[5,2,1,3]))
        days=[datetime.date(2026,11,2)+datetime.timedelta(d) for d in range(0,56)]
        wk=[S._day_index(d)[1] for d in days if not S._day_index(d)[0]]; we=[S._day_index(d)[1] for d in days if S._day_index(d)[0]]
        ok("weekday and weekend day numbers rise by one", all(b-a==1 for a,b in zip(wk,wk[1:])) and all(b-a==1 for a,b in zip(we,we[1:])))

        # --- the day's settings
        pool=[o for o in owner.get("/api/sero/outfits/").json()["outfits"] if o["in_pool"]]
        ok("starters supply a pool", len(pool)>=3)
        sat=datetime.date(2026,11,7); mon=datetime.date(2026,11,9)
        ok("plain by default: no outfit any day", S.day_outfit(sat) is None and S.day_outfit(mon) is None)
        fixed=[o for o in owner.get("/api/sero/outfits/").json()["outfits"] if o["name"]=="Safety hat"][0]["id"]
        ok("fixed needs an outfit", owner.put("/api/sero/settings/", {"weekday_mode":"fixed","weekend_mode":"plain"}, format="json").status_code==400)
        ok("an unknown mode is refused", owner.put("/api/sero/settings/", {"weekday_mode":"random","weekend_mode":"plain"}, format="json").status_code==400)
        r=owner.put("/api/sero/settings/", {"weekday_mode":"fixed","weekday_outfit":fixed,"weekend_mode":"daily"}, format="json")
        ok("weekdays fixed, weekends daily is saved", r.status_code==200 and r.json()["settings"]["weekday_outfit"]==fixed, r.content[:200])
        ok("a weekday wears the fixed outfit", S.day_outfit(mon).outfit_id==fixed)
        sats=[S.day_outfit(sat+datetime.timedelta(7*i)).outfit_id for i in range(12)]; suns=[S.day_outfit(sat+datetime.timedelta(7*i+1)).outfit_id for i in range(12)]
        ok("weekends come from the pool", set(sats+suns)<= {o["id"] for o in pool})
        ok("two weekends running do not match all the way", len(set(sats+suns))>1)
        inter=[x for pair in zip(sats,suns) for x in pair]
        ok("no outfit two weekend days running", all(a!=b for a,b in zip(inter,inter[1:])), inter)
        for o in pool: owner.patch(f"/api/sero/outfits/{o['id']}/", {"in_pool":False}, format="json")
        ok("daily with an empty pool is refused", owner.put("/api/sero/settings/", {"weekday_mode":"plain","weekend_mode":"daily"}, format="json").status_code==400)
        for o in pool: owner.patch(f"/api/sero/outfits/{o['id']}/", {"in_pool":True}, format="json")

        # --- the banner's Sero section
        d0=clean_design({})
        ok("a banner shows no Sero by default", d0["sero"]=={"show":False,"outfit":None,"x":None,"y":None})
        def design(**sero): return {**DEFAULT_DESIGN, "sero":sero}
        ok("a banner may show him in the day's outfit", clean_design(design(show=True, outfit=None))["sero"]=={"show":True,"outfit":None,"x":None,"y":None})
        ok("a banner may name an outfit", clean_design(design(show=True, outfit=fixed))["sero"]["outfit"]==fixed)
        def rejects(**sero):
            try: clean_design(design(**sero)); return False
            except Exception: return True
        ok("an outfit that does not exist is refused", rejects(show=True, outfit=999999))
        ok("show must be true or false", rejects(show="yes", outfit=None))
        ok("an outfit must be a number", rejects(show=True, outfit="x"))
        ok("a banner may place Sero", clean_design(design(show=True, outfit=None, x=40, y=100))["sero"]["x"]==40)
        ok("Sero's place needs both x and y", rejects(show=True, outfit=None, x=40, y=None))
        ok("Sero's place stays within 0 to 100", rejects(show=True, outfit=None, x=140, y=0))
        ok("an old design without a place reads as the usual corner", clean_design(design(show=True, outfit=None))["sero"]["x"] is None)
        ok("an unknown Sero key is refused", rejects(show=True, outfit=None, hat=1))
        ok("a saved design with a deleted outfit reads as the day's outfit", clean_design(design(show=True, outfit=999999), strict=False)["sero"]=={"show":True,"outfit":None,"x":None,"y":None})

        # --- the outfit that comes with the live banner
        today=timezone.now().date()
        BannerEvent.objects.filter(starts_on__lte=today, ends_on__gte=today).update(is_published="N")
        ev=BannerEvent.objects.create(name="zz sero test", starts_on=today, ends_on=today, repeat_yearly="N", priority=100, is_published="Y", design=clean_design(design(show=True, outfit=fixed)), cr_user_id=1, cr_dt=timezone.now())
        got=admin.get("/api/banner/active/").json()
        ok("the live banner's outfit comes with it", got["sero"] and got["sero"]["id"]==fixed and got["event"]["design"]["sero"]["show"] is True, got.get("sero"))
        other=[o["id"] for o in pool][0]
        ev.design=clean_design(design(show=False, outfit=None)); ev.save()
        got=admin.get("/api/banner/active/").json()
        expect=S.day_outfit(today)
        ok("a banner on 'follow the day' wears the day's outfit", (got["sero"] or {}).get("id")==(expect.outfit_id if expect else None))
        ev.is_published="N"; ev.save()
        got=admin.get("/api/banner/active/").json()
        ok("with no banner the day's outfit still comes", got["event"] is None and (got["sero"] or {}).get("id")==(expect.outfit_id if expect else None))

        # --- deleting: a warning first, then a clean-up
        ev.design=clean_design(design(show=True, outfit=fixed)); ev.is_published="Y"; ev.save()
        r=owner.delete(f"/api/sero/outfits/{fixed}/")
        ok("deleting an outfit in use is refused with who uses it", r.status_code==409 and r.json()["used_by"]["banners"]==["zz sero test"] and r.json()["used_by"]["weekdays"] is True, r.content[:200])
        ok("the outfit is still there", SeroOutfit.objects.filter(pk=fixed).exists())
        ok("a person without Delete cannot confirm", viewer.delete(f"/api/sero/outfits/{fixed}/?confirm=1").status_code==403)
        r=owner.delete(f"/api/sero/outfits/{fixed}/?confirm=1")
        ok("confirmed, it is deleted", r.status_code==200 and not SeroOutfit.objects.filter(pk=fixed).exists())
        ev.refresh_from_db()
        ok("the banner now follows the day's outfit", ev.design["sero"]["outfit"] is None and ev.design["sero"]["show"] is True)
        ok("weekdays fall back to plain", S.settings_row().weekday_mode=="plain" and S.settings_row().weekday_outfit is None)
        free=owner.post("/api/sero/outfits/", {"name":"Spare","look":LOOK}, format="json").json()["outfits"]
        spare=[o for o in free if o["name"]=="Spare"][0]
        ok("an unused outfit deletes without a warning", owner.delete(f"/api/sero/outfits/{spare['id']}/").status_code==200)
        ok("deleting what is gone is a 404", owner.delete(f"/api/sero/outfits/{spare['id']}/").status_code==404)
        raise Rollback()
except Rollback:
    pass
print("\n"+("ALL OK" if not fails else f"{len(fails)} FAILED: {fails}"))
sys.exit(1 if fails else 0)
