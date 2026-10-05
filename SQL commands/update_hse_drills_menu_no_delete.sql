-- Legacy frmMst_HSE_Drill has no Delete (button commented out) — the page
-- and API no longer allow it, so User Rights shouldn't offer a Delete
-- checkbox for this menu either.
UPDATE serosIT.sys_menu
SET delete_available = 0, mod_dt = NOW()
WHERE menu_key = 'masters.hse_drills';

-- Anyone already granted Delete on it loses the now-meaningless flag.
UPDATE serosIT.sys_user_permissions
SET can_delete = 0
WHERE menu_key = 'masters.hse_drills' AND can_delete = 1;

SELECT menu_key, view_available, add_available, edit_available, delete_available FROM serosIT.sys_menu WHERE menu_key = 'masters.hse_drills';
