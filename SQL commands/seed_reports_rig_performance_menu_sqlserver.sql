-- Reports > Rig Performance (Report, Masters) (SQL Server). Safe to run more than once. Run after `python manage.py migrate`.
INSERT INTO sys_menu (menu_key, menu_label, menu_group, group_order, menu_order,
                      view_available, add_available, edit_available, delete_available,
                      export_available, upload_available, is_active, cr_dt, mod_dt)
SELECT 'reports.rig_performance', 'Rig Performance Report', 'Reports', 70, 3, 1, 0, 0, 0, 1, 0, 1, GETDATE(), GETDATE()
WHERE NOT EXISTS (SELECT 1 FROM sys_menu WHERE menu_key = 'reports.rig_performance');

INSERT INTO sys_menu (menu_key, menu_label, menu_group, group_order, menu_order,
                      view_available, add_available, edit_available, delete_available,
                      export_available, upload_available, is_active, cr_dt, mod_dt)
SELECT 'reports.rig_performance_masters', 'Rig Performance Masters', 'Reports', 70, 4, 1, 1, 1, 0, 0, 0, 1, GETDATE(), GETDATE()
WHERE NOT EXISTS (SELECT 1 FROM sys_menu WHERE menu_key = 'reports.rig_performance_masters');
