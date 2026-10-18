-- Admin > Banner Events (SQL Server). Safe to run more than once. Run after `python manage.py migrate`.
INSERT INTO sys_menu (menu_key, menu_label, menu_group, group_order, menu_order,
                      view_available, add_available, edit_available, delete_available,
                      export_available, upload_available, is_active, cr_dt, mod_dt)
SELECT 'admin.banner_events', 'Banner Events', 'Admin', 90, 4, 1, 1, 1, 1, 0, 0, 1, GETDATE(), GETDATE()
WHERE NOT EXISTS (SELECT 1 FROM sys_menu WHERE menu_key = 'admin.banner_events');
