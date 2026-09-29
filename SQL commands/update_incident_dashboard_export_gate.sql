-- Incident Dashboard's Excel export and drilldown PDF are now gated on the
-- Export permission flag (not just View, see IncidentDashboardExportView /
-- IncidentDashboardDrilldownPrintView's `action = "export"` in
-- core/incident_dashboard.py) instead of falling back to "view" for every
-- action. That check reads UserPermission.can_export, which the User Rights
-- admin grid only offers a checkbox for when the menu's own
-- export_available flag is set — matching reports.incidents' (Incident
-- Register) convention, which already has real per-user Export gating.
UPDATE serosIT.sys_menu
SET export_available = 1, mod_dt = NOW()
WHERE menu_key = 'dashboards.incident_dashboard';

SELECT menu_key, menu_label, view_available, export_available FROM serosIT.sys_menu WHERE menu_key = 'dashboards.incident_dashboard';
