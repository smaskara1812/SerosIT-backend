INSERT INTO serosIT.sys_menu
    (menu_key, menu_label, menu_group, group_order, menu_order,
     view_available, add_available, edit_available, delete_available,
     export_available, upload_available, is_active, cr_dt, mod_dt)
VALUES
    ('masters.buss_cert_types', 'Certificate Type', 'Masters · General', 10, 14,
     1,1,1,1, 1,0, 1, NOW(), NOW());
