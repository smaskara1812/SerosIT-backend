import re

from rest_framework import serializers

from .models import DrillingHdr

_COORD_RE = re.compile(r"^(\d{1,3})°(\d{1,2})'(\d{1,2})\.(\d{1,2})\"([NSEW]?)$")


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

    def get_latitude_decimal(self, obj):
        return _coord_to_decimal(obj.latitude, negative_hemispheres={"S"})

    def get_longitude_decimal(self, obj):
        return _coord_to_decimal(obj.longitude, negative_hemispheres={"W"})
