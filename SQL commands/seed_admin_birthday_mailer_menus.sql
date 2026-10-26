-- Admin > Birthday Mailer and Admin > Scheduled Mails (MySQL). Safe to run more than once.
INSERT INTO serosIT.sys_menu
    (menu_key, menu_label, menu_group, group_order, menu_order,
     view_available, add_available, edit_available, delete_available,
     export_available, upload_available, is_active, cr_dt, mod_dt)
SELECT 'admin.birthday_mailer', 'Birthday Mailer', 'Admin', 90, 5,
       1,1,1,1, 1,0, 1, NOW(), NOW()
FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM serosIT.sys_menu WHERE menu_key = 'admin.birthday_mailer');

-- Scheduled Mails: View to see it, Edit to skip, resend, send now or pause (nothing is added or deleted by hand).
INSERT INTO serosIT.sys_menu
    (menu_key, menu_label, menu_group, group_order, menu_order,
     view_available, add_available, edit_available, delete_available,
     export_available, upload_available, is_active, cr_dt, mod_dt)
SELECT 'admin.scheduled_mails', 'Scheduled Mails', 'Admin', 90, 6,
       1,0,1,0, 0,0, 1, NOW(), NOW()
FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM serosIT.sys_menu WHERE menu_key = 'admin.scheduled_mails');
