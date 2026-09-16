-- Fixes a mistake made during the post-import bulk recompute: that pass
-- assumed every Drilling_Dtl's hour/meterage totals could be reconstructed
-- from its own Drilling_Dtl_Ops rows, and zeroed them out for any day with
-- none. But 1,519 of 7,734 days (mostly pre-2020, before the detailed
-- Ops-level time log existed) have real, legacy-entered hour totals with
-- no Ops rows to back them — those got wrongly wiped to 0.00. This
-- restores the original imported values for exactly those rows; every
-- other row (which does have real Ops rows) keeps its recomputed value.

UPDATE serosIT.drilling_dtl d
JOIN Seros_Data.eos_Drilling_Dtl src ON src.Drilling_Dtl_Id = d.drilling_dtl_id
SET
    d.operating_hrs = src.Operating_Hrs,
    d.standby_hrs = src.Standby_Hrs,
    d.repair_service_hrs = src.Repair_Service_Hrs,
    d.repair_rate_hrs = src.Repair_Rate_Hrs,
    d.zero_rate_hrs = src.Zero_Rate_Hrs,
    d.rig_move_hrs = src.Rig_Move_Hrs,
    d.drilling_meterage = src.Drilling_Meterage
WHERE NOT EXISTS (
    SELECT 1 FROM serosIT.drilling_dtl_ops o WHERE o.drilling_dtl_id = d.drilling_dtl_id
);
