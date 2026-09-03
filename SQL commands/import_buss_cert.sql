-- Populates mst_buss_cert from the legacy Mst_Buss_Cert table — a
-- brand-new table in this app, no prior import_*.sql this rides along with.
-- Requires mst_buss_cert_type already populated (see import_buss_cert_type.sql).

INSERT INTO serosIT.mst_buss_cert
    (buss_cert_id, buss_cert_name, buss_cert_type_id, buss_cert_validity,
     business_system_id_2, business_system_id_5, business_system_id_6,
     business_system_id_7, business_system_id_8, business_system_id_9,
     business_system_id_11, buss_cert_active,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Buss_Cert_Id,
    Buss_Cert_Name,
    Buss_Cert_Type_Id,
    Buss_Cert_Validity,
    Business_System_Id_2,
    Business_System_Id_5,
    Business_System_Id_6,
    Business_System_Id_7,
    Business_System_Id_8,
    Business_System_Id_9,
    Business_System_Id_11,
    Buss_Cert_Active,
    Cr_User_Id,
    Cr_Dt,
    Mod_User_Id,
    Mod_Dt
FROM Seros_Data.Mst_Buss_Cert;
