INSERT INTO serosIT.sys_menu
    (menu_key, menu_label, menu_group, group_order, menu_order,
     view_available, add_available, edit_available, delete_available,
     export_available, upload_available, is_active, cr_dt, mod_dt)
VALUES
    ('masters.project_contract', 'Project Contract', 'Masters · Projects', 50, 1, 1,1,1,1, 0,0, 1, NOW(), NOW()),
    ('masters.project_drilling_rates', 'Project Drilling Rates', 'Masters · Projects', 50, 2, 1,1,1,1, 0,0, 1, NOW(), NOW());

SELECT menu_key, menu_label, menu_group, group_order, menu_order FROM serosIT.sys_menu WHERE menu_group = 'Masters · Projects' ORDER BY menu_order;
