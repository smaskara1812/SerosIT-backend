-- Rig Personnel > Candidate Competencies Details (MySQL). Safe to run more than once. Run after `python manage.py migrate`.
INSERT INTO serosIT.sys_menu
    (menu_key, menu_label, menu_group, group_order, menu_order,
     view_available, add_available, edit_available, delete_available,
     export_available, upload_available, is_active, cr_dt, mod_dt)
SELECT 'hr.candidate_competencies', 'Candidate Competencies Details', 'Rig Personnel', 87, 2,
       1,1,1,0, 1,0, 1, NOW(), NOW()
FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM serosIT.sys_menu WHERE menu_key = 'hr.candidate_competencies');
