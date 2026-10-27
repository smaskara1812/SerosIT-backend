-- Admin > Report Mails (SQL Server). Safe to run more than once. Run after `python manage.py migrate`.
-- View to see it, Edit to send a test mail, Export to download the report file.
INSERT INTO sys_menu (menu_key, menu_label, menu_group, group_order, menu_order,
                      view_available, add_available, edit_available, delete_available,
                      export_available, upload_available, is_active, cr_dt, mod_dt)
SELECT 'admin.report_mails', 'Report Mails', 'Admin', 90, 8, 1, 0, 1, 0, 1, 0, 1, GETDATE(), GETDATE()
WHERE NOT EXISTS (SELECT 1 FROM sys_menu WHERE menu_key = 'admin.report_mails');
