-- Masters > Mail Alert Masters > Rig Alert Recipients (MySQL). Safe to run more than once. Run after `python manage.py migrate`.
SET NAMES utf8mb4;
INSERT INTO serosIT.sys_menu
    (menu_key, menu_label, menu_group, group_order, menu_order,
     view_available, add_available, edit_available, delete_available,
     export_available, upload_available, is_active, cr_dt, mod_dt)
SELECT 'masters.rig_alert_recipients', 'Rig Alert Recipients', 'Masters · Mail Alert Masters', 33, 6,
       1,1,1,1, 1,0, 1, NOW(), NOW()
FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM serosIT.sys_menu WHERE menu_key = 'masters.rig_alert_recipients');
