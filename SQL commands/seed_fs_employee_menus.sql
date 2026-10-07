INSERT INTO serosIT.sys_menu
    (menu_key, menu_label, menu_group, group_order, menu_order,
     view_available, add_available, edit_available, delete_available,
     export_available, upload_available, is_active, cr_dt, mod_dt)
VALUES
    ('masters.fs_employees', 'FS Employee', 'Masters · HR', 20, 8, 1,1,1,1, 1,0, 1, NOW(), NOW()),
    ('masters.fs_emp_cur_status', 'FS Employee Status', 'Masters · HR', 20, 9, 1,1,1,1, 1,0, 1, NOW(), NOW());

SELECT menu_key, menu_label, menu_group, menu_order FROM serosIT.sys_menu WHERE menu_key IN ('masters.fs_employees', 'masters.fs_emp_cur_status');
