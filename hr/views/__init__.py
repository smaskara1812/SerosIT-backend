from django.core.exceptions import ImproperlyConfigured

from core.masters_views import BaseMasterViewSet


class HrMasterViewSet(BaseMasterViewSet):
    """Base for every HR page that is a simple master (list, add, edit, delete with User Rights and an audit trail). Use it instead of
    BaseMasterViewSet so a forgotten setting is caught when the server starts, not when someone opens the page:

        class CandidateViewSet(HrMasterViewSet):
            queryset = Candidate.objects.all()
            serializer_class = CandidateSerializer
            entity_key = "hr.candidates"       # must start with "hr." and match the page's sys_menu row
            name_field = "candidate_name"
    """

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        where = f"{cls.__module__}.{cls.__name__}"
        key = cls.__dict__.get("entity_key") or getattr(cls, "entity_key", None)
        if not key or not str(key).startswith("hr.") or str(key) != str(key).lower() or " " in str(key):
            raise ImproperlyConfigured(
                f"{where}: entity_key must be set, lower case, and start with 'hr.' (for example 'hr.candidates'). Got {key!r}. "
                "It is the page's name in User Rights (sys_menu.menu_key); without it the page would have no rights check.")
        if getattr(cls, "queryset", None) is None or getattr(cls, "serializer_class", None) is None:
            raise ImproperlyConfigured(f"{where}: set both queryset and serializer_class.")
        if cls.queryset.model._meta.app_label != "hr":
            raise ImproperlyConfigured(f"{where}: its queryset is on {cls.queryset.model.__name__}, which is not an HR model.")
        if not getattr(cls, "name_field", None):
            raise ImproperlyConfigured(f"{where}: set name_field (the column used to name a record in the history log and to sort the list).")
