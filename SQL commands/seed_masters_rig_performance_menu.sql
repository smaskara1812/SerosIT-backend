-- Masters > Rig Performance (Diesel Prices, Rig Month Plans, ILM Rate Terms) (MySQL). Safe to run more than once. Run after `python manage.py migrate`.
-- The group name has a middle dot (·): this line makes the client send it as UTF-8, otherwise it is stored as "Â·".
SET NAMES utf8mb4;
INSERT INTO serosIT.sys_menu
    (menu_key, menu_label, menu_group, group_order, menu_order,
     view_available, add_available, edit_available, delete_available,
     export_available, upload_available, is_active, cr_dt, mod_dt)
SELECT 'masters.diesel_prices', 'Diesel Prices', 'Masters · Rig Performance', 70, 1,
       1,1,1,1, 1,0, 1, NOW(), NOW()
FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM serosIT.sys_menu WHERE menu_key = 'masters.diesel_prices');

INSERT INTO serosIT.sys_menu
    (menu_key, menu_label, menu_group, group_order, menu_order,
     view_available, add_available, edit_available, delete_available,
     export_available, upload_available, is_active, cr_dt, mod_dt)
SELECT 'masters.rig_month_plans', 'Rig Month Plans', 'Masters · Rig Performance', 70, 2,
       1,1,1,1, 1,0, 1, NOW(), NOW()
FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM serosIT.sys_menu WHERE menu_key = 'masters.rig_month_plans');

INSERT INTO serosIT.sys_menu
    (menu_key, menu_label, menu_group, group_order, menu_order,
     view_available, add_available, edit_available, delete_available,
     export_available, upload_available, is_active, cr_dt, mod_dt)
SELECT 'masters.ilm_rate_terms', 'ILM Rate Terms', 'Masters · Rig Performance', 70, 3,
       1,1,1,1, 1,0, 1, NOW(), NOW()
FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM serosIT.sys_menu WHERE menu_key = 'masters.ilm_rate_terms');
