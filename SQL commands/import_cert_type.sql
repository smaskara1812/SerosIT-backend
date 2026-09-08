-- Populates mst_cert_type from the legacy Mst_Cert_Type table — a
-- brand-new table in this app, no prior import_*.sql this rides along with.

INSERT INTO serosIT.mst_cert_type
    (cert_type_id, cert_type_name, cert_type_abrv,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    cert_type_id,
    cert_type_name,
    cert_type_abrv,
    cr_user_id,
    cr_dt,
    mod_user_id,
    mod_dt
FROM Seros_Data.Mst_Cert_Type;
