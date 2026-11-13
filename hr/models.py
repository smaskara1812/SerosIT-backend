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
