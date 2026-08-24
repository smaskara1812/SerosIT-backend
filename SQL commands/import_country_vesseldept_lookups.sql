INSERT INTO serosIT.mst_continent
    (continent_id, continent_name, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT Continent_Id, Continent_Name, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.Mst_Continent;
ALTER TABLE serosIT.mst_continent AUTO_INCREMENT = 6;

INSERT INTO serosIT.mst_country
    (country_id, country_name, country_known_name, country_iso_cd, continent_id,
     country_active, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT country_id, country_name, Country_Known_Name, Country_ISO_Cd, Continent_Id,
       country_active, cr_user_id, cr_dt, mod_user_id, Mod_Dt
FROM Seros_Data.Mst_Country;
ALTER TABLE serosIT.mst_country AUTO_INCREMENT = 244;

INSERT INTO serosIT.mst_country_state
    (country_state_id, country_id, country_state_name, country_state_abrv,
     country_state_active, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT country_state_id, country_id, country_state_name, country_state_abrv,
       country_state_active, cr_user_id, cr_dt, mod_user_id, mod_dt
FROM Seros_Data.Mst_Country_State;
ALTER TABLE serosIT.mst_country_state AUTO_INCREMENT = 103;

INSERT INTO serosIT.mst_vessel_dept
    (vessel_dept_id, vessel_dept_name, vessel_dept_order, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT vessel_dept_id, vessel_dept_name, vessel_dept_order, cr_user_id, cr_dt, mod_user_id, mod_dt
FROM Seros_Data.Mst_Vessel_Dept;
ALTER TABLE serosIT.mst_vessel_dept AUTO_INCREMENT = 11;

SELECT COUNT(*) FROM serosIT.mst_continent;
SELECT COUNT(*) FROM serosIT.mst_country;
SELECT COUNT(*) FROM serosIT.mst_country_state;
SELECT COUNT(*) FROM serosIT.mst_vessel_dept;
