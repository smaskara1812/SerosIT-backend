-- Populates mst_serv_type from the legacy Mst_Serv_Type table — a
-- brand-new table in this app, no prior import_*.sql this rides along with.

INSERT INTO serosIT.mst_serv_type
    (serv_type_id, serv_type_name, serv_type_abrv,
     business_system_id_2, business_system_id_6,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    serv_type_id,
    serv_type_name,
    serv_type_abrv,
    Business_System_Id_2,
    Business_System_Id_6,
    cr_user_id,
    cr_dt,
    mod_user_id,
    mod_dt
FROM Seros_Data.Mst_Serv_Type;
