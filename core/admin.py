"""
Every model in this app is auto-registered with Django admin below, purely
as a dev/ops convenience for browsing and quick-editing the raw tables
(the real app UI is the React masters/reports pages, gated by the real
User Rights permission system — this admin site is superuser-only via
Django's own auth, separate from that). New models get admin coverage for
free without anyone needing to remember to register them by hand.
"""

from django.apps import apps
from django.contrib import admin

# Keep the list view readable even for wide operational tables (Incident
# has ~50 columns) — show the PK plus a handful of the model's own fields.
MAX_LIST_FIELDS = 8
MAX_SEARCH_FIELDS = 5
TEXT_FIELD_TYPES = ("CharField", "TextField", "EmailField")


class AutoAdmin(admin.ModelAdmin):
    def __init__(self, model, admin_site):
        concrete_fields = [f.name for f in model._meta.fields]
        self.list_display = concrete_fields[:MAX_LIST_FIELDS]
        self.search_fields = [
            f.name
            for f in model._meta.fields
            if f.get_internal_type() in TEXT_FIELD_TYPES and not f.choices
        ][:MAX_SEARCH_FIELDS]
        super().__init__(model, admin_site)


for _model in apps.get_app_config("core").get_models():
    try:
        admin.site.register(_model, AutoAdmin)
    except admin.sites.AlreadyRegistered:
        pass
