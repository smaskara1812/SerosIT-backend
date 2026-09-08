INSERT INTO serosIT.sys_menu
    (menu_key, menu_label, menu_group, group_order, menu_order,
     view_available, add_available, edit_available, delete_available,
     export_available, upload_available, is_active, cr_dt, mod_dt)
VALUES
    ('masters.continents', 'Continent', 'Masters · Regional Information', 31, 1,
     1,1,1,1, 1,0, 1, NOW(), NOW()),
    ('masters.countries', 'Country', 'Masters · Regional Information', 31, 2,
     1,1,1,1, 1,0, 1, NOW(), NOW()),
    ('masters.country_states', 'Country State', 'Masters · Regional Information', 31, 3,
     1,1,1,1, 1,0, 1, NOW(), NOW()),
    ('masters.locations', 'Location', 'Masters · Regional Information', 31, 4,
     1,1,1,1, 1,0, 1, NOW(), NOW());
