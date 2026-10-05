-- Populates HSE Weekly Drill (header + detail) from the legacy
-- eos_HSE_Weekly_Drill_* tables. Verified before writing: no duplicate
-- rig/year/week or hdr/drill pairs, and every rig and drill id already
-- exists here with the same id, so every FK is a straight passthrough.
INSERT INTO serosIT.hse_weekly_drill_hdr
    (hse_weekly_drill_hdr_id, rig_id, drill_year, drill_week, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT HSE_Weekly_Drill_Hdr_Id, Rig_Id, Drill_Year, Drill_Week, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_HSE_Weekly_Drill_Hdr;
ALTER TABLE serosIT.hse_weekly_drill_hdr AUTO_INCREMENT = 37;

INSERT INTO serosIT.hse_weekly_drill_dtl
    (hse_weekly_drill_dtl_id, hse_weekly_drill_hdr_id, hse_drill_id, drill_conducted_dt, drill_last_conducted_dt, remarks,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT HSE_Weekly_Drill_Dtl_Id, HSE_Weekly_Drill_Hdr_Id, HSE_Drill_Id, Drill_Conducted_Dt, Drill_Last_Conducted_Dt, Remarks,
       Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_HSE_Weekly_Drill_Dtl;
ALTER TABLE serosIT.hse_weekly_drill_dtl AUTO_INCREMENT = 68;

SELECT (SELECT COUNT(*) FROM serosIT.hse_weekly_drill_hdr) AS headers, (SELECT COUNT(*) FROM serosIT.hse_weekly_drill_dtl) AS details;
