-- Admin > Report Mails (MySQL). Safe to run more than once. View to see it, Edit to send a test mail, Export to download the report file.
INSERT INTO serosIT.sys_menu
    (menu_key, menu_label, menu_group, group_order, menu_order,
     view_available, add_available, edit_available, delete_available,
     export_available, upload_available, is_active, cr_dt, mod_dt)
SELECT 'admin.report_mails', 'Report Mails', 'Admin', 90, 8,
       1,0,1,0, 1,0, 1, NOW(), NOW()
FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM serosIT.sys_menu WHERE menu_key = 'admin.report_mails');
