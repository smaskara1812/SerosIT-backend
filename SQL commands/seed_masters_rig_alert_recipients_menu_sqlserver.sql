-- Masters > Mail Alert Masters > Rig Alert Recipients (SQL Server). Safe to run more than once. Run after `python manage.py migrate`.
INSERT INTO sys_menu (menu_key, menu_label, menu_group, group_order, menu_order,
                      view_available, add_available, edit_available, delete_available,
                      export_available, upload_available, is_active, cr_dt, mod_dt)
SELECT 'masters.rig_alert_recipients', 'Rig Alert Recipients', N'Masters · Mail Alert Masters', 33, 6, 1, 1, 1, 1, 1, 0, 1, GETDATE(), GETDATE()
WHERE NOT EXISTS (SELECT 1 FROM sys_menu WHERE menu_key = 'masters.rig_alert_recipients');
