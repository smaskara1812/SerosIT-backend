-- Masters > User Mapping Masters > Signable Documents (MySQL). Safe to run more than once. Run after `python manage.py migrate`.
-- The group name has a middle dot (·): this line makes the client send it as UTF-8, otherwise it is stored as "Â·".
SET NAMES utf8mb4;
INSERT INTO serosIT.sys_menu
    (menu_key, menu_label, menu_group, group_order, menu_order,
     view_available, add_available, edit_available, delete_available,
     export_available, upload_available, is_active, cr_dt, mod_dt)
SELECT 'masters.signable_docs', 'Signable Documents', 'Masters · User Mapping Masters', 40, 5,
       1,1,1,1, 1,0, 1, NOW(), NOW()
FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM serosIT.sys_menu WHERE menu_key = 'masters.signable_docs');
