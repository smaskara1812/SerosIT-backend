-- Populates HSE Leading Indicators (header + detail) from the legacy
-- eos_Leading_Indicators_* tables. Verified before writing: every rig,
-- company, workgroup, indicator type and subtype id already exists here
-- with the same id, and report numbers are unique, so FKs pass straight
-- through. Total_Sessions/No_Of_Persons/Total_Duration are NOT NULL
-- (0 = blank) in both systems.
INSERT INTO serosIT.leading_indicators_hdr
    (leading_indicator_id, company_id, rig_id, report_no, period, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT Leading_Indicator_Id, Company_Id, Rig_Id, Report_No, Period, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Leading_Indicators_Hdr;
ALTER TABLE serosIT.leading_indicators_hdr AUTO_INCREMENT = 11;

INSERT INTO serosIT.leading_indicators_dtl
    (leading_indicator_dtl_id, leading_indicator_id, workgroup_id, indicator_type_id, indicator_subtype_id,
     total_sessions, no_of_persons, total_duration, duration_type, active, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT Leading_Indicator_Dtl_Id, Leading_Indicator_Id, Workgroup_Id, Indicator_Type_Id, Indicator_Subtype_Id,
       Total_Sessions, No_Of_Persons, Total_Duration, Duration_Type, Active, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Leading_Indicators_Dtl;
ALTER TABLE serosIT.leading_indicators_dtl AUTO_INCREMENT = 443;

SELECT (SELECT COUNT(*) FROM serosIT.leading_indicators_hdr) AS headers, (SELECT COUNT(*) FROM serosIT.leading_indicators_dtl) AS details;
