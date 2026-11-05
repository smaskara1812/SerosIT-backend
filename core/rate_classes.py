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
PRODUCTIVE_CLASSES = frozenset({OPERATING, STANDBY, REPAIR, FORCE_MAJEURE, RIG_MOVE})  # everything except Zero Rate
RATE_IDS_OF_CLASS = {c: sorted(i for i, k in CLASS_OF_RATE_ID.items() if k == c) for c in CLASSES}
# Classes whose hours earn money at the rate's own price per hour (a rig move is a lump sum, billed another way)
PRICED_CLASSES = frozenset({OPERATING, STANDBY, REPAIR, FORCE_MAJEURE, ZERO_RATE})
# Rig Performance shows one column per class
COLUMN_OF_CLASS = {OPERATING: "R1", STANDBY: "R2", REPAIR: "R3", ZERO_RATE: "R0", FORCE_MAJEURE: "FM", RIG_MOVE: "ILM/IPM"}


def class_of(rate_id):
    return CLASS_OF_RATE_ID.get(rate_id, UNMAPPED)


def is_productive(cls):
    return cls in PRODUCTIVE_CLASSES


def rule_text():
    """The rule in words, for the notes shown with the reports."""
    left_out = [c for c in CLASSES if c not in PRODUCTIVE_CLASSES]
    return "every class counts as productive except " + ", ".join(left_out)
