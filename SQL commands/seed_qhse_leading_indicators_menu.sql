-- No Delete in legacy (frmLeading_Indicators_Hdr has no delete path), no Print.
INSERT INTO serosIT.sys_menu
    (menu_key, menu_label, menu_group, group_order, menu_order,
     view_available, add_available, edit_available, delete_available,
     export_available, upload_available, is_active, cr_dt, mod_dt)
VALUES
    ('qhse.leading_indicators', 'HSE - Leading Indicators', 'QHSE', 86, 16, 1,1,1,0, 0,0, 1, NOW(), NOW());

SELECT menu_key, menu_label, menu_group, menu_order FROM serosIT.sys_menu WHERE menu_key = 'qhse.leading_indicators';
