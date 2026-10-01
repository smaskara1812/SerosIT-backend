-- Found via a systematic sweep (every entity_key referenced in core/*.py
-- diffed against actual sys_menu rows) while chasing the same gap as
-- qhse.hse_drill_record / qhse.mis_hse_return / qhse.mis_hse_review: these
-- three masters pages (all real dedicated nav pages, not dropdown-only —
-- confirmed in frontend/src/config/nav.js) use the default
-- permission_classes = [HasMenuPermission], but none ever got a sys_menu
-- row, so no non-admin has ever had a User Rights row for any of them.
-- masters.hse_drills is the Type of Drill master added this session;
-- masters.hse_manhours_parties and masters.hse_meetings predate this
-- session's work entirely — this gap isn't new.
INSERT INTO serosIT.sys_menu
    (menu_key, menu_label, menu_group, group_order, menu_order,
     view_available, add_available, edit_available, delete_available,
     export_available, upload_available, is_active, cr_dt, mod_dt)
VALUES
    ('masters.hse_manhours_parties', 'HSE Manhours Party', 'Masters · QHSE', 30, 11, 1,1,1,1, 1,0, 1, NOW(), NOW()),
    ('masters.hse_meetings', 'HSE Meeting', 'Masters · QHSE', 30, 12, 1,1,1,1, 1,0, 1, NOW(), NOW()),
    ('masters.hse_drills', 'HSE Drill', 'Masters · QHSE', 30, 13, 1,1,1,1, 1,0, 1, NOW(), NOW());

SELECT menu_key, menu_label, menu_group, menu_order FROM serosIT.sys_menu
WHERE menu_key IN ('masters.hse_manhours_parties', 'masters.hse_meetings', 'masters.hse_drills');
