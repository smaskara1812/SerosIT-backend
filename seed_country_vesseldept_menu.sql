INSERT INTO serosIT.sys_menu
    (menu_key, menu_label, menu_group, group_order, menu_order,
     view_available, add_available, edit_available, delete_available,
     export_available, upload_available, is_active, cr_dt, mod_dt)
VALUES
    ('masters.continents', 'Continents', 'Masters · General', 10, 10, 1,1,1,1, 0,0, 1, NOW(), NOW()),
    ('masters.countries', 'Countries', 'Masters · General', 10, 11, 1,1,1,1, 0,0, 1, NOW(), NOW()),
    ('masters.country_states', 'Country States', 'Masters · General', 10, 12, 1,1,1,1, 0,0, 1, NOW(), NOW()),
    ('masters.vessel_depts', 'Vessel Departments', 'Masters · General', 10, 13, 1,1,1,1, 0,0, 1, NOW(), NOW());

SELECT menu_key, menu_label, HEX(menu_group) FROM serosIT.sys_menu WHERE menu_key IN
    ('masters.continents','masters.countries','masters.country_states','masters.vessel_depts');
