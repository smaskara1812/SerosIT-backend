-- HSE Leading Indicators: Delete (not in legacy, but provided — admins simply
-- never grant it) and Excel Export (list and per-report) now exist.
UPDATE serosIT.sys_menu
SET delete_available = 1, export_available = 1, mod_dt = NOW()
WHERE menu_key = 'qhse.leading_indicators';

SELECT menu_key, view_available, add_available, edit_available, delete_available, export_available FROM serosIT.sys_menu WHERE menu_key = 'qhse.leading_indicators';
