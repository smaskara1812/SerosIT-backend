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
    location_id = models.IntegerField()  # Location master not built yet
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
    location_id = models.IntegerField(null=True, blank=True)
    country_id = models.IntegerField(null=True, blank=True)
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


class MstRig(models.Model):
    rig_id = models.AutoField(primary_key=True)
    rig_name = models.CharField(max_length=40)
    rig_short_name = models.CharField(max_length=8)
    old_rig_name = models.CharField(max_length=40, null=True, blank=True)
    rig_subtype_id = models.IntegerField()  # Rig Subtype master not built yet
    rig_type_id = models.IntegerField()  # Rig Type master not built yet
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
    fs_emp_id = models.IntegerField(null=True, blank=True)  # Employee master not built yet
    location_id = models.IntegerField(null=True, blank=True)  # Location master not built yet
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


class MstRank(models.Model):
    rank_id = models.AutoField(primary_key=True)
    fs_category = models.ForeignKey(
        MstFsCategory,
        db_column="fs_category_id",
        on_delete=models.PROTECT,
        related_name="ranks",
    )
    vessel_dept_id = models.IntegerField()  # Vessel Department master not built yet
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
    emp_id = models.IntegerField(null=True, blank=True)
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
