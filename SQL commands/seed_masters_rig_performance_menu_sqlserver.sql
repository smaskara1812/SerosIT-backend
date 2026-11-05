-- Masters > Rig Performance (Diesel Prices, Rig Month Plans, ILM Rate Terms) (SQL Server). Safe to run more than once. Run after `python manage.py migrate`.
INSERT INTO sys_menu (menu_key, menu_label, menu_group, group_order, menu_order,
                      view_available, add_available, edit_available, delete_available,
                      export_available, upload_available, is_active, cr_dt, mod_dt)
SELECT 'masters.diesel_prices', 'Diesel Prices', N'Masters · Rig Performance', 70, 1, 1, 1, 1, 1, 1, 0, 1, GETDATE(), GETDATE()
WHERE NOT EXISTS (SELECT 1 FROM sys_menu WHERE menu_key = 'masters.diesel_prices');

INSERT INTO sys_menu (menu_key, menu_label, menu_group, group_order, menu_order,
                      view_available, add_available, edit_available, delete_available,
                      export_available, upload_available, is_active, cr_dt, mod_dt)
SELECT 'masters.rig_month_plans', 'Rig Month Plans', N'Masters · Rig Performance', 70, 2, 1, 1, 1, 1, 1, 0, 1, GETDATE(), GETDATE()
WHERE NOT EXISTS (SELECT 1 FROM sys_menu WHERE menu_key = 'masters.rig_month_plans');

INSERT INTO sys_menu (menu_key, menu_label, menu_group, group_order, menu_order,
                      view_available, add_available, edit_available, delete_available,
                      export_available, upload_available, is_active, cr_dt, mod_dt)
SELECT 'masters.ilm_rate_terms', 'ILM Rate Terms', N'Masters · Rig Performance', 70, 3, 1, 1, 1, 1, 1, 0, 1, GETDATE(), GETDATE()
WHERE NOT EXISTS (SELECT 1 FROM sys_menu WHERE menu_key = 'masters.ilm_rate_terms');
