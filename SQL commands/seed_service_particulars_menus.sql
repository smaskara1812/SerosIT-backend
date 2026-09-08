INSERT INTO serosIT.sys_menu
    (menu_key, menu_label, menu_group, group_order, menu_order,
     view_available, add_available, edit_available, delete_available,
     export_available, upload_available, is_active, cr_dt, mod_dt)
VALUES
    ('masters.serv_types', 'Service Type', 'Masters · Service Particulars', 28, 1,
     1,1,1,1, 1,0, 1, NOW(), NOW()),
    ('masters.serv_subtypes', 'Service Subtype', 'Masters · Service Particulars', 28, 2,
     1,1,1,1, 1,0, 1, NOW(), NOW()),
    ('masters.fs_catg_to_sstype', 'FS Category To Service Subtype', 'Masters · Service Particulars', 28, 3,
     1,1,1,1, 1,0, 1, NOW(), NOW());
