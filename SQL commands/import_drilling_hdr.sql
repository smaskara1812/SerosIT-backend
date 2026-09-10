-- Populates drilling_hdr from the legacy eos_Drilling_Hdr table — a
-- brand-new table in this app, no prior import_*.sql this rides along
-- with. Requires project_contract, mst_rig, and mst_drilling_rate already
-- populated.

INSERT INTO serosIT.drilling_hdr
    (drilling_hdr_id, prj_contract_id, rig_id, latitude, longitude, location,
     total_water_depth, total_depth, first_anchor_down_dt, distance_covered_kms_knots,
     drilling_rate_id, tot_consumption_diesel, tot_consumption_water, tot_received_diesel,
     tot_received_water, tot_generated_water, tot_operating_hrs, tot_standby_hrs,
     tot_repair_service_hrs, tot_repair_rate_hrs, tot_zero_rate_hrs, total_days,
     drilling_completion_dt, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Drilling_Hdr_Id,
    Prj_Contract_Id,
    Rig_Id,
    Latitude,
    Longitude,
    Location,
    Total_Water_Depth,
    Total_Depth,
    First_Anchor_Down_Dt,
    Distance_Covered_Kms_Knots,
    Drilling_Rate_Id,
    Tot_Consumption_Diesel,
    Tot_Consumption_Water,
    Tot_Received_Diesel,
    Tot_Received_Water,
    Tot_Generated_Water,
    Tot_Operating_Hrs,
    Tot_Standby_Hrs,
    Tot_Repair_Service_Hrs,
    Tot_Repair_Rate_Hrs,
    Tot_Zero_Rate_Hrs,
    Total_Days,
    Drilling_Completion_Dt,
    Cr_User_Id,
    Cr_Dt,
    Mod_User_Id,
    Mod_Dt
FROM Seros_Data.eos_Drilling_Hdr;
