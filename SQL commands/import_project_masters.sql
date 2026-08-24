-- One-time import of the Project masters + their supporting lookups from
-- the legacy Seros_Data database into the new serosIT schema. Both
-- databases live on the same MySQL server, so a plain cross-database
-- INSERT...SELECT is enough — no ETL script needed.

INSERT INTO serosIT.mst_location
    (location_id, location_name, country_id, country_state_id, location_active,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Location_Id, Location_Name, Country_Id, Country_State_Id, location_active,
    Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.Mst_Location;

INSERT INTO serosIT.mst_currency
    (currency_id, currency_name, currency_abrv, decimal_name, currency_text, currency_active,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Currency_Id, Currency_Name, Currency_Abrv, Decimal_Name, Currency_Text, Currency_Active,
    CR_USER_ID, CR_DT, MOD_USER_ID, MOD_DT
FROM Seros_Data.Mst_Currency;

INSERT INTO serosIT.mst_drilling_rate
    (drilling_rate_id, rate_code, rate_description, rate_active,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Drilling_Rate_Id, Rate_Code, NULLIF(Rate_Description, ''), Rate_Active,
    Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Mst_Drilling_Rate;

INSERT INTO serosIT.project_contract
    (prj_contract_id, location_id, operator_id, prj_contract_no, prj_short_name,
     prj_start_dt, prj_end_dt, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Prj_Contract_Id, Location_Id, Operator_Id, Prj_Contract_No, Prj_Short_Name,
    Prj_Start_Dt, Prj_End_Dt, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Mst_Project_Contract;

INSERT INTO serosIT.project_contract_dtl
    (prj_contract_dtl_id, prj_contract_id, rig_id, rig_active_from, rig_active_to,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Prj_Contract_Dtl_Id, Prj_Contract_Id, Rig_Id, Rig_Active_From, Rig_Active_To,
    Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Mst_Project_Contract_dtl;

INSERT INTO serosIT.project_drilling_rate
    (prj_drilling_rate_id, drilling_rate_id, prj_contract_id, rig_id, currency_id, rate,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Prj_Drilling_Rate_Id, Drilling_Rate_Id, Prj_Contract_Id, Rig_Id, Currency_Id, Rate,
    Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Prj_Drilling_Rate;

SELECT 'mst_location' t, COUNT(*) n FROM serosIT.mst_location
UNION ALL SELECT 'mst_currency', COUNT(*) FROM serosIT.mst_currency
UNION ALL SELECT 'mst_drilling_rate', COUNT(*) FROM serosIT.mst_drilling_rate
UNION ALL SELECT 'project_contract', COUNT(*) FROM serosIT.project_contract
UNION ALL SELECT 'project_contract_dtl', COUNT(*) FROM serosIT.project_contract_dtl
UNION ALL SELECT 'project_drilling_rate', COUNT(*) FROM serosIT.project_drilling_rate;
