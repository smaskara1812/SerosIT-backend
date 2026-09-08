-- Populates mst_leaving_reason from the legacy Mst_Leaving_Reason table —
-- a brand-new table in this app, no prior import_*.sql this rides along
-- with.

INSERT INTO serosIT.mst_leaving_reason
    (leaving_reason_id, leaving_reason, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    leaving_reason_id,
    leaving_reason,
    cr_user_id,
    cr_dt,
    mod_user_id,
    mod_dt
FROM Seros_Data.Mst_Leaving_Reason;
