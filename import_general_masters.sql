-- Import the "General" masters group from the legacy ops-data DB into
-- SerosIT, preserving legacy PKs. Order matters: mst_cost_centre references
-- mst_rig and mst_cost_centre_type, so it has to import last.

SET SQL_SAFE_UPDATES = 0;
DELETE FROM serosIT.mst_cost_centre;
DELETE FROM serosIT.mst_cost_centre_type;
DELETE FROM serosIT.mst_contractor;
DELETE FROM serosIT.mst_cert_institute;
DELETE FROM serosIT.mst_email_notification_type;
DELETE FROM serosIT.mst_operator;
DELETE FROM serosIT.mst_rig;
SET SQL_SAFE_UPDATES = 1;

INSERT INTO serosIT.mst_cost_centre_type
    (cost_centre_type_id, cost_centre_type_name, cost_centre_type_shortname,
     cost_centre_type_active, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Cost_Centre_Type_Id, Cost_Centre_Type_Name, Cost_Centre_Type_Shortname,
    Cost_Centre_Type_Active, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Mst_Cost_Centre_Type;

INSERT INTO serosIT.mst_contractor
    (contractor_id, contractor_name, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Contractor_Id, Contractor_Name, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Mst_Contractor;

INSERT INTO serosIT.mst_cert_institute
    (cert_institute_id, cert_institute_name, cert_institute_shortname,
     cert_institute_address, location_id, tel_no, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Cert_Institute_Id, Cert_Institute_Name, Cert_Institute_Shortname,
    Cert_Institute_Address, Location_Id, Tel_No, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Mst_Cert_Institute;

INSERT INTO serosIT.mst_email_notification_type
    (en_type_id, en_type_name, en_type_subject, en_description, en_type_active,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    EN_Type_Id, EN_Type_Name, EN_Type_Subject, EN_Description, EN_Type_Active,
    Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Email_Notification_Type;

INSERT INTO serosIT.mst_operator
    (operator_id, operator_name, operator_short_name, operator_sap_code, wbs_client_code,
     location_id, country_id, contact_person, tel_no, email_id, operator_active,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Operator_Id, Operator_Name, Operator_Short_Name, Operator_SAP_Code, WBS_Client_Code,
    Location_Id, Country_Id, Contact_Person, Tel_No, Email_Id, Operator_Active,
    Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Mst_Operator;

INSERT INTO serosIT.mst_rig
    (rig_id, rig_name, rig_short_name, old_rig_name, rig_subtype_id, rig_type_id,
     rig_built_dt, rig_tel_no, rig_fax_no, rig_email_id, personnel_area, org_unit_code,
     rig_from, rig_to, rig_active, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Rig_Id, Rig_Name, Rig_Short_Name, Old_Rig_Name, Rig_Subtype_Id, Rig_Type_Id,
    Rig_Built_Dt, Rig_Tel_No, Rig_Fax_No, Rig_Email_Id, Personnel_Area, Org_Unit_Code,
    Rig_From, Rig_To, Rig_Active, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Mst_Rig;

-- One legacy row (Cost_Centre_Id 28, "W  R02") points at Rig_Id 100, which
-- doesn't exist in eos_Mst_Rig — a dangling reference legacy never enforced
-- via FK. Null it out here rather than fail the import or fabricate a rig.
INSERT INTO serosIT.mst_cost_centre
    (cost_centre_id, cost_centre_type_id, cost_centre_name, old_cost_centre_name, rig_id,
     fs_emp_id, location_id, cost_centre_active, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    cc.Cost_Centre_Id, cct.Cost_Centre_Type_Id, cc.Cost_Centre_Name, cc.Old_Cost_Centre_Name,
    r.Rig_Id, cc.Fs_Emp_Id, cc.Location_Id, cc.Cost_Centre_Active, cc.Cr_User_Id, cc.Cr_Dt,
    cc.Mod_User_Id, cc.Mod_Dt
FROM Seros_Data.eos_Mst_Cost_Centre cc
LEFT JOIN Seros_Data.eos_Mst_Cost_Centre_Type cct ON cct.Cost_Centre_Type_Id = cc.Cost_Centre_Type_Id
LEFT JOIN Seros_Data.eos_Mst_Rig r ON r.Rig_Id = cc.Rig_Id;

-- Reseed AUTO_INCREMENT past the max imported id on each table.
SET @s = (SELECT CONCAT('ALTER TABLE serosIT.mst_cost_centre_type AUTO_INCREMENT = ', MAX(cost_centre_type_id) + 1) FROM serosIT.mst_cost_centre_type);
PREPARE stmt FROM @s; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @s = (SELECT CONCAT('ALTER TABLE serosIT.mst_contractor AUTO_INCREMENT = ', MAX(contractor_id) + 1) FROM serosIT.mst_contractor);
PREPARE stmt FROM @s; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @s = (SELECT CONCAT('ALTER TABLE serosIT.mst_cert_institute AUTO_INCREMENT = ', MAX(cert_institute_id) + 1) FROM serosIT.mst_cert_institute);
PREPARE stmt FROM @s; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @s = (SELECT CONCAT('ALTER TABLE serosIT.mst_email_notification_type AUTO_INCREMENT = ', MAX(en_type_id) + 1) FROM serosIT.mst_email_notification_type);
PREPARE stmt FROM @s; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @s = (SELECT CONCAT('ALTER TABLE serosIT.mst_operator AUTO_INCREMENT = ', MAX(operator_id) + 1) FROM serosIT.mst_operator);
PREPARE stmt FROM @s; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @s = (SELECT CONCAT('ALTER TABLE serosIT.mst_rig AUTO_INCREMENT = ', MAX(rig_id) + 1) FROM serosIT.mst_rig);
PREPARE stmt FROM @s; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @s = (SELECT CONCAT('ALTER TABLE serosIT.mst_cost_centre AUTO_INCREMENT = ', MAX(cost_centre_id) + 1) FROM serosIT.mst_cost_centre);
PREPARE stmt FROM @s; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SELECT 'mst_cost_centre_type' AS t, COUNT(*) FROM serosIT.mst_cost_centre_type
UNION ALL SELECT 'mst_contractor', COUNT(*) FROM serosIT.mst_contractor
UNION ALL SELECT 'mst_cert_institute', COUNT(*) FROM serosIT.mst_cert_institute
UNION ALL SELECT 'mst_email_notification_type', COUNT(*) FROM serosIT.mst_email_notification_type
UNION ALL SELECT 'mst_operator', COUNT(*) FROM serosIT.mst_operator
UNION ALL SELECT 'mst_rig', COUNT(*) FROM serosIT.mst_rig
UNION ALL SELECT 'mst_cost_centre', COUNT(*) FROM serosIT.mst_cost_centre;
