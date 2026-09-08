-- Populates mst_cert from the legacy Mst_Cert table — a brand-new table in
-- this app, no prior import_*.sql this rides along with.
-- Requires mst_cert_type already populated (see import_cert_type.sql).

INSERT INTO serosIT.mst_cert
    (cert_id, cert_type_id, cert_name, cert_abrv, vessel_dept_id,
     cert_training_type, business_system_id_2, business_system_id_6,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    cert_id,
    cert_type_id,
    cert_name,
    cert_abrv,
    vessel_dept_id,
    Cert_Training_Type,
    Business_System_Id_2,
    Business_System_Id_6,
    cr_user_id,
    cr_dt,
    mod_user_id,
    mod_dt
FROM Seros_Data.Mst_Cert;
