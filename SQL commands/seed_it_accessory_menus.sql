INSERT INTO serosIT.sys_menu
    (menu_key, menu_label, menu_group, group_order, menu_order,
     view_available, add_available, edit_available, delete_available,
     export_available, upload_available, is_active, cr_dt, mod_dt)
VALUES
    ('masters.it_accessories', 'IT Accessory', 'Masters · IT Asset Masters', 65, 7,
     1,1,1,1, 1,0, 1, NOW(), NOW()),
    ('it_asset.it_accessory_holders', 'IT Accessory Holder', 'IT Asset', 80, 4,
     1,1,1,1, 1,0, 1, NOW(), NOW());
