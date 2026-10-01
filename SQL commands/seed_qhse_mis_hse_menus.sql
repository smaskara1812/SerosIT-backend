-- Same gap as qhse.hse_drill_record (see seed_qhse_hse_drill_record_menu.sql):
-- both MIS Monthly HSE Return and Monthly HSE Review are gated by
-- permission_classes = [HasMenuPermission] with these entity_keys, but
-- neither ever got a sys_menu row, so no non-admin has ever had a User
-- Rights row to grant themselves access to either page.
INSERT INTO serosIT.sys_menu
    (menu_key, menu_label, menu_group, group_order, menu_order,
     view_available, add_available, edit_available, delete_available,
     export_available, upload_available, is_active, cr_dt, mod_dt)
VALUES
    ('qhse.mis_hse_return', 'MIS Monthly HSE Return', 'QHSE', 86, 12, 1,1,1,1, 0,0, 1, NOW(), NOW()),
    ('qhse.mis_hse_review', 'Monthly HSE Review', 'QHSE', 86, 13, 1,0,0,0, 1,0, 1, NOW(), NOW());

SELECT menu_key, menu_label, menu_group, menu_order FROM serosIT.sys_menu WHERE menu_key IN ('qhse.mis_hse_return', 'qhse.mis_hse_review');
