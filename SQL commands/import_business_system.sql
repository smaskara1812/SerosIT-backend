-- Populates mst_business_system from the legacy Mst_Business_System table
-- — a brand-new table in this app, no prior import_*.sql this rides along
-- with. Note: Mail_User_Password is carried over as-is (plaintext in the
-- legacy source already), not a new exposure introduced by this import.

INSERT INTO serosIT.mst_business_system
    (business_system_id, buss_system_dtl, buss_system_abrv, buss_system_schema_name,
     mail_from_address, mail_user_name, mail_user_password, owner_emp_id,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Business_System_id,
    Buss_System_Dtl,
    Buss_System_Abrv,
    Buss_System_Schema_Name,
    Mail_From_Address,
    Mail_User_Name,
    Mail_User_Password,
    Owner_Emp_Id,
    Cr_User_Id,
    Cr_Dt,
    Mod_User_Id,
    Mod_Dt
FROM Seros_Data.Mst_Business_System;
