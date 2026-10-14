-- SQL Server version of the four dashboard menu seeds (compliance radar, safety performance,
-- fuel and water, rig moves). Safe to run more than once: a row is only added if its key is missing.
-- Tables are unqualified so they resolve to the login's default schema, same as Django's tables.
DECLARE @rows TABLE (k nvarchar(100), label nvarchar(100), ord int, exp bit);
INSERT INTO @rows VALUES
  ('dashboards.compliance_radar',   'Compliance Radar',   9,  1),
  ('dashboards.safety_performance', 'Safety Performance', 10, 0),
  ('dashboards.fuel_water',         'Fuel and Water',     11, 0),
  ('dashboards.rig_moves',          'Rig Moves',          12, 0);

INSERT INTO sys_menu (menu_key, menu_label, menu_group, group_order, menu_order,
                      view_available, add_available, edit_available, delete_available,
                      export_available, upload_available, is_active, cr_dt, mod_dt)
SELECT r.k, r.label, 'Dashboards', 100, r.ord, 1, 0, 0, 0, r.exp, 0, 1, GETDATE(), GETDATE()
FROM @rows r
WHERE NOT EXISTS (SELECT 1 FROM sys_menu m WHERE m.menu_key = r.k);

SELECT menu_key, menu_label, menu_order, view_available, export_available, is_active
FROM sys_menu WHERE menu_key IN (SELECT k FROM @rows) ORDER BY menu_order;
