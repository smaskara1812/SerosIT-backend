-- Populates mst_leaving_reason_dtl from the legacy Mst_Leaving_Reason_Dtl
-- table — a brand-new table in this app, no prior import_*.sql this rides
-- along with. Requires mst_leaving_reason already populated (see
-- import_leaving_reason.sql).

INSERT INTO serosIT.mst_leaving_reason_dtl
    (leaving_reason_dtl_id, leaving_reason_id, leaving_reason_dtl,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    leaving_reason_dtl_id,
    leaving_reason_id,
    leaving_reason_dtl,
    cr_user_id,
    cr_dt,
    mod_user_id,
    mod_dt
FROM Seros_Data.Mst_Leaving_Reason_Dtl;
