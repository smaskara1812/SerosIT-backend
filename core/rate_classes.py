"""The one place that says which time class a drilling rate belongs to and which classes count as PRODUCTIVE hours. Everything that shows productivity (the Rig
Performance report and mail, the Rig Operations dashboard) reads this, so they cannot disagree.

Classes (a rate type's hours belong to exactly one):
  Operating (R1) · Standby (R2, ILM-R2, 1/5 R2) · Repair (R3) · Zero Rate (R0) · Force Majeure (FM, FM 2/3, FM 1/3, Force majeure) ·
  Rig Move (ILM, IPM - Lateral, IPM - Adjacent) · Unmapped (anything else: Other-1..4, meterage, MOB, KMS: billing items, not time classes).
Standby follows the daily drilling report's own bucket rule (R2 and ILM-R2); Rig Move follows its RIG_MOVE_CODES.

PRODUCTIVE RULE (chosen 5 Nov 2026, to be confirmed with Arjun): every class except Zero Rate counts as productive, force majeure and rig moves included. It is
the old MIS rule, the default of the Rig Operations workbook, and the rule of two of Arjun's three rig sheets (EE01, SK02; his EE05 sheet leaves FM out and
the mentor's note says R0 and FM are both left out). To change the rule, change PRODUCTIVE_CLASSES here and nowhere else."""

OPERATING, STANDBY, REPAIR, FORCE_MAJEURE, ZERO_RATE, RIG_MOVE, UNMAPPED = "Operating", "Standby", "Repair", "Force Majeure", "Zero Rate", "Rig Move", "Unmapped"
CLASSES = [OPERATING, STANDBY, REPAIR, FORCE_MAJEURE, ZERO_RATE, RIG_MOVE]

CLASS_OF_RATE_ID = {
    1: OPERATING,
    2: STANDBY, 15: STANDBY, 18: STANDBY,
    3: REPAIR,
    4: ZERO_RATE,
    5: FORCE_MAJEURE, 16: FORCE_MAJEURE, 17: FORCE_MAJEURE, 21: FORCE_MAJEURE,
    6: RIG_MOVE, 7: RIG_MOVE, 8: RIG_MOVE,
}

# Rate ids whose class is built in (they predate the Rate class field of the Drilling Rates master). The master's own Rate class wins; this is the fallback for rows
# where it is blank.
_BUILT_IN_ORIGINAL = dict(CLASS_OF_RATE_ID)
PRODUCTIVE_CLASSES = frozenset({OPERATING, STANDBY, REPAIR, FORCE_MAJEURE, RIG_MOVE})  # everything except Zero Rate
# Classes whose hours earn money at the rate's own price per hour (a rig move is a lump sum, billed another way)
PRICED_CLASSES = frozenset({OPERATING, STANDBY, REPAIR, FORCE_MAJEURE, ZERO_RATE})
# Rig Performance shows one column per class
COLUMN_OF_CLASS = {OPERATING: "R1", STANDBY: "R2", REPAIR: "R3", ZERO_RATE: "R0", FORCE_MAJEURE: "FM", RIG_MOVE: "ILM/IPM"}


_CACHE = {"at": 0.0, "map": None, "codes": {}}
CACHE_SECONDS = 20


def clear_cache():
    _CACHE["map"] = None


def class_map():
    """{rate id: class}: the Rate class set on each Drilling Rates row, else the built-in default for the old ids. Cached for a few seconds (one query), and cleared
    when the master is saved."""
    import time

    if _CACHE["map"] is None or time.monotonic() - _CACHE["at"] > CACHE_SECONDS:
        from .models import MstDrillingRate

        m, codes = dict(_BUILT_IN_ORIGINAL), {}
        for rid, cls, code in MstDrillingRate.objects.values_list("drilling_rate_id", "rate_class", "rate_code"):
            codes[rid] = (code or "").strip()
            if cls in CLASSES:
                m[rid] = cls
        _CACHE["map"], _CACHE["codes"], _CACHE["at"] = m, codes, time.monotonic()
    return _CACHE["map"]


def class_of(rate_id):
    return class_map().get(rate_id, UNMAPPED)


def rate_ids_of(cls):
    return sorted(i for i, k in class_map().items() if k == cls)


def column_of(rate_id):
    """The Rig Performance column of a rate: its class column (R1, R2, R3, R0, FM, ILM/IPM); None when unmapped. A Standby rate added later (R2-A, R2-B, R2-C ...,
    not one of the old standby ids) gets a column of its own, named by its rate code; its hours are standby hours (productive like R2)."""
    cls = class_map().get(rate_id)
    if cls is None:
        return None
    if cls == STANDBY and rate_id not in _BUILT_IN_ORIGINAL:
        return _CACHE["codes"].get(rate_id) or COLUMN_OF_CLASS[STANDBY]
    return COLUMN_OF_CLASS.get(cls)


def added_standby_ids():
    """Standby rates added after the original ones (R2-A, R2-B, R2-C ...): they are offered with R2 wherever R2 is."""
    return {i for i, k in class_map().items() if k == STANDBY and i not in _BUILT_IN_ORIGINAL}


def extra_standby_columns(columns):
    """Of the given column names, those that are separate Standby columns (not one of the fixed ones)."""
    fixed = set(COLUMN_OF_CLASS.values()) | {"Other"}
    return [c for c in columns if c not in fixed]


def is_productive(cls):
    return cls in PRODUCTIVE_CLASSES


def rule_text():
    """The rule in words, for the notes shown with the reports."""
    left_out = [c for c in CLASSES if c not in PRODUCTIVE_CLASSES]
    return "every class counts as productive except " + ", ".join(left_out)
