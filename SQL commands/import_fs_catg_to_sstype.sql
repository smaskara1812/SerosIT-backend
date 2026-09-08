-- Populates mst_fs_catg_to_sstype from the legacy Mst_Fs_Catg_To_SSType
-- table — a brand-new table in this app, no prior import_*.sql this rides
-- along with. Requires mst_serv_type and mst_serv_subtype already populated
-- (see import_serv_type.sql / import_serv_subtype.sql).

INSERT INTO serosIT.mst_fs_catg_to_sstype
    (catg_sstype_id, fs_category_id, emp_type_id, serv_type_id, serv_subtype_id,
     business_system_id_2, business_system_id_5, business_system_id_6, business_system_id_11,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    catg_sstype_id,
    fs_category_id,
    emp_type_id,
    serv_type_id,
    serv_subtype_id,
    Business_System_Id_2,
    Business_System_Id_5,
    Business_System_Id_6,
    Business_System_Id_11,
    cr_user_id,
    cr_dt,
    mod_user_id,
    mod_dt
FROM Seros_Data.Mst_Fs_Catg_To_SSType;
