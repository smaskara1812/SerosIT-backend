-- Backfills mst_incident_subcause with the rows missing since the original
-- import_incident_children.sql run (that one only had Seros_Data's own
-- local mirror up to Incident_Subcause_Id 127 — a stale-mirror gap, same
-- root cause as the Mail_Alert_Dtl/Mail_Alert_To_User ones fixed earlier).
-- The real table goes to 209 and includes the "Others (...)" catch-all
-- subcause rows (196-207) that QHSE's Incident Root Cause page needs —
-- see core/incident_serializers.py's IncidentRootCauseSerializer for how
-- those get detected (by name pattern, not a hardcoded id list).
--
-- REPLACE (not INSERT) so any row already present gets refreshed to the
-- current source content too, not just the new tail — verified beforehand
-- that the overlapping 1-127 rows are identical to what's already loaded,
-- so this is a no-op for those and a real backfill for 128-209.

REPLACE INTO serosIT.mst_incident_subcause
    (incident_subcause_id, incident_subcause, incident_cause_id, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT Incident_Subcause_Id, Incident_Subcause, Incident_Cause_Id, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.Mstx_Incident_Subcause;

ALTER TABLE serosIT.mst_incident_subcause AUTO_INCREMENT = 210;

SELECT COUNT(*), MIN(incident_subcause_id), MAX(incident_subcause_id) FROM serosIT.mst_incident_subcause;
