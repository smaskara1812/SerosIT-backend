INSERT INTO serosIT.sys_menu
    (menu_key, menu_label, menu_group, group_order, menu_order,
     view_available, add_available, edit_available, delete_available,
     export_available, upload_available, is_active, cr_dt, mod_dt)
VALUES
    ('masters.drilling_operations', 'Drilling Operations', 'Masters · Drilling', 60, 1, 1,1,1,1, 0,0, 1, NOW(), NOW()),
    ('masters.drilling_sections', 'Drilling Sections', 'Masters · Drilling', 60, 2, 1,1,1,1, 0,0, 1, NOW(), NOW());

SELECT menu_key, menu_label, menu_group, HEX(menu_group) FROM serosIT.sys_menu WHERE menu_group = 'Masters · Drilling' ORDER BY menu_order;
