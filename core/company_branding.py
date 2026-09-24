"""Resolves which company's letterhead (name + logo images) applies to a
given Rig at a given effective date — reused wherever a print/PDF report
needs to show "which company issued this record" (first use: the QHSE
Incident Flash Report). Ported from legacy eos.Fnc_Get_Company_Cost_Centre_Id's
'RIG' mode, as called via eos.Prc_Doc_To_Sign_Mapping's
'Get_Header_Footer_Rig_Id' record status.

Unlike the legacy function, company name resolution here has no
hardcoded Company_Id special cases (it originally hardcoded a one-time
EOSIL -> OGD Services Limited cutover for Company_Id 10, and only
consulted Company_Name_Change for Company_Id 308/309). This version
always checks Company_Name_Change first, for whichever Company_Id
resolves, and falls back to Mst_Company only when no name-change row
covers that date — fully data-driven, so a future company rename or
brand cutover just needs a new Company_Name_Change row, not a code
change. This does depend on Company_Name_Change's own date ranges being
accurate for every company that needs historical fidelity.

Deliberately kept separate from any future user/employee -> company
resolver (the legacy function's 'EMPLOYEE'/'APPLICANT' modes) — see
project memory qhse_incident_report_dynamic_branding for why.
"""

import os

from django.conf import settings
from django.db.models import Q

from .models import CompanyNameChange, CostCentreToCompanyMapping, MstCompany, MstCostCentre

LETTERHEAD_DIR = "Letterhead Logo"
IMAGE_FILES = {
    "header_path": "Header.jpg",
    "footer_path": "Footer.jpg",
    "small_logo_path": "Small_Company_Logo.jpg",
    "big_logo_path": "Big_Company_Logo.jpg",
    "stamp_path": "Company_Stamp.jpg",
}


def _resolve_company_id(rig_id, effective_date):
    cost_centre = MstCostCentre.objects.filter(rig_id=rig_id).first()
    if not cost_centre:
        return None
    mapping = (
        CostCentreToCompanyMapping.objects.filter(cost_centre_id=cost_centre.pk, mapping_from__lte=effective_date)
        .filter(Q(mapping_to__isnull=True) | Q(mapping_to__gte=effective_date))
        .order_by("-mapping_from")
        .first()
    )
    return mapping.company_id if mapping else None


def _resolve_company_name(company_id, effective_date):
    change = (
        CompanyNameChange.objects.filter(company_id=company_id, from_date__lte=effective_date)
        .filter(Q(to_date__isnull=True) | Q(to_date__gte=effective_date))
        .order_by("-from_date")
        .first()
    )
    if change:
        return change.company_name, change.company_short_name

    company = MstCompany.objects.filter(pk=company_id).first()
    if company:
        return company.company_name, company.company_abrv
    return None, None


def resolve_rig_company_branding(rig_id, effective_date):
    """Returns a dict: company_id, company_name, company_short_name, and one
    *_path per IMAGE_FILES key (a path relative to MEDIA_ROOT, under
    "Letterhead Logo/<short_name>/"). A key is None wherever the resolved
    company has no matching image on disk — deliberately silent, no
    SEROS_COMMON fallback (confirmed: unresolved branding should come back
    blank rather than substituting a generic image)."""
    result = {
        "company_id": None,
        "company_name": None,
        "company_short_name": None,
        **{key: None for key in IMAGE_FILES},
    }

    company_id = _resolve_company_id(rig_id, effective_date)
    if not company_id:
        return result

    company_name, short_name = _resolve_company_name(company_id, effective_date)
    result["company_id"] = company_id
    result["company_name"] = company_name
    result["company_short_name"] = short_name
    if not short_name:
        return result

    folder_abs = os.path.join(settings.MEDIA_ROOT, LETTERHEAD_DIR, short_name)
    for key, filename in IMAGE_FILES.items():
        if os.path.isfile(os.path.join(folder_abs, filename)):
            result[key] = f"{LETTERHEAD_DIR}/{short_name}/{filename}"

    return result
