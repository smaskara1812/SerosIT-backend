import json

from django.db import models


class PortableJSONField(models.TextField):
    """
    JSONField that works on both MySQL and SQL Server — mssql-django has no
    native JSONField support (fields.E180). Stores JSON as text, transparent
    to calling code via from_db_value/get_prep_value.
    """

    def __init__(self, *args, **kwargs):
        self.default_value = kwargs.pop("default", None)
        super().__init__(*args, default=self.default_value, **kwargs)

    def from_db_value(self, value, expression, connection):
        if value is None:
            return None
        return json.loads(value)

    def to_python(self, value):
        if value is None or not isinstance(value, str):
            return value
        return json.loads(value)

    def get_prep_value(self, value):
        if value is None:
            return None
        return json.dumps(value)
