-- Populates activity_monitor from the legacy eos_Activity_Monitor table —
-- QHSE's Activity Monitor page. Scoped to rows whose Activity is one of
-- the Oilfield Services activities already imported into mst_activity
-- (see import_mst_activity.sql) — in practice every one of the legacy
-- table's 244 rows already falls in that scope, but the join still guards
-- against a future re-import where that's no longer true, the same way
-- the FK itself would reject an out-of-scope row anyway.
--
-- Monitor_Compl_Gap isn't carried over — this app computes it live from
-- scheduled_dt/completion_dt instead of storing it (see activity_monitor.py).
-- Requires mst_activity, mst_rig already populated.

INSERT INTO serosIT.activity_monitor
    (activity_monitor_id, activity_id, rig_id, scheduled_dt, original_scheduled_dt,
     planning_remark, completion_dt, completion_remark,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    m.Activity_Monitor_Id, m.Activity_Id, m.Rig_Id, m.Activity_Monitor_Dt, m.Original_Monitor_Dt,
    m.Planning_Remark, m.Activity_Compl_Dt, m.Completion_Remark,
    m.Cr_User_Id, m.Cr_Dt, m.Mod_User_Id, m.Mod_Dt
FROM Seros_Data.eos_Activity_Monitor m
JOIN serosIT.mst_activity a ON a.activity_id = m.Activity_Id;

ALTER TABLE serosIT.activity_monitor AUTO_INCREMENT = 245;

SELECT COUNT(*) FROM serosIT.activity_monitor;
