INSERT INTO serosIT.sys_menu
    (menu_key, menu_label, menu_group, group_order, menu_order,
     view_available, add_available, edit_available, delete_available,
     export_available, upload_available, is_active, cr_dt, mod_dt)
VALUES
    ('masters.nationality_to_emp_type_mapping', 'Nationality To Emp Type Mapping', 'Masters · HR Mapping Masters', 45, 3,
     1,1,1,1, 0,0, 1, NOW(), NOW());

SELECT menu_key, menu_label, menu_group FROM serosIT.sys_menu WHERE menu_key = 'masters.nationality_to_emp_type_mapping';
