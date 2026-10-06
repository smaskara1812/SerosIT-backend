-- Populates HSE Lagging Indicators (header + detail) from the legacy
-- eos_Lagging_Indicators_* tables. Verified before writing: every rig,
-- company, workgroup, indicator type and subtype id already exists here
-- with the same id. Report numbers repeat across Leading and Lagging
-- ("1", "11/16", "02") — fine, Report No is unique within each kind only.
INSERT INTO serosIT.lagging_indicators_hdr
    (lagging_indicator_id, company_id, rig_id, report_no, period, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT Lagging_Indicator_Id, Company_Id, Rig_Id, Report_No, Period, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Lagging_Indicators_Hdr;
ALTER TABLE serosIT.lagging_indicators_hdr AUTO_INCREMENT = 4;

INSERT INTO serosIT.lagging_indicators_dtl
    (lagging_indicator_dtl_id, lagging_indicator_id, workgroup_id, indicator_type_id, indicator_subtype_id,
     total_count, active, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT Lagging_Indicator_Dtl_Id, Lagging_Indicator_Id, Workgroup_Id, Indicator_Type_Id, Indicator_Subtype_Id,
       Total_Count, Active, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Lagging_Indicators_Dtl;
ALTER TABLE serosIT.lagging_indicators_dtl AUTO_INCREMENT = 82;

SELECT (SELECT COUNT(*) FROM serosIT.lagging_indicators_hdr) AS headers, (SELECT COUNT(*) FROM serosIT.lagging_indicators_dtl) AS details;
