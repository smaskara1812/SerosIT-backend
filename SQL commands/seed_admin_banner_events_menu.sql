-- Admin > Banner Events (MySQL). Safe to run more than once.
INSERT INTO serosIT.sys_menu
    (menu_key, menu_label, menu_group, group_order, menu_order,
     view_available, add_available, edit_available, delete_available,
     export_available, upload_available, is_active, cr_dt, mod_dt)
SELECT 'admin.banner_events', 'Banner Events', 'Admin', 90, 4,
       1,1,1,1, 0,0, 1, NOW(), NOW()
FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM serosIT.sys_menu WHERE menu_key = 'admin.banner_events');
