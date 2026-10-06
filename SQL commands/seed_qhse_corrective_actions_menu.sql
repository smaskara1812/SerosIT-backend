INSERT INTO serosIT.sys_menu
    (menu_key, menu_label, menu_group, group_order, menu_order,
     view_available, add_available, edit_available, delete_available,
     export_available, upload_available, is_active, cr_dt, mod_dt)
VALUES
    ('qhse.corrective_actions', 'Corrective Actions Reporting', 'QHSE', 86, 18, 1,1,1,1, 1,0, 1, NOW(), NOW());

SELECT menu_key, menu_label, menu_group, menu_order FROM serosIT.sys_menu WHERE menu_key = 'qhse.corrective_actions';
