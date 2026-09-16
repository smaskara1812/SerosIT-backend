-- Populates drilling_dtl_ops (the Time Log / Ops grid rows) from the
-- legacy eos_Drilling_Dtl_Ops table. Run AFTER import_drilling_dtl.sql —
-- every row here references a drilling_dtl_id that must already exist.
--
-- No FK orphans and no explicit-PK-0 row in the source (verified before
-- writing this script).

INSERT INTO serosIT.drilling_dtl_ops
    (drilling_dtl_ops_id, drilling_dtl_id, time_from, time_to, work_shift, duration,
     drilling_ops_id, drilling_section_id, depth_from, depth_to, rop_trip_mh, operation_desc,
     prj_drilling_rate_id, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Drilling_Dtl_Ops_Id, Drilling_Dtl_Id, Time_From, Time_To, Work_Shift, Duration,
    Drilling_Ops_Id, Drilling_Section_Id, Depth_From, Depth_To, ROP_Trip_MH, Operation_Desc,
    Prj_Drilling_Rate_Id, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Drilling_Dtl_Ops;
