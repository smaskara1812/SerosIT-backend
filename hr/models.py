"""HR models: straight copies of the legacy HR tables, in this one file.

Same names as legacy, lower case (the legacy HR tables are already prefixed hr_):

    legacy hr_Mst_NonEmployee  ->  class MstNonEmployee, db_table = "hr_mst_nonemployee"
    legacy Emp_Id              ->  emp_id

Every model sets db_table explicitly, lower case, starting with "hr_" (a legacy HR-area table that has no hr_ prefix gets one, so it can
never clash with a core table). Link to core tables with a string, for example models.ForeignKey("core.MstUser", ...).
"""

from django.db import models  # noqa: F401
