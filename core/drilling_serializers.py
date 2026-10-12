import re

from django.utils import timezone
from rest_framework import serializers

from .models import DrillingHdr
from .validation_helpers import fields_changed

_COORD_RE = re.compile(r"^(\d{1,3})°(\d{1,2})'(\d{1,2})\.(\d{1,2})\"([NSEW]?)$")


# Degree limits per coordinate: a latitude can't pass 90, a longitude can't pass 180.
_DEGREE_LIMIT = {"latitude": 90, "longitude": 180}
_HEMISPHERES = {"latitude": "NS", "longitude": "EW"}


def _check_coordinate(name, label, value):
    """A message for a coordinate that isn't `DD°MM'SS.ff"H` with valid parts, else None."""
    match = _COORD_RE.match(value or "")
    if not match:
        return f"{label} must be degrees, minutes and seconds (for example 08°36'00.00\"N)."
    deg, minutes, sec, _frac, hemisphere = match.groups()
    if int(deg) > _DEGREE_LIMIT[name]:
        return f"{label} degrees must be between 0 and {_DEGREE_LIMIT[name]}."
    if int(minutes) > 59:
        return f"{label} minutes must be between 0 and 59."
    if int(sec) > 59:
        return f"{label} seconds must be between 0 and 59."
    if hemisphere and hemisphere not in _HEMISPHERES[name]:
        return f"{label} zone must be {_HEMISPHERES[name][0]} or {_HEMISPHERES[name][1]}."
    return None


def _coord_to_decimal(value, negative_hemispheres):
    """`08°36'00.00"N` -> 8.6 — used for the map view only; the DMS string
    stays the column of record (see DrillingHdr's model docstring)."""
    match = _COORD_RE.match(value) if value else None
    if not match:
        return None
    deg, minutes, sec, frac, hemisphere = match.groups()
    decimal = int(deg) + int(minutes) / 60 + float(f"{sec}.{frac}") / 3600
    return -decimal if hemisphere in negative_hemispheres else decimal


class DrillingHdrSerializer(serializers.ModelSerializer):
    contract_no = serializers.CharField(source="contract.prj_contract_no", read_only=True, default="")
    rig_name = serializers.CharField(source="rig.rig_name", read_only=True, default="")
    drilling_rate_code = serializers.CharField(source="drilling_rate.rate_code", read_only=True, default="")
    latitude_decimal = serializers.SerializerMethodField()
    longitude_decimal = serializers.SerializerMethodField()

    class Meta:
        model = DrillingHdr
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def validate(self, attrs):
        inst = self.instance
        get = lambda name: attrs.get(name, getattr(inst, name, None))
        errors = {}
        now = timezone.now()

        if get("contract") is None and fields_changed(inst, attrs, "contract"):
            errors["contract"] = "Choose a Project."
        for name, label in (("latitude", "Latitude"), ("longitude", "Longitude")):
            if name in attrs and fields_changed(inst, attrs, name):
                message = _check_coordinate(name, label, attrs[name])
                if message:
                    errors[name] = message
        if "location" in attrs:
            attrs["location"] = attrs["location"].strip()
            if not attrs["location"]:
                errors["location"] = "This field is required."

        depth = get("total_water_depth")
        if inst is None and depth is None:
            errors["total_water_depth"] = "Enter the Total Water Depth."
        elif depth is not None and depth < 0 and fields_changed(inst, attrs, "total_water_depth"):
            errors["total_water_depth"] = "Total Water Depth can't be negative."
        total_depth = get("total_depth")
        if depth is not None and total_depth is not None and fields_changed(inst, attrs, "total_depth", "total_water_depth") and total_depth <= depth:
            errors["total_depth"] = "Total Depth must be more than the Total Water Depth."

        anchor = get("first_anchor_down_dt")
        if anchor and fields_changed(inst, attrs, "first_anchor_down_dt") and anchor > now:
            errors["first_anchor_down_dt"] = "First Anchor Down date and time can't be in the future."

        distance = get("distance_covered_kms_knots")
        if distance is None and fields_changed(inst, attrs, "distance_covered_kms_knots") and (inst is None or "distance_covered_kms_knots" in attrs):
            errors["distance_covered_kms_knots"] = "Enter the Nautical Miles / Kilometres Covered."
        elif distance is not None and distance < 0 and fields_changed(inst, attrs, "distance_covered_kms_knots"):
            errors["distance_covered_kms_knots"] = "Nautical Miles / Kilometres Covered can't be negative."
        if get("drilling_rate") is None and fields_changed(inst, attrs, "drilling_rate") and (inst is None or "drilling_rate" in attrs):
            errors["drilling_rate"] = "Choose the Rig Move Rate Type."

        completion = get("drilling_completion_dt")
        if completion and fields_changed(inst, attrs, "drilling_completion_dt", "first_anchor_down_dt"):
            if completion > now:
                errors["drilling_completion_dt"] = "Drilling Completion date and time can't be in the future."
            elif anchor and completion.date() < anchor.date():
                errors["drilling_completion_dt"] = "Drilling Completion can't be before the First Anchor Down date."

        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def get_latitude_decimal(self, obj):
        return _coord_to_decimal(obj.latitude, negative_hemispheres={"S"})

    def get_longitude_decimal(self, obj):
        return _coord_to_decimal(obj.longitude, negative_hemispheres={"W"})
