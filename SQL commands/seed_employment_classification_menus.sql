INSERT INTO serosIT.sys_menu
    (menu_key, menu_label, menu_group, group_order, menu_order,
     view_available, add_available, edit_available, delete_available,
     export_available, upload_available, is_active, cr_dt, mod_dt)
VALUES
    ('masters.emp_natures', 'Employment Nature', 'Masters · Employment Classification', 27, 1,
     1,1,1,1, 1,0, 1, NOW(), NOW()),
    ('masters.emp_types', 'Employment Type', 'Masters · Employment Classification', 27, 2,
     1,1,1,1, 1,0, 1, NOW(), NOW());
