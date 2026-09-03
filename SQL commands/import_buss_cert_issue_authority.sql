-- Populates mst_buss_cert_issue_authority from the legacy
-- Mst_Buss_Cert_Issue_Authority table — a brand-new table in this app (no
-- prior masters group covered it), so there's no earlier import_*.sql this
-- rides along with.

INSERT INTO serosIT.mst_buss_cert_issue_authority
    (buss_cert_issue_auth_id, buss_cert_issue_authority, buss_cert_issue_abrv,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Buss_Cert_Issue_Auth_Id,
    Buss_Cert_Issue_Authority,
    Buss_Cert_Issue_Abrv,
    Cr_User_Id,
    Cr_Dt,
    Mod_User_Id,
    Mod_Dt
FROM Seros_Data.Mst_Buss_Cert_Issue_Authority;
