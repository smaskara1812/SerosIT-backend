INSERT INTO serosIT.sys_menu
    (menu_key, menu_label, menu_group, group_order, menu_order,
     view_available, add_available, edit_available, delete_available,
     export_available, upload_available, is_active, cr_dt, mod_dt)
VALUES
    ('masters.rig_operations', 'Rig Operation', 'Masters · QHSE', 30, 1, 1,1,1,1, 0,0, 1, NOW(), NOW()),
    ('masters.contact_exposure_types', 'Contact Exposure Type', 'Masters · QHSE', 30, 2, 1,1,1,1, 0,0, 1, NOW(), NOW()),
    ('masters.indicator_types', 'Indicator Type', 'Masters · QHSE', 30, 3, 1,1,1,1, 0,0, 1, NOW(), NOW()),
    ('masters.indicator_subtypes', 'Indicator Subtype', 'Masters · QHSE', 30, 4, 1,1,1,1, 0,0, 1, NOW(), NOW()),
    ('masters.parts_of_body', 'Parts Of Body', 'Masters · QHSE', 30, 5, 1,1,1,1, 0,0, 1, NOW(), NOW()),
    ('masters.qhse_categories', 'QHSE Category', 'Masters · QHSE', 30, 6, 1,1,1,1, 0,0, 1, NOW(), NOW()),
    ('masters.hse_activities', 'HSE Activity', 'Masters · QHSE', 30, 7, 1,1,1,1, 0,0, 1, NOW(), NOW()),
    ('masters.hse_consumables', 'HSE Consumable', 'Masters · QHSE', 30, 8, 1,1,1,1, 0,0, 1, NOW(), NOW()),
    ('masters.hazard_types', 'Hazard Type', 'Masters · QHSE', 30, 9, 1,1,1,1, 0,0, 1, NOW(), NOW());

SELECT menu_key, menu_label, menu_group, group_order, menu_order FROM serosIT.sys_menu WHERE menu_group = 'Masters · QHSE' ORDER BY menu_order;
