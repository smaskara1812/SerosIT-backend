UPDATE serosIT.sys_menu
SET menu_group = 'Masters · User Mapping Masters'
WHERE menu_group = 'Masters · Mapping';

INSERT INTO serosIT.sys_menu
    (menu_key, menu_label, menu_group, group_order, menu_order,
     view_available, add_available, edit_available, delete_available,
     export_available, upload_available, is_active, cr_dt, mod_dt)
VALUES
    ('masters.fs_catg_to_rig_type_mapping', 'Category To Rig Type Mapping', 'Masters · HR Mapping Masters', 45, 1,
     1,1,1,1, 0,0, 1, NOW(), NOW());

SELECT menu_key, menu_label, menu_group, HEX(menu_group) FROM serosIT.sys_menu
WHERE menu_group IN ('Masters · User Mapping Masters', 'Masters · HR Mapping Masters');
