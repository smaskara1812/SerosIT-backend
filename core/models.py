from django.db import models

from .fields import PortableJSONField


class MstDepartment(models.Model):
    """Straight copy of the legacy Mst_Department table structure."""

    dept_id = models.AutoField(primary_key=True)
    dept_name = models.CharField(max_length=50)
    dept_dispname = models.CharField(max_length=25)
    dept_abrv = models.CharField(max_length=8)
    dept_order = models.IntegerField(default=0)
    dept_active = models.CharField(max_length=1, default="Y")
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mst_department"
        ordering = ["dept_order"]

    def __str__(self):
        return self.dept_dispname


# ── General masters ──────────────────────────────────────────────────────
# Legacy's "General" master group (masters_registry.py) — straight copies of
# the eos_Mst_* structure, eos_ prefix dropped (same call as cb_ → sys_).
# Cross-group references (Location_Id, Country_Id, Fs_Emp_Id, Rig_Subtype_Id,
# Rig_Type_Id) stay plain nullable ints until those masters exist, same
# pattern as dept_id before Mst_Department was built.


class MstCostCentreType(models.Model):
    cost_centre_type_id = models.AutoField(primary_key=True)
    cost_centre_type_name = models.CharField(max_length=15)
    cost_centre_type_shortname = models.CharField(max_length=10)
    cost_centre_type_active = models.CharField(max_length=1, default="Y")
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mst_cost_centre_type"

    def __str__(self):
        return self.cost_centre_type_name


class MstContractor(models.Model):
    contractor_id = models.AutoField(primary_key=True)
    contractor_name = models.CharField(max_length=40)
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mst_contractor"

    def __str__(self):
        return self.contractor_name


class MstCertInstitute(models.Model):
    cert_institute_id = models.AutoField(primary_key=True)
    cert_institute_name = models.CharField(max_length=100)
    cert_institute_shortname = models.CharField(max_length=10)
    cert_institute_address = models.CharField(max_length=100, null=True, blank=True)
    location = models.ForeignKey(
        "MstLocation",
        db_column="location_id",
        on_delete=models.PROTECT,
        related_name="cert_institutes",
    )
    tel_no = models.CharField(max_length=15, null=True, blank=True)
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mst_cert_institute"

    def __str__(self):
        return self.cert_institute_name


class MstEmailNotificationType(models.Model):
    en_type_id = models.AutoField(primary_key=True)
    en_type_name = models.CharField(max_length=50)
    en_type_subject = models.CharField(max_length=100)
    en_description = models.TextField()
    en_type_active = models.CharField(max_length=1, default="Y")
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mst_email_notification_type"

    def __str__(self):
        return self.en_type_name


class MstOperator(models.Model):
    operator_id = models.AutoField(primary_key=True)
    operator_name = models.CharField(max_length=60)
    operator_short_name = models.CharField(max_length=15)
    operator_sap_code = models.CharField(max_length=8, null=True, blank=True)
    wbs_client_code = models.CharField(max_length=4, null=True, blank=True)
    location = models.ForeignKey(
        "MstLocation",
        db_column="location_id",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="operators",
    )
    country = models.ForeignKey(
        "MstCountry",
        db_column="country_id",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="operators",
    )
    contact_person = models.CharField(max_length=75, null=True, blank=True)
    tel_no = models.CharField(max_length=12, null=True, blank=True)
    email_id = models.EmailField(max_length=40, null=True, blank=True)
    operator_active = models.CharField(max_length=1, default="Y")
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mst_operator"

    def __str__(self):
        return self.operator_name


class MstRigType(models.Model):
    rig_type_id = models.AutoField(primary_key=True)
    rig_type_name = models.CharField(max_length=15)
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mst_rig_type"

    def __str__(self):
        return self.rig_type_name


class MstRigSubtype(models.Model):
    rig_subtype_id = models.AutoField(primary_key=True)
    rig_subtype_name = models.CharField(max_length=20)
    rig_type = models.ForeignKey(
        MstRigType, db_column="rig_type_id", on_delete=models.PROTECT, related_name="subtypes"
    )
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mst_rig_subtype"

    def __str__(self):
        return self.rig_subtype_name


class MstRig(models.Model):
    rig_id = models.AutoField(primary_key=True)
    rig_name = models.CharField(max_length=40)
    rig_short_name = models.CharField(max_length=8)
    old_rig_name = models.CharField(max_length=40, null=True, blank=True)
    rig_subtype = models.ForeignKey(
        MstRigSubtype, db_column="rig_subtype_id", on_delete=models.PROTECT, related_name="rigs"
    )
    rig_type = models.ForeignKey(
        MstRigType, db_column="rig_type_id", on_delete=models.PROTECT, related_name="rigs"
    )
    rig_built_dt = models.DateField()
    rig_tel_no = models.CharField(max_length=25, null=True, blank=True)
    rig_fax_no = models.CharField(max_length=15, null=True, blank=True)
    rig_email_id = models.EmailField(max_length=50, null=True, blank=True)
    personnel_area = models.CharField(max_length=10, null=True, blank=True)
    org_unit_code = models.CharField(max_length=10, null=True, blank=True)
    rig_from = models.DateField()
    rig_to = models.DateField(null=True, blank=True)
    rig_active = models.CharField(max_length=1, default="Y")
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mst_rig"

    def __str__(self):
        return self.rig_name


class MstCostCentre(models.Model):
    cost_centre_id = models.AutoField(primary_key=True)
    cost_centre_type = models.ForeignKey(
        MstCostCentreType,
        db_column="cost_centre_type_id",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="cost_centres",
    )
    cost_centre_name = models.CharField(max_length=50)
    old_cost_centre_name = models.CharField(max_length=50, null=True, blank=True)
    rig = models.ForeignKey(
        MstRig,
        db_column="rig_id",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="cost_centres",
    )
    fs_emp = models.ForeignKey(
        "MstEmployee",
        db_column="fs_emp_id",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="cost_centres",
    )
    location = models.ForeignKey(
        "MstLocation",
        db_column="location_id",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="cost_centres",
    )
    cost_centre_active = models.CharField(max_length=1, default="Y")
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mst_cost_centre"

    def __str__(self):
        return self.cost_centre_name


# ── HR masters ───────────────────────────────────────────────────────────
# Legacy's "HR" master group. Travel Eligibility / Reporting Structure are
# still deferred — they're FK-combination rows with no name field of their
# own, and now that Fs_Category/Rank exist, building them for real is a
# reasonable next step. Job Descriptions (header+detail) needs its own UI,
# not this file's generic single-table shape — deferred separately.


class MstCompetency(models.Model):
    competency_id = models.AutoField(primary_key=True)
    competency_name = models.CharField(max_length=50)
    department = models.ForeignKey(
        MstDepartment,
        db_column="dept_id",
        on_delete=models.PROTECT,
        related_name="competencies",
    )
    active = models.CharField(max_length=1, default="Y")
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mst_competency"

    def __str__(self):
        return self.competency_name


class MstFsCategory(models.Model):
    """Employee category (Officer/Petty Officer/Crew/etc). The
    Business_System_Id_* flags are legacy cross-system integration toggles —
    kept in the schema for a faithful copy, not surfaced in the edit form."""

    fs_category_id = models.AutoField(primary_key=True)
    fs_category_name = models.CharField(max_length=25)
    business_system_id_2 = models.CharField(max_length=1, null=True, blank=True)
    business_system_id_5 = models.CharField(max_length=1, null=True, blank=True)
    business_system_id_6 = models.CharField(max_length=1, null=True, blank=True)
    business_system_id_11 = models.CharField(max_length=1, null=True, blank=True)
    business_system_id_16 = models.CharField(max_length=1, null=True, blank=True)
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mst_fs_category"

    def __str__(self):
        return self.fs_category_name


class MstVesselDept(models.Model):
    vessel_dept_id = models.AutoField(primary_key=True)
    vessel_dept_name = models.CharField(max_length=25)
    vessel_dept_order = models.IntegerField(default=0)
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mst_vessel_dept"

    def __str__(self):
        return self.vessel_dept_name


class MstRank(models.Model):
    rank_id = models.AutoField(primary_key=True)
    fs_category = models.ForeignKey(
        MstFsCategory,
        db_column="fs_category_id",
        on_delete=models.PROTECT,
        related_name="ranks",
    )
    vessel_dept = models.ForeignKey(
        MstVesselDept,
        db_column="vessel_dept_id",
        on_delete=models.PROTECT,
        related_name="ranks",
    )
    rank_name = models.CharField(max_length=35)
    rank_abrv = models.CharField(max_length=7)
    rank_order = models.IntegerField(default=0)
    business_system_id_2 = models.CharField(max_length=1, null=True, blank=True)
    business_system_id_5 = models.CharField(max_length=1, null=True, blank=True)
    business_system_id_6 = models.CharField(max_length=1, null=True, blank=True)
    business_system_id_11 = models.CharField(max_length=1, null=True, blank=True)
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mst_rank"
        ordering = ["rank_order"]

    def __str__(self):
        return self.rank_name


class JobDescriptionHdr(models.Model):
    """
    A named section (e.g. "Position Summary", "Essential Job Functions")
    within a Rank's job description. Each section holds one or more detail
    lines (JobDescriptionDtl) — this is a real header+detail structure, not
    a flat lookup, so it gets its own editor UI rather than the generic
    single-table masters page.
    """

    jd_hdr_id = models.AutoField(primary_key=True)
    fs_category = models.ForeignKey(
        MstFsCategory, db_column="fs_category_id", on_delete=models.PROTECT
    )
    rank = models.ForeignKey(
        MstRank, db_column="rank_id", on_delete=models.PROTECT, related_name="jd_headers"
    )
    jd_hdr_description = models.CharField(max_length=75)
    jd_hdr_order = models.IntegerField(default=0)
    jd_hdr_active = models.CharField(max_length=1, default="Y")
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "job_description_hdr"
        ordering = ["jd_hdr_order"]

    def __str__(self):
        return self.jd_hdr_description


class JobDescriptionDtl(models.Model):
    jd_dtl_id = models.AutoField(primary_key=True)
    header = models.ForeignKey(
        JobDescriptionHdr, db_column="jd_hdr_id", on_delete=models.CASCADE, related_name="details"
    )
    jd_dtl_description = models.CharField(max_length=500)
    jd_dtl_order = models.IntegerField(default=0)
    jd_dtl_active = models.CharField(max_length=1, default="Y")
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "job_description_dtl"
        ordering = ["jd_dtl_order"]

    def __str__(self):
        return self.jd_dtl_description[:50]


TRAVEL_MODE_CHOICES = [("A", "Air"), ("R", "Rail"), ("C", "Coach")]


class TravelEligibility(models.Model):
    """
    An FK-combination row (Category + Rank + travel mode → entitled class),
    no name field of its own — legacy's own audit code notes this. The
    serializer synthesizes a display label from rank + mode for the UI.
    """

    travel_eligibility_id = models.AutoField(primary_key=True)
    fs_category = models.ForeignKey(
        MstFsCategory, db_column="fs_category_id", on_delete=models.PROTECT
    )
    rank = models.ForeignKey(MstRank, db_column="rank_id", on_delete=models.PROTECT)
    travel_mode = models.CharField(max_length=1, choices=TRAVEL_MODE_CHOICES)
    travel_class = models.CharField(max_length=225)
    travel_preference = models.IntegerField(default=1)
    eligible_from = models.DateField()
    eligible_to = models.DateField(null=True, blank=True)
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "travel_eligibility"

    def __str__(self):
        return f"{self.rank.rank_name} — {self.get_travel_mode_display()}"


class ReportingStructure(models.Model):
    """Who reports to whom, by rank (Category + Rank → Reporting Rank). No
    name field of its own — same FK-combo shape as TravelEligibility."""

    reporting_structure_id = models.AutoField(primary_key=True)
    fs_category = models.ForeignKey(
        MstFsCategory, db_column="fs_category_id", on_delete=models.PROTECT
    )
    rank = models.ForeignKey(
        MstRank, db_column="rank_id", on_delete=models.PROTECT, related_name="+"
    )
    reporting_rank = models.ForeignKey(
        MstRank,
        db_column="reporting_rank_id",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "reporting_structure"

    def __str__(self):
        if self.reporting_rank_id:
            return f"{self.rank.rank_name} → {self.reporting_rank.rank_name}"
        return f"{self.rank.rank_name} (top of chain)"


class MstRigOperation(models.Model):
    rig_operation_id = models.AutoField(primary_key=True)
    rig_operation_name = models.CharField(max_length=65)
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mst_rig_operation"

    def __str__(self):
        return self.rig_operation_name


class MstContactExposureType(models.Model):
    contact_expo_type_id = models.AutoField(primary_key=True)
    contact_expo_type_name = models.CharField(max_length=65)
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mst_contact_exposure_type"

    def __str__(self):
        return self.contact_expo_type_name


INDICATOR_REPORT_TYPE_CHOICES = [("Leading", "Leading"), ("Lagging", "Lagging")]


class MstIndicatorType(models.Model):
    """indicator_type_order is a per-Report_Type sequence, auto-assigned on
    create (append-to-end) — never user-editable, matching legacy."""

    indicator_type_id = models.AutoField(primary_key=True)
    indicator_type_name = models.CharField(max_length=65)
    indicator_type_order = models.IntegerField(default=0)
    report_type = models.CharField(max_length=7, choices=INDICATOR_REPORT_TYPE_CHOICES)
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mst_indicator_type"
        ordering = ["report_type", "indicator_type_order"]

    def __str__(self):
        return self.indicator_type_name


class MstIndicatorSubtype(models.Model):
    """indicator_subtype_order is a per-Indicator_Type sequence, same
    auto-assign-on-create pattern as indicator_type_order."""

    indicator_subtype_id = models.AutoField(primary_key=True)
    indicator_type = models.ForeignKey(
        MstIndicatorType, db_column="indicator_type_id", on_delete=models.PROTECT, related_name="subtypes"
    )
    indicator_subtype_name = models.CharField(max_length=65)
    indicator_subtype_order = models.IntegerField(default=0)
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mst_indicator_subtype"
        ordering = ["indicator_type__indicator_type_name", "indicator_subtype_order"]

    def __str__(self):
        return self.indicator_subtype_name


class MstPartsOfBody(models.Model):
    part_of_body_id = models.AutoField(primary_key=True)
    part_of_body_name = models.CharField(max_length=60)
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mst_parts_of_body"

    def __str__(self):
        return self.part_of_body_name


class MstQhseCategory(models.Model):
    qhse_category_id = models.AutoField(primary_key=True)
    qhse_category_name = models.CharField(max_length=100)
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mst_qhse_category"

    def __str__(self):
        return self.qhse_category_name


HSE_ACTIVITY_TYPE_CHOICES = [
    ("IN", "Inspection"),
    ("DR", "Drill"),
    ("AU", "Audit"),
    ("OT", "Other"),
]


class MstHseActivity(models.Model):
    hse_activity_id = models.AutoField(primary_key=True)
    hse_activity_name = models.CharField(max_length=50)
    hse_activity_type = models.CharField(max_length=2, choices=HSE_ACTIVITY_TYPE_CHOICES)
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mst_hse_activity"

    def __str__(self):
        return self.hse_activity_name


class MstHseConsumable(models.Model):
    hse_consumable_id = models.AutoField(primary_key=True)
    hse_consumable_name = models.CharField(max_length=100)
    hse_consumption_unit = models.CharField(max_length=15)
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mst_hse_consumable"

    def __str__(self):
        return self.hse_consumable_name


HAZ_TYPE_CLASS_CHOICES = [("Positive", "Positive"), ("Negative", "Negative")]


class MstHazardType(models.Model):
    """haz_type_active is always 'Y' in legacy — hardcoded on create there,
    never exposed for editing — so it's kept but not surfaced in the form."""

    haz_type_id = models.AutoField(primary_key=True)
    haz_type_name = models.CharField(max_length=25)
    haz_type_class = models.CharField(max_length=8, choices=HAZ_TYPE_CLASS_CHOICES)
    haz_type_active = models.CharField(max_length=1, default="Y")
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mst_hazard_type"

    def __str__(self):
        return self.haz_type_name


class MstUser(models.Model):
    """
    Straight copy of the legacy Mst_User table structure (smallint columns
    widened to IntegerField — no other landmines known yet).

    user_id keeps a real AutoField as its PK (not a hand-rolled MAX(id)+1)
    so it behaves correctly going forward; the legacy backfill script writes
    the old USER_ID values into it explicitly and reseeds the auto-increment
    counter afterwards, preserving those IDs without losing real auto-increment.
    """

    user_id = models.AutoField(primary_key=True)
    user_name = models.CharField(max_length=60)
    emp = models.ForeignKey(
        "MstEmployee",
        db_column="emp_id",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="users",
    )
    # Mst_NonEmployee lives in legacy's separate hr_ module (visa,
    # deficiency-tracking, etc.) that hasn't been brought over — left as a
    # plain id rather than pulling that whole subsystem in for one FK.
    nonemp_id = models.IntegerField(null=True, blank=True)
    # A real FK now that Mst_Department exists — legacy only had a bare
    # smallint column, but we have "complete control" over the schema here.
    department = models.ForeignKey(
        MstDepartment,
        db_column="dept_id",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="users",
    )
    # NOT unique — the real legacy data has ~17 login_ids duplicated across
    # an active + inactive row each (rehires, name changes), so the app layer
    # (SerosAuthBackend) has to pick the right row, not the DB constraint.
    user_login_id = models.CharField(max_length=20, db_index=True)
    user_active = models.CharField(max_length=1, default="Y")
    user_type_id = models.CharField(max_length=1)
    mac_address = models.CharField(max_length=17, null=True, blank=True)
    user_from = models.DateField()
    user_to = models.DateField(null=True, blank=True)
    user_email = models.EmailField(max_length=40, null=True, blank=True)
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mst_user"

    def __str__(self):
        return self.user_login_id


class MstUserPassword(models.Model):
    """Local SHA-256 password, same shape as the legacy cb_mst_user_password
    table. A missing row means the user authenticates via AD instead."""

    user = models.OneToOneField(
        MstUser,
        on_delete=models.CASCADE,
        primary_key=True,
        db_column="user_id",
        related_name="password_row",
    )
    password_hash = models.CharField(max_length=64)
    set_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "mst_user_password"

    def __str__(self):
        return f"LocalPwd(user_id={self.user_id})"


class UserProfile(models.Model):
    """Admin/permission profile for an Mst_User — same shape as the legacy
    cb_user_profile table, renamed off the cb_ (chatbot) prefix since this
    is a system table, not chatbot-specific."""

    user_id = models.IntegerField(primary_key=True)  # Mst_User.user_id
    user_login_id = models.CharField(max_length=20, db_index=True)
    is_app_admin = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "sys_user_profile"

    def __str__(self):
        return self.user_login_id


class UserPermission(models.Model):
    """Same shape as legacy cb_user_permissions, renamed to sys_."""

    user_id = models.IntegerField(db_index=True)
    menu_key = models.CharField(max_length=60)
    can_view = models.BooleanField(default=False)
    can_add = models.BooleanField(default=False)
    can_edit = models.BooleanField(default=False)
    can_delete = models.BooleanField(default=False)
    can_export = models.BooleanField(default=False)
    granted_by = models.CharField(max_length=20, blank=True)
    granted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "sys_user_permissions"
        unique_together = [("user_id", "menu_key")]

    def __str__(self):
        return f"{self.user_id}:{self.menu_key}"


class SysMenu(models.Model):
    """Same shape as legacy cb_menu — drives both the sidebar nav and the
    User Rights permission grid. Renamed off cb_ to sys_."""

    menu_key = models.CharField(max_length=60, unique=True)
    menu_label = models.CharField(max_length=60)
    menu_group = models.CharField(max_length=40, blank=True)
    group_order = models.SmallIntegerField(default=0)
    menu_order = models.SmallIntegerField(default=0)
    view_available = models.BooleanField(default=True)
    add_available = models.BooleanField(default=False)
    edit_available = models.BooleanField(default=False)
    delete_available = models.BooleanField(default=False)
    export_available = models.BooleanField(default=False)
    upload_available = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    cr_dt = models.DateTimeField(auto_now_add=True)
    mod_dt = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "sys_menu"
        ordering = ["group_order", "menu_order"]

    def __str__(self):
        return f"{self.menu_key} ({self.menu_label})"

    def get_actions(self):
        actions = []
        if self.view_available:
            actions.append("view")
        if self.add_available:
            actions.append("add")
        if self.edit_available:
            actions.append("edit")
        if self.delete_available:
            actions.append("delete")
        if self.export_available:
            actions.append("export")
        if self.upload_available:
            actions.append("upload")
        return actions


class SysAuditLog(models.Model):
    """Append-only audit trail — same shape as legacy cb_audit_log, renamed
    to sys_. Never edited/deleted from the app."""

    ts = models.DateTimeField(auto_now_add=True, db_index=True)
    user_id = models.IntegerField(null=True, blank=True, db_index=True)
    username = models.CharField(max_length=50)
    action = models.CharField(max_length=24, db_index=True)
    entity = models.CharField(max_length=60, db_index=True)
    entity_label = models.CharField(max_length=80, blank=True)
    record_id = models.CharField(max_length=40, blank=True)
    record_label = models.CharField(max_length=200, blank=True)
    changes = PortableJSONField(null=True, blank=True)
    ip = models.CharField(max_length=45, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)

    class Meta:
        db_table = "sys_audit_log"
        ordering = ["-ts"]
        indexes = [
            models.Index(fields=["entity", "ts"]),
            models.Index(fields=["user_id", "ts"]),
            models.Index(fields=["action", "ts"]),
        ]

    def __str__(self):
        return f"{self.ts} {self.username} {self.action} {self.entity}"


class MstEmployee(models.Model):
    """Read-only lookup, not a delegable master — 27k+ rows is a real HR
    employee roster the app doesn't own or edit, just enough columns to
    resolve a name for Document To Sign Mapping's Employee field. emp_id
    keeps its legacy value as a plain (non-auto) PK since we never insert
    into this table ourselves."""

    emp_id = models.IntegerField(primary_key=True)
    emp_fname = models.CharField(max_length=26, null=True, blank=True)
    emp_mname = models.CharField(max_length=20, null=True, blank=True)
    emp_sname = models.CharField(max_length=35)
    emp_active = models.CharField(max_length=1, default="Y")

    class Meta:
        db_table = "mst_employee"

    def __str__(self):
        return " ".join(p for p in [self.emp_fname, self.emp_mname, self.emp_sname] if p)


class MstUserRigMapping(models.Model):
    user_rig_mapping_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(MstUser, db_column="user_id", on_delete=models.PROTECT, related_name="rig_mappings")
    rig = models.ForeignKey(MstRig, db_column="rig_id", on_delete=models.PROTECT)
    mapping_from = models.DateField()
    mapping_to = models.DateField(null=True, blank=True)
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "user_rig_mapping"

    def __str__(self):
        return f"{self.user.user_login_id} — {self.rig.rig_name}"


class MstUserFsCatgMapping(models.Model):
    user_fs_catg_mapping_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        MstUser, db_column="user_id", on_delete=models.PROTECT, related_name="fs_catg_mappings"
    )
    fs_category = models.ForeignKey(MstFsCategory, db_column="fs_category_id", on_delete=models.PROTECT)
    mapping_from = models.DateField()
    mapping_to = models.DateField(null=True, blank=True)
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "user_fs_catg_mapping"

    def __str__(self):
        return f"{self.user.user_login_id} — {self.fs_category.fs_category_name}"


class DocToSignMapping(models.Model):
    doc_to_sign_id = models.AutoField(primary_key=True)
    doc_name = models.CharField(max_length=50)
    employee = models.ForeignKey(MstEmployee, db_column="emp_id", on_delete=models.PROTECT)
    # Legacy stores this as a plain typed-in path (e.g. "/Images/Signatures/84.jpg"),
    # not an actual upload here — see DocToSignMapping's form.
    sign_path = models.CharField(max_length=100, null=True, blank=True)
    sign_from = models.DateField()
    sign_to = models.DateField(null=True, blank=True)
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "doc_to_sign_mapping"

    def __str__(self):
        return f"{self.doc_name} — {self.employee}"


class MstInterviewer(models.Model):
    """Department-to-interviewer assignment with an actual uploaded
    signature image/PDF, stored under MEDIA_ROOT/interviewer_signatures/."""

    interviewer_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(MstUser, db_column="user_id", on_delete=models.PROTECT, related_name="+")
    department = models.ForeignKey(MstDepartment, db_column="dept_id", on_delete=models.PROTECT)
    sign_path = models.CharField(max_length=100, null=True, blank=True)
    active = models.CharField(max_length=1, default="Y")
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mst_interviewer"

    def __str__(self):
        return f"{self.department.dept_dispname} — {self.user.user_login_id}"


class FsCatgToRigTypeMapping(models.Model):
    """Which Rig Types a Fs Category applies to — straight copy of legacy
    eos_Fs_Catg_To_Rig_Type_Mapping. First of the HR Mapping Masters group;
    not built out as its own page in legacy either."""

    fs_catg_to_rig_type_mapping_id = models.AutoField(primary_key=True)
    fs_category = models.ForeignKey(
        MstFsCategory, db_column="fs_category_id", on_delete=models.PROTECT, related_name="rig_type_mappings"
    )
    rig_type = models.ForeignKey(
        MstRigType, db_column="rig_type_id", on_delete=models.PROTECT, related_name="fs_category_mappings"
    )
    # Legacy has this blank (not even 'N') for an unchecked pairing rather
    # than a real tri-state — treated as 'N' everywhere it's read.
    mapping_active = models.CharField(max_length=1, default="N")
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "fs_catg_to_rig_type_mapping"

    def __str__(self):
        return f"{self.fs_category.fs_category_name} — {self.rig_type.rig_type_name}"


class RankClassification(models.Model):
    """Straight copy of legacy eos_Rank_Classification, deduplicated on
    import — legacy has no unique constraint on Rank_Id and one rank had 34
    duplicate re-saves over the years (alternating Junior/Senior); only the
    most recently created row per rank was kept. rank_class_abrv isn't
    stored separately since it's 100% derived from rank_class ('J' -> 'Jr.',
    'S' -> 'Sr.') with no exceptions in the data."""

    RANK_CLASS_CHOICES = [("J", "Junior"), ("S", "Senior")]
    RANK_CLASS_ABRV = {"J": "Jr.", "S": "Sr."}

    rank_classification_id = models.AutoField(primary_key=True)
    rank = models.OneToOneField(
        MstRank, db_column="rank_id", on_delete=models.PROTECT, related_name="classification"
    )
    rank_class = models.CharField(max_length=1, choices=RANK_CLASS_CHOICES)
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "rank_classification"

    def __str__(self):
        return f"{self.rank.rank_name} — {self.get_rank_class_display()}"


class MstEmpNature(models.Model):
    emp_nature_id = models.AutoField(primary_key=True)
    emp_nature_name = models.CharField(max_length=50)
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mst_emp_nature"

    def __str__(self):
        return self.emp_nature_name


class MstEmpType(models.Model):
    emp_type_id = models.AutoField(primary_key=True)
    emp_nature = models.ForeignKey(
        MstEmpNature, db_column="emp_nature_id", on_delete=models.PROTECT, related_name="emp_types"
    )
    emp_type_name = models.CharField(max_length=45)
    # Forward reference — MstCurrency is defined further down the file.
    currency = models.ForeignKey(
        "MstCurrency",
        db_column="currency_id",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="emp_types",
    )
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mst_emp_type"

    def __str__(self):
        return self.emp_type_name


class NationalityToEmpTypeMapping(models.Model):
    """Straight copy of legacy eos_Nationality_To_Emp_Type_Mapping."""

    NATIONALITY_CHOICES = [("National", "National"), ("Expat", "Expat")]

    nat_to_emp_type_map_id = models.AutoField(primary_key=True)
    fs_category = models.ForeignKey(
        MstFsCategory, db_column="fs_category_id", on_delete=models.PROTECT, related_name="nat_emp_type_mappings"
    )
    nationality = models.CharField(max_length=8, choices=NATIONALITY_CHOICES)
    emp_type = models.ForeignKey(
        MstEmpType, db_column="emp_type_id", on_delete=models.PROTECT, related_name="nationality_mappings"
    )
    active = models.CharField(max_length=1, default="Y")
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "nationality_to_emp_type_mapping"

    def __str__(self):
        return f"{self.fs_category.fs_category_name} — {self.nationality} — {self.emp_type.emp_type_name}"


class CrewChangeRelieverMapping(models.Model):
    """Straight copy of legacy eos_Crew_Change_Reliever_Mapping — which
    Rank relieves which other Rank on crew change, per Fs Category."""

    cc_reliever_mapping_id = models.AutoField(primary_key=True)
    fs_category = models.ForeignKey(
        MstFsCategory, db_column="fs_category_id", on_delete=models.PROTECT, related_name="reliever_mappings"
    )
    rank = models.ForeignKey(
        MstRank, db_column="rank_id", on_delete=models.PROTECT, related_name="reliever_mappings_as_rank"
    )
    reliever_rank = models.ForeignKey(
        MstRank, db_column="reliever_rank_id", on_delete=models.PROTECT, related_name="reliever_mappings_as_reliever"
    )
    active = models.CharField(max_length=1, default="Y")
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "crew_change_reliever_mapping"

    def __str__(self):
        return f"{self.rank.rank_name} — {self.reliever_rank.rank_name}"


# ── Project masters ──────────────────────────────────────────────────────────
# Location/Currency/Drilling Rate (type) are plain lookups with no CRUD page
# of their own in legacy either — they only ever populate a dropdown on the
# two real project masters below.


class MstContinent(models.Model):
    continent_id = models.AutoField(primary_key=True)
    continent_name = models.CharField(max_length=15)
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mst_continent"

    def __str__(self):
        return self.continent_name


class MstCountry(models.Model):
    country_id = models.AutoField(primary_key=True)
    country_name = models.CharField(max_length=40)
    country_known_name = models.CharField(max_length=25)
    country_iso_cd = models.CharField(max_length=2)
    continent = models.ForeignKey(
        MstContinent,
        db_column="continent_id",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="countries",
    )
    country_active = models.CharField(max_length=1, default="Y")
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mst_country"

    def __str__(self):
        return self.country_name


class MstCountryState(models.Model):
    country_state_id = models.AutoField(primary_key=True)
    country = models.ForeignKey(
        MstCountry,
        db_column="country_id",
        on_delete=models.PROTECT,
        related_name="states",
    )
    country_state_name = models.CharField(max_length=25)
    country_state_abrv = models.CharField(max_length=2)
    country_state_active = models.CharField(max_length=1, default="Y")
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mst_country_state"

    def __str__(self):
        return self.country_state_name


class MstLocation(models.Model):
    location_id = models.AutoField(primary_key=True)
    location_name = models.CharField(max_length=50)
    country = models.ForeignKey(
        MstCountry,
        db_column="country_id",
        on_delete=models.PROTECT,
        related_name="locations",
    )
    country_state = models.ForeignKey(
        MstCountryState,
        db_column="country_state_id",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="locations",
    )
    location_active = models.CharField(max_length=1, default="Y")
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mst_location"

    def __str__(self):
        return self.location_name


class MstCurrency(models.Model):
    currency_id = models.AutoField(primary_key=True)
    currency_name = models.CharField(max_length=30)
    currency_abrv = models.CharField(max_length=3)
    decimal_name = models.CharField(max_length=15)
    currency_text = models.CharField(max_length=25)
    currency_active = models.CharField(max_length=1, default="Y")
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mst_currency"

    def __str__(self):
        return self.currency_name


class MstDrillingRate(models.Model):
    """A drilling rate *type* (e.g. "R1", "FM", "MOB") — not a rate value
    itself, that's ProjectDrillingRate."""

    drilling_rate_id = models.AutoField(primary_key=True)
    rate_code = models.CharField(max_length=20)
    rate_description = models.CharField(max_length=50, null=True, blank=True)
    rate_active = models.CharField(max_length=1, default="Y")
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mst_drilling_rate"

    def __str__(self):
        return self.rate_code


class ProjectContract(models.Model):
    """A contract with an operator at a location. Real header+detail
    structure (rig assignments below are its detail lines) — gets its own
    editor UI rather than the generic single-table masters page."""

    prj_contract_id = models.AutoField(primary_key=True)
    location = models.ForeignKey(MstLocation, db_column="location_id", on_delete=models.PROTECT)
    operator = models.ForeignKey(MstOperator, db_column="operator_id", on_delete=models.PROTECT)
    prj_contract_no = models.CharField(max_length=110)
    prj_short_name = models.CharField(max_length=10, null=True, blank=True)
    prj_start_dt = models.DateField()
    prj_end_dt = models.DateField(null=True, blank=True)
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "project_contract"

    def __str__(self):
        return self.prj_contract_no


class ProjectContractDtl(models.Model):
    """A rig assigned to a contract for a date range."""

    prj_contract_dtl_id = models.AutoField(primary_key=True)
    contract = models.ForeignKey(
        ProjectContract, db_column="prj_contract_id", on_delete=models.CASCADE, related_name="lines"
    )
    rig = models.ForeignKey(MstRig, db_column="rig_id", on_delete=models.PROTECT)
    rig_active_from = models.DateField()
    rig_active_to = models.DateField(null=True, blank=True)
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "project_contract_dtl"
        ordering = ["rig_active_from"]

    def __str__(self):
        return f"{self.contract.prj_contract_no} — {self.rig.rig_name}"


class ProjectDrillingRate(models.Model):
    """One rate (by type) for one rig on one contract — a flat lookup
    unlike Project Contract, so it gets the generic masters page."""

    prj_drilling_rate_id = models.AutoField(primary_key=True)
    drilling_rate = models.ForeignKey(
        MstDrillingRate,
        db_column="drilling_rate_id",
        on_delete=models.PROTECT,
        related_name="rate_usages",
    )
    contract = models.ForeignKey(
        ProjectContract, db_column="prj_contract_id", on_delete=models.CASCADE, related_name="drilling_rates"
    )
    rig = models.ForeignKey(MstRig, db_column="rig_id", on_delete=models.PROTECT)
    currency = models.ForeignKey(
        MstCurrency, db_column="currency_id", on_delete=models.PROTECT, null=True, blank=True
    )
    rate = models.DecimalField(max_digits=11, decimal_places=2, null=True, blank=True)
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "project_drilling_rate"

    def __str__(self):
        return f"{self.contract.prj_contract_no} — {self.rig.rig_name} — {self.drilling_rate.rate_code}"


# ── Drilling masters ──────────────────────────────────────────────────────────


class MstDrillingOperation(models.Model):
    drilling_ops_id = models.AutoField(primary_key=True)
    drilling_ops_code_no = models.IntegerField()
    drilling_ops_name = models.CharField(max_length=50)
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mst_drilling_operation"

    def __str__(self):
        return self.drilling_ops_name


class MstDrillingSection(models.Model):
    drilling_section_id = models.AutoField(primary_key=True)
    drilling_section_name = models.CharField(max_length=10)
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mst_drilling_section"

    def __str__(self):
        return self.drilling_section_name


class MstDrillingWorkShift(models.Model):
    """Morning/Evening work shift timing for one rig, optionally scoped to
    a specific contract — same (contract, rig) scoping workflow as
    ProjectDrillingRate, just for shift timings instead of rates."""

    WORK_SHIFT_CHOICES = [("M", "Morning"), ("E", "Evening")]

    drilling_work_shift_id = models.AutoField(primary_key=True)
    contract = models.ForeignKey(
        ProjectContract,
        db_column="prj_contract_id",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="work_shifts",
    )
    rig = models.ForeignKey(MstRig, db_column="rig_id", on_delete=models.PROTECT)
    work_shift = models.CharField(max_length=1, choices=WORK_SHIFT_CHOICES)
    work_shift_start_time = models.TimeField()
    work_shift_end_time = models.TimeField()
    work_shift_days = models.IntegerField()
    work_shift_active = models.CharField(max_length=1, default="Y")
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mst_drilling_work_shift"

    def __str__(self):
        return f"{self.rig.rig_name} — {self.get_work_shift_display()}"


# ── Incidents ─────────────────────────────────────────────────────────────


class MstWorkLocation(models.Model):
    work_location_id = models.AutoField(primary_key=True)
    work_location = models.CharField(max_length=45)
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mst_work_location"

    def __str__(self):
        return self.work_location


class MstIncidentType(models.Model):
    incident_type_id = models.AutoField(primary_key=True)
    incident_type = models.CharField(max_length=50)
    incident_abrv = models.CharField(max_length=5)
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mst_incident_type"

    def __str__(self):
        return self.incident_type


class MstIncidentCause(models.Model):
    incident_cause_id = models.AutoField(primary_key=True)
    incident_cause_desc = models.CharField(max_length=65)
    # 'I' = Immediate, 'R' = Root, 'B' = Both — legacy's Incident_Cause_Category
    # flag; the same lookup backs both Incident.immediate_incident_cause and
    # IncidentRootCause.root_cause depending on this flag.
    incident_cause_category = models.CharField(max_length=1)
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mst_incident_cause"

    def __str__(self):
        return self.incident_cause_desc


class MstIncidentSubcause(models.Model):
    incident_subcause_id = models.AutoField(primary_key=True)
    incident_subcause = models.CharField(max_length=75)
    incident_cause = models.ForeignKey(
        MstIncidentCause,
        db_column="incident_cause_id",
        on_delete=models.PROTECT,
        related_name="subcauses",
    )
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mst_incident_subcause"

    def __str__(self):
        return self.incident_subcause


class MstFinancialYear(models.Model):
    financial_year_id = models.AutoField(primary_key=True)
    fin_year_from = models.DateField()
    fin_year_to = models.DateField()
    fin_year_text = models.CharField(max_length=9)
    fin_year_subtext = models.CharField(max_length=5)
    assessment_year = models.CharField(max_length=9)
    nri_days = models.IntegerField()
    fin_year_status = models.CharField(max_length=1)
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mst_financial_year"

    def __str__(self):
        return self.fin_year_text


class Incident(models.Model):
    """Straight copy of legacy eos_Incident_Details — the first of the
    operational (non-master) data-entry tables being migrated, starting
    with just the table structure/FKs; no CRUD page yet."""

    incident_id = models.AutoField(primary_key=True)
    work_location = models.ForeignKey(
        MstWorkLocation,
        db_column="work_location_id",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="incidents",
    )
    rig = models.ForeignKey(
        MstRig, db_column="rig_id", null=True, blank=True, on_delete=models.PROTECT, related_name="incidents"
    )
    unit_name = models.CharField(max_length=35, null=True, blank=True)
    rig_incident_no = models.CharField(max_length=20, null=True, blank=True)
    incident_no = models.IntegerField()
    incident_date = models.DateTimeField()
    financial_year = models.ForeignKey(
        MstFinancialYear, db_column="financial_year_id", on_delete=models.PROTECT, related_name="incidents"
    )
    country = models.ForeignKey(
        MstCountry, db_column="country_id", null=True, blank=True, on_delete=models.PROTECT, related_name="incidents"
    )
    well_no = models.CharField(max_length=20, null=True, blank=True)
    drilling_superintendent = models.CharField(max_length=40, null=True, blank=True)
    safety_officer = models.CharField(max_length=40, null=True, blank=True)
    incident_party = models.CharField(max_length=3, null=True, blank=True)
    incident_descr = models.CharField(max_length=1000)
    incident_severity_potential = models.CharField(max_length=1, null=True, blank=True)
    incident_severity = models.CharField(max_length=1)
    incident_type = models.ForeignKey(
        MstIncidentType, db_column="incident_type_id", on_delete=models.PROTECT, related_name="incidents"
    )
    immediate_incident_cause = models.ForeignKey(
        MstIncidentCause,
        db_column="immediate_incident_cause_id",
        on_delete=models.PROTECT,
        related_name="incidents_as_cause",
    )
    immediate_incident_cause_2 = models.ForeignKey(
        MstIncidentCause,
        db_column="immediate_incident_cause_id_2",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="incidents_as_cause_2",
    )
    immediate_cause_descr = models.CharField(max_length=500, null=True, blank=True)
    rig_operation = models.ForeignKey(
        MstRigOperation,
        db_column="rig_operation_id",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="incidents",
    )
    contact_expo_type = models.ForeignKey(
        MstContactExposureType,
        db_column="contact_expo_type_id",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="incidents",
    )
    corrective_action = models.CharField(max_length=300, null=True, blank=True)
    preventive_action = models.CharField(max_length=250, null=True, blank=True)
    npt_hrs_loss = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    manhours_loss = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    financial_loss_currency = models.ForeignKey(
        MstCurrency,
        db_column="financial_loss_currency_id",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="incidents",
    )
    financial_loss_amt = models.IntegerField(null=True, blank=True)
    exchange_rate = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True)
    financial_loss_bc_amt = models.IntegerField(null=True, blank=True)
    comments = models.CharField(max_length=200, null=True, blank=True)
    third_party = models.CharField(max_length=3, null=True, blank=True)
    contractor = models.ForeignKey(
        MstContractor,
        db_column="contractor_id",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="incidents",
    )
    operator = models.ForeignKey(
        MstOperator, db_column="operator_id", null=True, blank=True, on_delete=models.PROTECT, related_name="incidents"
    )
    incident_reported_dt = models.DateTimeField(null=True, blank=True)
    person_injured = models.CharField(max_length=1, null=True, blank=True)
    fs_emp = models.ForeignKey(
        MstEmployee, db_column="fs_emp_id", null=True, blank=True, on_delete=models.PROTECT, related_name="incidents"
    )
    emp_name = models.CharField(max_length=75, null=True, blank=True)
    rank = models.ForeignKey(
        MstRank,
        db_column="rank_id",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="incidents",
    )
    rank_name = models.CharField(max_length=35, null=True, blank=True)
    total_rig_exp_months = models.IntegerField(null=True, blank=True)
    part_of_body_1 = models.ForeignKey(
        MstPartsOfBody,
        db_column="part_of_body_id_1",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="incidents_as_pob1",
    )
    part_of_body_2 = models.ForeignKey(
        MstPartsOfBody,
        db_column="part_of_body_id_2",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="incidents_as_pob2",
    )
    part_of_body_3 = models.ForeignKey(
        MstPartsOfBody,
        db_column="part_of_body_id_3",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="incidents_as_pob3",
    )
    part_of_body_4 = models.ForeignKey(
        MstPartsOfBody,
        db_column="part_of_body_id_4",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="incidents_as_pob4",
    )
    reported_by = models.CharField(max_length=50, null=True, blank=True)
    rptd_by_rank = models.ForeignKey(
        MstRank,
        db_column="rptd_by_rank_id",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="incidents_as_reporter",
    )
    dms_path_qhse = models.CharField(max_length=250, null=True, blank=True)
    marked_as_deleted = models.CharField(max_length=1, null=True, blank=True)
    deleted_remarks = models.CharField(max_length=100, null=True, blank=True)
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "incident"

    def __str__(self):
        return f"{self.incident_no} — {self.incident_date:%Y-%m-%d}"


class IncidentAction(models.Model):
    """Corrective/preventive action items tracked against one Incident —
    straight copy of legacy eos_Incident_Actions."""

    incident_action_id = models.AutoField(primary_key=True)
    incident = models.ForeignKey(
        Incident, db_column="incident_id", on_delete=models.CASCADE, related_name="actions"
    )
    action_recommended = models.CharField(max_length=500)
    action_taken = models.CharField(max_length=250, null=True, blank=True)
    action_party = models.CharField(max_length=100)
    target_date = models.DateField(null=True, blank=True)
    completion_dt = models.DateField(null=True, blank=True)
    # Legacy's Action_Status is a free 2-char code (e.g. 'O'/'C') — kept as-is
    # rather than guessing at a choices set with no reference doc for it.
    action_status = models.CharField(max_length=2)
    marked_as_deleted = models.CharField(max_length=1, null=True, blank=True)
    deleted_remarks = models.CharField(max_length=100, null=True, blank=True)
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "incident_action"

    def __str__(self):
        return f"{self.incident} — {self.action_recommended[:40]}"


class IncidentPhoto(models.Model):
    """Straight copy of legacy eos_Incident_Photos — a photo attachment path
    per Incident."""

    incident_photo_id = models.AutoField(primary_key=True)
    incident = models.ForeignKey(
        Incident, db_column="incident_id", on_delete=models.CASCADE, related_name="photos"
    )
    incident_photo_path = models.CharField(max_length=50)
    incident_photo_active = models.CharField(max_length=1, default="Y")
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "incident_photo"

    def __str__(self):
        return f"{self.incident} — {self.incident_photo_path}"


class IncidentRootCause(models.Model):
    """Straight copy of legacy eos_Incident_Root_Cause — one or more root
    causes recorded against an Incident, each with an optional subcause."""

    incident_root_cause_id = models.AutoField(primary_key=True)
    incident = models.ForeignKey(
        Incident, db_column="incident_id", on_delete=models.CASCADE, related_name="root_causes"
    )
    root_cause = models.ForeignKey(
        MstIncidentCause, db_column="root_cause_id", on_delete=models.PROTECT, related_name="as_root_cause"
    )
    root_subcause = models.ForeignKey(
        MstIncidentSubcause,
        db_column="root_subcause_id",
        on_delete=models.PROTECT,
        related_name="as_root_subcause",
    )
    root_subcause_others = models.CharField(max_length=100, null=True, blank=True)
    marked_as_deleted = models.CharField(max_length=1, null=True, blank=True)
    deleted_remarks = models.CharField(max_length=100, null=True, blank=True)
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "incident_root_cause"

    def __str__(self):
        return f"{self.incident} — {self.root_cause}"


# ── Hazard Cards ──────────────────────────────────────────────────────────


class HazardCard(models.Model):
    """Straight copy of legacy eos_Hazard_ID_Card — a hazard/near-miss
    observation card raised against a project contract's rig. Every FK
    target already existed as a master by the time this was built, so
    unlike Incident there was no lookup-table gap to fill first."""

    haz_card_id = models.AutoField(primary_key=True)
    haz_id_card_no = models.IntegerField(null=True, blank=True)
    contract = models.ForeignKey(
        ProjectContract, db_column="prj_contract_id", on_delete=models.PROTECT, related_name="hazard_cards"
    )
    rig = models.ForeignKey(MstRig, db_column="rig_id", on_delete=models.PROTECT, related_name="hazard_cards")
    event_dt = models.DateTimeField()
    reported_by_party = models.CharField(max_length=15)
    reported_by_fs_emp = models.ForeignKey(
        MstEmployee,
        db_column="reported_by_fs_emp_id",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="hazard_cards_reported",
    )
    reported_by_name = models.CharField(max_length=30, null=True, blank=True)
    work_location = models.ForeignKey(
        MstWorkLocation, db_column="work_location_id", on_delete=models.PROTECT, related_name="hazard_cards"
    )
    haz_type = models.ForeignKey(
        MstHazardType, db_column="haz_type_id", on_delete=models.PROTECT, related_name="hazard_cards"
    )
    timeout_for_safety = models.CharField(max_length=1)
    hazard_desc = models.CharField(max_length=200)
    action_taken = models.CharField(max_length=200, null=True, blank=True)
    resp_dept = models.ForeignKey(
        MstDepartment, db_column="resp_dept_id", on_delete=models.PROTECT, related_name="hazard_cards"
    )
    resp_rank = models.ForeignKey(
        MstRank, db_column="resp_rank_id", on_delete=models.PROTECT, related_name="hazard_cards"
    )
    close_out_dt = models.DateTimeField(null=True, blank=True)
    haz_id_card_status = models.CharField(max_length=1)
    marked_as_deleted = models.CharField(max_length=1, null=True, blank=True)
    deleted_remarks = models.CharField(max_length=100, null=True, blank=True)
    # Client_Key_Id/MAC_Address are legacy's offline-client-sync bookkeeping
    # (which field device/session captured the card), not a domain
    # relationship — kept as a plain id like cr_user_id/mod_user_id.
    client_key_id = models.IntegerField(null=True, blank=True)
    mac_address = models.CharField(max_length=20, null=True, blank=True)
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "hazard_card"

    def __str__(self):
        return f"{self.haz_id_card_no} — {self.event_dt:%Y-%m-%d}"
