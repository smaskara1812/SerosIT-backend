-- Populates mst_buss_cert_type from the legacy Mst_Buss_Cert_Type table —
-- a brand-new table in this app, no prior import_*.sql this rides along with.

INSERT INTO serosIT.mst_buss_cert_type
    (buss_cert_type_id, buss_cert_type, buss_cert_type_abrv,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Buss_Cert_Type_Id,
    Buss_Cert_Type,
    Buss_Cert_Type_Abrv,
    Cr_User_Id,
    Cr_Dt,
    Mod_User_Id,
    Mod_Dt
FROM Seros_Data.Mst_Buss_Cert_Type;
