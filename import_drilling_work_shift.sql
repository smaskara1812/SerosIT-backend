INSERT INTO serosIT.mst_drilling_work_shift
    (drilling_work_shift_id, prj_contract_id, rig_id, work_shift,
     work_shift_start_time, work_shift_end_time, work_shift_days, work_shift_active,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Drilling_Work_Shift_Id, Prj_Contract_Id, Rig_Id, Work_Shift,
    Work_Shift_Start_Time, Work_Shift_End_Time, Work_Shift_Days, COALESCE(Work_Shift_Active, 'Y'),
    Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Drilling_Work_Shift;

SELECT COUNT(*) FROM serosIT.mst_drilling_work_shift;
