-- Populates mst_qualification from the legacy Mst_Qualification table — a
-- brand-new table in this app, no prior import_*.sql this rides along with.

INSERT INTO serosIT.mst_qualification
    (qualification_id, qualification_name, qualification_abrv, qualification_type,
     business_system_id_2, business_system_id_6,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Qualification_Id,
    Qualification_Name,
    Qualification_Abrv,
    Qualification_Type,
    Business_System_Id_2,
    Business_System_Id_6,
    Cr_User_Id,
    Cr_Dt,
    Mod_User_Id,
    Mod_Dt
FROM Seros_Data.Mst_Qualification;
