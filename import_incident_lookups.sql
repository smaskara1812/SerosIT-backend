INSERT INTO serosIT.mst_work_location
    (work_location_id, work_location, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT Work_Location_Id, Work_Location, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.Mstx_Work_Location;
ALTER TABLE serosIT.mst_work_location AUTO_INCREMENT = 122;

INSERT INTO serosIT.mst_incident_type
    (incident_type_id, incident_type, incident_abrv, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT Incident_Type_Id, Incident_Type, Incident_Abrv, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.Mstx_Incident_Type;
ALTER TABLE serosIT.mst_incident_type AUTO_INCREMENT = 21;

INSERT INTO serosIT.mst_incident_cause
    (incident_cause_id, incident_cause_desc, incident_cause_category, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT Incident_Cause_Id, Incident_Cause_Desc, Incident_Cause_Category, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.Mstx_Incident_Cause;
ALTER TABLE serosIT.mst_incident_cause AUTO_INCREMENT = 63;

INSERT INTO serosIT.mst_financial_year
    (financial_year_id, fin_year_from, fin_year_to, fin_year_text, fin_year_subtext,
     assessment_year, nri_days, fin_year_status, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT Financial_Year_Id, Fin_Year_From, Fin_Year_To, Fin_Year_Text, Fin_Year_Subtext,
       Assessment_Year, NRI_Days, Fin_Year_Status, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.Mst_Financial_Year;
ALTER TABLE serosIT.mst_financial_year AUTO_INCREMENT = 23;

SELECT COUNT(*) FROM serosIT.mst_work_location;
SELECT COUNT(*) FROM serosIT.mst_incident_type;
SELECT COUNT(*) FROM serosIT.mst_incident_cause;
SELECT COUNT(*) FROM serosIT.mst_financial_year;
