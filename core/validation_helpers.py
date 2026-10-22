"""Small helpers shared by the legacy-rule checks in the serializers/views."""
from rest_framework import serializers


def fields_changed(instance, data, *names):
    """True for a new record, or when any of these fields is being given a different
    value than the saved one (text compared without surrounding spaces, since the
    serializer trims what it receives and imported values may be padded).

    Used so a rule is only checked when the fields it involves are new or changed:
    an old record that already breaks a rule can still be edited for something else."""
    if instance is None:
        return True

    def norm(v):
        v = getattr(v, "pk", v)
        return v.strip() or None if isinstance(v, str) else (v if v not in ("", None) else None)

    return any(name in data and norm(data[name]) != norm(getattr(instance, name, None)) for name in names)


# ── Rules every form shares: email, telephone, latitude/longitude and the year of a date ───────────────────────────────────────────────
# The browser's own date box accepts any year (a date typed as 12-01-26 arrives as 0026) and its email box accepts "a@b", so the server judges
# both itself. Like the other rules, a value is only judged when it is new or changed, so an old record stays editable.
import re

MIN_YEAR = 1900
MAX_YEAR = 2100
YEAR_MESSAGE = f"The year must be between {MIN_YEAR} and {MAX_YEAR}. Type it in full, like 2026."

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)*\.[A-Za-z]{2,}$")
EMAIL_MESSAGE = "Enter a valid email address, like name@company.com."
# The fields that hold an email address (a plain text column), by name.
EMAIL_FIELD_NAMES = {
    "mail_from_address", "email_id", "rig_email_id", "user_email", "vendor_email", "fs_emp_email_official", "fs_emp_email_pers",
    "email_addr", "trainer_email_id", "training_org_email",
}

# Document To Sign Mapping's Document Name is one of these, as in the old system (frontend/src/lib/mastersChecks.js has the same list).
DOC_TO_SIGN_NAMES = (
    "Appreciation_Ltr_Offshore", "Appreciation_Ltr_Onshore", "Conformation_Ltr_Offshore", "Conformation_Ltr_Onshore",
    "Contract_Extension_Ltr_Offshore", "Contract_Extension_Ltr_Onshore", "Experience_Ltr_Offshore", "Experience_Ltr_Onshore",
    "Increment_Ltr_Offshore", "Increment_Ltr_Onshore", "Joining_Contracts_Offshore", "Joining_Contracts_Onshore",
    "Material_Requisition", "Material_Requisition_Onshore", "Offer_Ltr_Offshore", "Offer_Ltr_Onshore",
    "Promotion_Ltr_Offshore", "Promotion_Ltr_Onshore", "Salary_Correction_Ltr_Offshore", "Salary_Correction_Ltr_Onshore",
    "Service_Requisition_Offshore", "Service_Requisition_Onshore", "Termination_Ltr_Offshore", "Termination_Ltr_Onshore",
    "User_Defined_Resume_Offshore", "User_Defined_Resume_Onshore", "Warning_Ltr_Offshore", "Warning_Ltr_Onshore",
)


def year_message(text):
    """For a date given as text (YYYY-MM-DD...), the year message when its year is outside 1900-2100, else ''."""
    m = re.match(r"\s*(\d+)-\d{1,2}-\d{1,2}", str(text or ""))
    return YEAR_MESSAGE if m and not MIN_YEAR <= int(m.group(1)) <= MAX_YEAR else ""


def is_valid_email(value):
    return bool(EMAIL_RE.fullmatch(str(value or "").strip()))


def phone_error(value):
    tel = str(value or "").strip()
    if not re.fullmatch(r"[0-9+()/ -]+", tel):
        return "Telephone can have only digits and + - ( ) / and spaces."
    if len(re.findall(r"\d", tel)) < 8:
        return "Telephone must have at least 8 digits."
    return ""


def dms_error(value, axis):
    """Legacy degrees-minutes-seconds, e.g. 18°58'00.00" or 072°49'00.00"E. `axis` is "lat" or "lon". '' when fine."""
    text = str(value or "").strip()
    lat = axis == "lat"
    m = re.fullmatch(r"(\d{1,3})°(\d{1,2})'(\d{1,2}(?:\.\d+)?)\"([A-Za-z]?)", text)
    if not m:
        example = "18°58'00.00\"" if lat else "072°49'00.00\"E"
        return f"Use degrees, minutes and seconds, like {example}."
    deg, minute, sec, letter = int(m.group(1)), int(m.group(2)), float(m.group(3)), m.group(4)
    if letter and letter.upper() not in ("NS" if lat else "EW"):
        return f"The letter at the end must be {'N or S' if lat else 'E or W'}."
    limit = 90 if lat else 180
    if deg > limit or (deg == limit and (minute or sec)):
        return f"{'Latitude' if lat else 'Longitude'} can't be more than {limit} degrees."
    if minute > 59 or sec >= 60:
        return "Minutes and seconds must be below 60."
    return ""


class StrictEmail:
    """A field validator: the address must look like name@company.com, judged when it is new or changed."""

    requires_context = True

    def __call__(self, value, serializer_field):
        text = str(value or "").strip()
        if not text:
            return
        inst = getattr(serializer_field.parent, "instance", None)
        if inst is not None and getattr(inst, serializer_field.source or serializer_field.field_name, None) == value:
            return
        if not EMAIL_RE.fullmatch(text):
            raise serializers.ValidationError(EMAIL_MESSAGE)


def _judge_year(field, result):
    if result is None or MIN_YEAR <= result.year <= MAX_YEAR:
        return
    inst = getattr(field.parent, "instance", None)
    if inst is not None and hasattr(inst, "pk") and getattr(inst, field.source or field.field_name, None) == result:
        return  # an old record that already has such a date can still be edited
    raise serializers.ValidationError(YEAR_MESSAGE)


def install_global_checks():
    """Called once at start-up (core/apps.py): every date field refuses a year outside 1900-2100, and the fields named in EMAIL_FIELD_NAMES
    must hold a real email address, on every serializer that builds them from the model."""
    if getattr(serializers, "_seros_checks_installed", False):
        return
    serializers._seros_checks_installed = True

    for cls in (serializers.DateField, serializers.DateTimeField):
        original = cls.to_internal_value

        def make(original):
            def to_internal_value(self, value):
                result = original(self, value)
                _judge_year(self, result)
                return result

            return to_internal_value

        cls.to_internal_value = make(original)

    build = serializers.ModelSerializer.build_standard_field

    def build_standard_field(self, field_name, model_field):
        field_class, kwargs = build(self, field_name, model_field)
        if field_name in EMAIL_FIELD_NAMES and issubclass(field_class, serializers.CharField) and not kwargs.get("read_only"):
            kwargs["validators"] = [*kwargs.get("validators", []), StrictEmail()]
        return field_class, kwargs

    serializers.ModelSerializer.build_standard_field = build_standard_field
