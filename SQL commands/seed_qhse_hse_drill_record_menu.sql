-- The HSE Drill Record page (and its Events/Observations/Improvements/
-- Corrective Action child tabs, which all share this same entity_key —
-- matching legacy's own single intMenu_id threaded through every child
-- iframe) was built and wired to permission_classes = [HasMenuPermission]
-- with entity_key = "qhse.hse_drill_record", but no sys_menu row was ever
-- seeded for it. Found while adding the child tabs: a non-admin user has
-- no row in User Rights to grant themselves access to any of this, since
-- HasMenuPermission denies anything without a matching sys_menu-backed
-- UserPermission row (is_app_admin bypasses it, which is why this wasn't
-- noticed during testing).
INSERT INTO serosIT.sys_menu
    (menu_key, menu_label, menu_group, group_order, menu_order,
     view_available, add_available, edit_available, delete_available,
     export_available, upload_available, is_active, cr_dt, mod_dt)
VALUES
    ('qhse.hse_drill_record', 'HSE Drills / Exercises', 'QHSE', 86, 11, 1,1,1,1, 0,0, 1, NOW(), NOW());

SELECT menu_key, menu_label, menu_group, menu_order FROM serosIT.sys_menu WHERE menu_key = 'qhse.hse_drill_record';
