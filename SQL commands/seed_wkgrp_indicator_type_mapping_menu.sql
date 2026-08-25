INSERT INTO serosIT.sys_menu
    (menu_key, menu_label, menu_group, group_order, menu_order,
     view_available, add_available, edit_available, delete_available,
     export_available, upload_available, is_active, cr_dt, mod_dt)
VALUES
    ('masters.wkgrp_indicator_type_mapping', 'Workgroup To Indicator Type Mapping', 'Masters · HSE Mapping Masters', 47, 1,
     1,1,1,1, 0,0, 1, NOW(), NOW());

SELECT menu_key, menu_label, menu_group, HEX(menu_group) FROM serosIT.sys_menu WHERE menu_key = 'masters.wkgrp_indicator_type_mapping';
