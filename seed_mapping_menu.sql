INSERT INTO serosIT.sys_menu
    (menu_key, menu_label, menu_group, group_order, menu_order,
     view_available, add_available, edit_available, delete_available,
     export_available, upload_available, is_active, cr_dt, mod_dt)
VALUES
    ('masters.user_rig_mapping', 'User Rig Mapping', 'Masters · Mapping', 40, 1, 1,1,1,1, 0,0, 1, NOW(), NOW()),
    ('masters.user_category_mapping', 'User Category Mapping', 'Masters · Mapping', 40, 2, 1,1,1,1, 0,0, 1, NOW(), NOW()),
    ('masters.doc_to_sign_mapping', 'Document To Sign Mapping', 'Masters · Mapping', 40, 3, 1,1,1,1, 0,0, 1, NOW(), NOW()),
    ('masters.interviewer_mapping', 'Department To Interviewer Mapping', 'Masters · Mapping', 40, 4, 1,1,1,1, 0,1, 1, NOW(), NOW());

SELECT menu_key, menu_label, menu_group, group_order, menu_order FROM serosIT.sys_menu WHERE menu_group = 'Masters · Mapping' ORDER BY menu_order;
