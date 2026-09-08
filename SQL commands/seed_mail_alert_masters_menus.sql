INSERT INTO serosIT.sys_menu
    (menu_key, menu_label, menu_group, group_order, menu_order,
     view_available, add_available, edit_available, delete_available,
     export_available, upload_available, is_active, cr_dt, mod_dt)
VALUES
    ('masters.business_systems', 'Business System', 'Masters · General', 10, 20,
     1,1,1,1, 1,0, 1, NOW(), NOW()),
    ('masters.mail_alerts', 'Alert Details', 'Masters · Mail Alert Masters', 33, 1,
     1,1,1,1, 1,0, 1, NOW(), NOW()),
    ('masters.mail_alert_to_users', 'Alert To Users', 'Masters · Mail Alert Masters', 33, 2,
     1,1,1,1, 1,0, 1, NOW(), NOW());
