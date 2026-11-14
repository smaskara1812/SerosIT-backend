"""HR models: straight copies of the legacy HR tables, in this one file.

Same names as legacy, lower case (the legacy HR tables are already prefixed hr_):

    legacy hr_Mst_NonEmployee  ->  class MstNonEmployee, db_table = "hr_mst_nonemployee"
    legacy Emp_Id              ->  emp_id

Every model sets db_table explicitly, lower case, starting with "hr_" (a legacy HR-area table that has no hr_ prefix gets one, so it can
never clash with a core table). Link to core tables with a string, for example models.ForeignKey("core.MstUser", ...).
"""

from django.db import models  # noqa: F401


class CandidateInterviewHdr(models.Model):
    """Candidate Interview Details (legacy eos.Candidate_Interview_Hdr): one row per candidate interviewed for a crew post.

    Entered by HR on the page, or by the candidate through an invite link (later). Rules (also enforced by the serializer):
    date of birth makes the person at least 18, experience in the current post is not more than total experience, Suitable_For_Role is
    Y or N, Hiring_Status is N (new, the default), R (rejected), S (selected) or O (on hold), and the interview date is not in the future.
    The resume file is stored under media/candidate_resumes/ and candidate_cert_path holds its relative path.
    candidate_submitted_dt is new (not in legacy): set when the candidate submits the form himself; the list shows a "New" badge for 24 hours.
    """

    candidate_interview_hdr_id = models.AutoField(primary_key=True)
    candidate_fname = models.CharField(max_length=20)
    candidate_mname = models.CharField(max_length=20, null=True, blank=True)
    candidate_lname = models.CharField(max_length=20)
    present_addr = models.CharField(max_length=100, null=True, blank=True)
    permanent_addr = models.CharField(max_length=100, null=True, blank=True)
    father_name = models.CharField(max_length=40, null=True, blank=True)
    nationality = models.CharField(max_length=25, null=True, blank=True)
    designated_post = models.CharField(max_length=25, null=True, blank=True)
    edu_qualification = models.CharField(max_length=200, null=True, blank=True)
    candidate_dob = models.DateField(null=True, blank=True)
    email_id = models.CharField(max_length=40)
    mobile_no = models.CharField(max_length=10)
    rig = models.ForeignKey("core.MstRig", db_column="rig_id", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    tot_experience_yrs = models.PositiveSmallIntegerField(null=True, blank=True)
    tot_experience_mths = models.PositiveSmallIntegerField(null=True, blank=True)
    exp_in_curr_pos_yrs = models.PositiveSmallIntegerField(null=True, blank=True)
    exp_in_curr_pos_mths = models.PositiveSmallIntegerField(null=True, blank=True)
    interview_dt = models.DateField(null=True, blank=True)
    rank = models.ForeignKey("core.MstRank", db_column="rank_id", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    candidate_cert_path = models.CharField(max_length=200, blank=True, default="")
    recruitment_source = models.CharField(max_length=50, null=True, blank=True)
    hiring_reccomendation = models.CharField(max_length=75, null=True, blank=True)
    overall_performance = models.PositiveSmallIntegerField(null=True, blank=True)
    suitable_for_role = models.CharField(max_length=1, null=True, blank=True)
    additional_notes = models.CharField(max_length=200, null=True, blank=True)
    hiring_status = models.CharField(max_length=1, default="N")
    candidate_submitted_dt = models.DateTimeField(null=True, blank=True)
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "hr_candidate_interview_hdr"
        constraints = [
            models.CheckConstraint(condition=models.Q(suitable_for_role__isnull=True) | models.Q(suitable_for_role__in=["Y", "N"]), name="hr_cand_suitable_yn"),
            models.CheckConstraint(condition=models.Q(hiring_status__in=["N", "R", "S", "O"]), name="hr_cand_hiring_status"),
        ]

    def __str__(self):
        return " ".join(p for p in (self.candidate_fname, self.candidate_mname, self.candidate_lname) if p)


class CandidateTrainingDtl(models.Model):
    """Trainings and certificates a candidate holds (legacy eos.Candidate_Training_Dtl)."""

    candidate_train_dtl_id = models.AutoField(primary_key=True)
    hdr = models.ForeignKey(CandidateInterviewHdr, db_column="candidate_interview_hdr_id", on_delete=models.CASCADE, related_name="trainings")
    training_type = models.CharField(max_length=50)
    training_agency = models.CharField(max_length=75)
    training_cert_no = models.CharField(max_length=25)
    training_cert_dt = models.DateField()
    cert_valid_from_dt = models.DateField()
    cert_valid_to_dt = models.DateField()
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "hr_candidate_training_dtl"


class CandidateExperienceDtl(models.Model):
    """A candidate's earlier jobs (legacy eos.Candidate_Experience_Dtl). Years and months are worked out from the two dates."""

    candidate_exp_dtl_id = models.AutoField(primary_key=True)
    hdr = models.ForeignKey(CandidateInterviewHdr, db_column="candidate_interview_hdr_id", on_delete=models.CASCADE, related_name="experiences")
    exp_from_dt = models.DateField()
    exp_to_dt = models.DateField()
    exp_years = models.PositiveSmallIntegerField()
    exp_months = models.PositiveSmallIntegerField()
    company_name = models.CharField(max_length=100)
    designation = models.CharField(max_length=25)
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "hr_candidate_experience_dtl"


class CandidateInterviewCompetency(models.Model):
    """Interviewer ratings per competency for a candidate (legacy eos.Candidate_Interview_Competency). Shown read-only for now."""

    candidate_interview_comp_id = models.AutoField(primary_key=True)
    hdr = models.ForeignKey(CandidateInterviewHdr, db_column="candidate_interview_hdr_id", on_delete=models.CASCADE, related_name="competencies")
    department = models.ForeignKey("core.MstDepartment", db_column="dept_id", on_delete=models.PROTECT, related_name="+")
    interviewer = models.ForeignKey("core.MstInterviewer", db_column="interviewer_id", on_delete=models.PROTECT, related_name="+")
    competency = models.ForeignKey("core.MstCompetency", db_column="competency_id", on_delete=models.PROTECT, related_name="+")
    rating = models.PositiveSmallIntegerField()
    remarks = models.CharField(max_length=75, null=True, blank=True)
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "hr_candidate_interview_competency"
        constraints = [models.CheckConstraint(condition=models.Q(rating__gte=1) & models.Q(rating__lte=3), name="hr_cand_comp_rating_1_3")]


class CandidateInvite(models.Model):
    """An invitation for one person to fill in the Candidate Interview form himself (no legacy table; new in this system).

    HR creates it with a name and ONE email address. The link carries a random token; only its SHA-256 is stored, so the table never holds a usable
    link. The candidate opens the link, asks for a code that is mailed to the invited address, enters it, and fills the form in steps. What he has
    typed is kept as private JSON in `draft` (not in the candidate tables) until he presses Submit; then the candidate rows are created and the
    draft is cleared. The code (also stored only as a hash) lives 10 minutes, may be sent 3 times an hour and tried 5 times, then the invite locks.
    """

    candidate_invite_id = models.AutoField(primary_key=True)
    token_hash = models.CharField(max_length=64, unique=True)
    candidate_name = models.CharField(max_length=60)
    email_id = models.CharField(max_length=40)
    expires_dt = models.DateTimeField()
    opened_dt = models.DateTimeField(null=True, blank=True)
    verified_dt = models.DateTimeField(null=True, blank=True)
    submitted_dt = models.DateTimeField(null=True, blank=True)
    cancelled_dt = models.DateTimeField(null=True, blank=True)
    hdr = models.ForeignKey(CandidateInterviewHdr, db_column="candidate_interview_hdr_id", on_delete=models.SET_NULL, null=True, blank=True, related_name="invites")
    otp_hash = models.CharField(max_length=64, blank=True, default="")
    otp_expires_dt = models.DateTimeField(null=True, blank=True)
    otp_sent_count = models.PositiveSmallIntegerField(default=0)
    otp_window_start = models.DateTimeField(null=True, blank=True)
    otp_attempts = models.PositiveSmallIntegerField(default=0)
    locked = models.BooleanField(default=False)
    session_nonce = models.CharField(max_length=32, blank=True, default="")
    draft = models.TextField(blank=True, default="")
    draft_version = models.PositiveIntegerField(default=0)
    draft_saved_dt = models.DateTimeField(null=True, blank=True)
    resume_path = models.CharField(max_length=200, blank=True, default="")
    last_mail_dt = models.DateTimeField(null=True, blank=True)
    resend_count = models.PositiveSmallIntegerField(default=0)
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "hr_candidate_invite"


class FsNewApplDtl(models.Model):
    """Applicants (legacy eos.Fs_New_Appl_Dtl): one row per person who applied for a field-staff (crew) job. Rig Personnel > New Joinee Workflow > Applicants.

    Differences from legacy: the five CDC columns (number, date, country, place, valid till) are not carried, by decision; `cv_path` is new (legacy kept the CV as
    Images/Fs_Emp_CV/<id>.zip with no column). Rules (serializer, hr/views/applicants.py): date of birth makes the person at least 15 and is in the past, the
    application date is not in the future, gender M or F, marital status Unmarried or Married (a marriage date for Married), a user may only work with the FS
    categories he is mapped to. Status is N (new, the default), C (closed), R (rejected), A (accepted: set when the offer letter is marked Accepted) or J (joined); only the hiring flow moves it. In the legacy copy a new
    applicant's N was stored blank, so the import turns blank into N (and the two lower-case "c" into C).
    """

    fs_new_appl_id = models.AutoField(primary_key=True)
    fs_new_appl_no = models.IntegerField()
    fs_new_appl_dt = models.DateField()
    fs_emp_fname = models.CharField(max_length=30, null=True, blank=True)
    fs_emp_mname = models.CharField(max_length=30, null=True, blank=True)
    fs_emp_lname = models.CharField(max_length=30)
    fathers_name = models.CharField(max_length=60, null=True, blank=True)
    permanent_addr = models.CharField(max_length=125)
    mailing_addr = models.CharField(max_length=100)
    emergency_addr = models.CharField(max_length=100, null=True, blank=True)
    fs_emp_tel_no = models.CharField(max_length=25, null=True, blank=True)
    fs_emp_mobile_no = models.CharField(max_length=25, null=True, blank=True)
    fs_emp_email_pers = models.CharField(max_length=40)
    gender = models.CharField(max_length=1)
    blood_group = models.CharField(max_length=10, null=True, blank=True)
    fs_emp_dob = models.DateField()
    fs_emp_pob = models.CharField(max_length=20, null=True, blank=True)
    marital_status = models.CharField(max_length=10, null=True, blank=True)
    marriage_dt = models.DateField(null=True, blank=True)
    nationality = models.ForeignKey("core.MstCountry", db_column="nationality_id", on_delete=models.PROTECT, related_name="+")
    home_town = models.ForeignKey("core.MstLocation", db_column="home_town_id", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    domicile_state = models.ForeignKey("core.MstCountryState", db_column="domicile_state_id", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    religion = models.CharField(max_length=20, null=True, blank=True)
    qualification = models.ForeignKey("core.MstQualification", db_column="qualification_id", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    pan_no = models.CharField(max_length=10, null=True, blank=True)
    aadhaar_no = models.CharField(max_length=20, null=True, blank=True)
    area_of_interest = models.CharField(max_length=15, null=True, blank=True)
    fs_emp_photo_path = models.CharField(max_length=100, null=True, blank=True)
    cv_path = models.CharField(max_length=100, null=True, blank=True)
    pp_no = models.CharField(max_length=15, null=True, blank=True)
    pp_dt = models.DateField(null=True, blank=True)
    pp_country = models.ForeignKey("core.MstCountry", db_column="pp_country_id", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    pin_code = models.CharField(max_length=10, null=True, blank=True)
    pp_place = models.ForeignKey("core.MstLocation", db_column="pp_place_id", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    pp_valid_till = models.DateField(null=True, blank=True)
    pp_ecnr = models.CharField(max_length=1, null=True, blank=True)
    appl_fs_category = models.ForeignKey("core.MstFsCategory", db_column="appl_fs_category_id", on_delete=models.PROTECT, related_name="+")
    appl_rank = models.ForeignKey("core.MstRank", db_column="appl_rank_id", on_delete=models.PROTECT, related_name="+")
    appl_emp_type = models.ForeignKey("core.MstEmpType", db_column="appl_emp_type_id", on_delete=models.PROTECT, related_name="+")
    appl_temporary = models.CharField(max_length=1, null=True, blank=True)
    fs_new_appl_status = models.CharField(max_length=1, default="N")
    fs_emp = models.ForeignKey("core.MstFsEmployee", db_column="fs_emp_id", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    prv_fs_emp = models.ForeignKey("core.MstFsEmployee", db_column="prv_fs_emp_id", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "hr_fs_new_appl_dtl"
        constraints = [
            models.CheckConstraint(condition=models.Q(fs_new_appl_status__in=["N", "C", "R", "A", "J"]), name="hr_fs_appl_status"),
            models.CheckConstraint(condition=models.Q(gender__in=["M", "F"]), name="hr_fs_appl_gender"),
        ]

    def __str__(self):
        return " ".join(p for p in (self.fs_emp_fname, self.fs_emp_mname, self.fs_emp_lname) if p and p.strip())


class FsOfferLetter(models.Model):
    """The offer letter of an applicant (legacy eos.Fs_Offer_Letter, one row per applicant): the header. The pay is in FsOfferLetterComponent rows (components come from core.MstEd) and
    salary_amt is the total the components must add up to. Creator and approver steps: cr_status N/F (creator finalised), l1_approval_status N/A/R
    (level 1 approver). offer_letter_status N new, S sent, C changed, R resent; response_status N, A accepted, D declined, C closed (the response
    is passed on to the applicant's status). The signer (authority) is a user; legacy kept an employee id."""

    fs_new_appl = models.OneToOneField(FsNewApplDtl, db_column="fs_new_appl_id", primary_key=True, on_delete=models.CASCADE, related_name="offer_letter")
    fs_offer_letter_dt = models.DateField()
    rank = models.ForeignKey("core.MstRank", db_column="rank_id", on_delete=models.PROTECT, related_name="+")
    rank_to_grade_id = models.IntegerField(null=True, blank=True)
    rig_site_mapping = models.ForeignKey("core.RigSiteMapping", db_column="rig_site_mapping_id", on_delete=models.PROTECT, related_name="+")
    contact_person = models.CharField(max_length=50, null=True, blank=True)
    contact_tel_no = models.CharField(max_length=25, null=True, blank=True)
    fs_offer_letter_doj = models.DateField()
    contract_end_dt = models.DateField()
    salary_amt = models.IntegerField()
    included_pf = models.CharField(max_length=1, null=True, blank=True)
    on_off_desc = models.CharField(max_length=1000, null=True, blank=True)
    on_days = models.IntegerField(null=True, blank=True)
    off_days = models.IntegerField(null=True, blank=True)
    travel_eligibility = models.ForeignKey("core.TravelEligibility", db_column="travel_eligibility_id", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    travel_class = models.CharField(max_length=325, null=True, blank=True)
    authority_user = models.ForeignKey("core.MstUser", db_column="authority_user_id", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    authority_designation = models.CharField(max_length=50, null=True, blank=True)
    key_personnel = models.CharField(max_length=1, null=True, blank=True)
    company = models.ForeignKey("core.MstCompany", db_column="company_id", on_delete=models.PROTECT, related_name="+")
    rig_location = models.CharField(max_length=50, null=True, blank=True)
    offer_letter_status = models.CharField(max_length=1, blank=True, default="")
    response_status = models.CharField(max_length=1, blank=True, default="")
    cr_status = models.CharField(max_length=1, null=True, blank=True)
    l1_approval_status = models.CharField(max_length=1, null=True, blank=True)
    l1_approval_dt = models.DateField(null=True, blank=True)
    l1_user_id = models.IntegerField(null=True, blank=True)
    opened_for_revision_by = models.IntegerField(null=True, blank=True)
    opened_for_revision_dt = models.DateField(null=True, blank=True)  # a date, like the other approval pages (core/approvals.py writes dates)
    revision_note = models.CharField(max_length=500, null=True, blank=True)  # new: why the approver sent the letter back
    auto_closed_dt = models.DateTimeField(null=True, blank=True)  # new: set when the system closed the letter for inactivity (hr/offer_letter_autoclose.py)
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "hr_fs_offer_letter"


class FsOfferLetterComponent(models.Model):
    """One pay component of an offer letter: the amount, whether it counts toward the letter's total salary, and whether it is shown in the letter.
    Replaces the legacy money columns (Basic_Salary, HRA, PF_Emplr, Camp_Allow ...)."""

    id = models.AutoField(primary_key=True)
    offer_letter = models.ForeignKey(FsOfferLetter, db_column="fs_new_appl_id", on_delete=models.CASCADE, related_name="components")
    component = models.ForeignKey("core.MstEd", db_column="component_id", on_delete=models.PROTECT, related_name="letter_rows")  # the pay component (Masters > Earnings and Deductions)
    amount = models.IntegerField(default=0)
    counts_in_total = models.CharField(max_length=1, default="Y")
    show_in_letter = models.CharField(max_length=1, default="Y")
    sort_order = models.SmallIntegerField(default=0)

    class Meta:
        db_table = "hr_fs_offer_letter_component"
        constraints = [
            models.UniqueConstraint(fields=["offer_letter", "component"], name="hr_offer_comp_unique"),
            models.CheckConstraint(condition=models.Q(counts_in_total__in=["Y", "N"]), name="hr_offer_comp_counts_y_n"),
            models.CheckConstraint(condition=models.Q(show_in_letter__in=["Y", "N"]), name="hr_offer_comp_show_y_n"),
        ]


class CtrlNtbrFs(models.Model):
    """The "not to be rehired" register for field staff (legacy dbo.Ctrl_Ntbr_Fs, 101 rows; business system 6 is the oilfield services one). The Applicants page
    warns when a new applicant matches a person here by date of birth and a name. Read only."""

    ntbr_fs_id = models.AutoField(primary_key=True)
    fs_emp_id = models.IntegerField()  # most rows belong to the other business system, whose employees are not in this app: no foreign key
    ntbr_fs_cdc_no = models.CharField(max_length=15)
    pan = models.CharField(max_length=10, null=True, blank=True)
    ntbr_fs_dob = models.DateField()
    ntbr_cnfm_dt = models.DateField()
    remark = models.CharField(max_length=150)
    ntbr_approved_by = models.CharField(max_length=150)
    business_system_id = models.IntegerField()
    ntbr_scan_path = models.CharField(max_length=65)
    ntbr_rejoin = models.CharField(max_length=1, blank=True, default="")
    ntbr_rejoin_remark = models.CharField(max_length=150, null=True, blank=True)
    cr_user_id = models.IntegerField()
    cr_dt = models.DateTimeField()
    mod_user_id = models.IntegerField(null=True, blank=True)
    mod_dt = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "hr_ctrl_ntbr_fs"
