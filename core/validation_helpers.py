"""Small helpers shared by the legacy-rule checks in the serializers/views."""


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
