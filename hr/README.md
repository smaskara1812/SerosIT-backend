# HR app (one app for the whole HR module)

All HR pages live here: `hr/models.py` (one plain file), `hr/views/`, `hr/serializers/` (add when needed), `hr/urls.py`, migrations in `hr/migrations/`. Routes are served under `/api/hr/`. It sits next to `core` and is listed in `PROJECT_APPS` in `config/settings.py` (the one list that exports, imports, History and revert, the admin, the self-test and the checks read).

## Adding an HR page: the checklist

1. **Model** in `hr/models.py`: a straight copy of the legacy table, same names, lower case. `Meta.db_table` is the legacy table name in lower case (the legacy HR tables are already `hr_...`; one without that prefix gets it). Link to core tables with a string: `models.ForeignKey("core.MstUser", ...)`.
2. `python manage.py makemigrations hr` and commit the migration file. (`scripts/check_project_structure.py` fails if you forget.)
3. **Serializer + viewset**: inherit `hr.views.HrMasterViewSet`; set `queryset`, `serializer_class`, `entity_key = "hr.<page>"` (lower case, starts with `hr.`) and `name_field`. The server refuses to start if any is missing or wrong.
4. **Register** the viewset in `hr/urls.py`.
5. **Menu row** so the page can be given rights: one row in `sys_menu` with `menu_key = 'hr.<page>'` (copy a seed from `backend/SQL commands/seed_*_menu*.sql`, MySQL and SQL Server versions). The structure check lists any HR page without one.
6. **Frontend**: add the schema or page, add its nav entry; rebuild the dropdown registry (`python scripts/build_lookup_consumers.py`) and run `scripts/check_lookup_access.py`.
7. **Legacy import**: add `db_migration/sql/import_hr_<area>.sql` (tables are written as `serosIT.hr_...`), keeping the legacy primary keys. List the legacy table in `db_migration/scripts/tables_legacy_mysql_635.txt` if it is not staged yet.
8. Run `scripts/check_project_structure.py` and the self-test.

## Safeguards (what stops a slip)

| Mistake | What catches it |
|---|---|
| HR table without `db_table`, wrong prefix or capitals | system check `hr.E001`, runs on every `manage.py` command |
| Viewset without `entity_key` (a page with no rights check), wrong key, no queryset or no `name_field` | `HrMasterViewSet` refuses at import, so the server will not start |
| Viewset on a core model by mistake | same |
| New app folder not added to `PROJECT_APPS` | system check `core.E010` |
| Model changed, migration forgotten | `scripts/check_project_structure.py` (`makemigrations --check`) |
| Code that asks for "the core app" where all apps are meant | the same script fails on any `get_app_config("core")` |
| An HR route open to anyone | the same script requests every HR route anonymously |
| HR page with no menu row | the same script |
| Export / import / History and revert / admin skipping HR tables | they all use `core/project_apps.py`; the script tests it |

Run the guard before every commit and on the Windows machine after a pull:

    python scripts/check_project_structure.py
