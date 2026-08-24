INSERT INTO serosIT.sys_menu
    (menu_key, menu_label, menu_group, group_order, menu_order,
     view_available, add_available, edit_available, delete_available,
     export_available, upload_available, is_active, cr_dt, mod_dt)
VALUES
    ('masters.rig_types', 'Rig Types', 'Masters · General', 10, 8, 1,1,1,1, 0,0, 1, NOW(), NOW()),
    ('masters.rig_subtypes', 'Rig Subtypes', 'Masters · General', 10, 9, 1,1,1,1, 0,0, 1, NOW(), NOW());

SELECT menu_key, menu_label, menu_group, HEX(menu_group) FROM serosIT.sys_menu WHERE menu_key IN ('masters.rig_types','masters.rig_subtypes');
