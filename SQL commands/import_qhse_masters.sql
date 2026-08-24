-- Import QHSE masters. Indicator Subtype depends on Indicator Type.

SET SQL_SAFE_UPDATES = 0;
DELETE FROM serosIT.mst_indicator_subtype;
DELETE FROM serosIT.mst_indicator_type;
DELETE FROM serosIT.mst_rig_operation;
DELETE FROM serosIT.mst_contact_exposure_type;
DELETE FROM serosIT.mst_parts_of_body;
DELETE FROM serosIT.mst_qhse_category;
DELETE FROM serosIT.mst_hse_activity;
DELETE FROM serosIT.mst_hse_consumable;
DELETE FROM serosIT.mst_hazard_type;
SET SQL_SAFE_UPDATES = 1;

INSERT INTO serosIT.mst_rig_operation
    (rig_operation_id, rig_operation_name, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT Rig_Operation_Id, Rig_Operation_Name, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Mst_Rig_Operation;

INSERT INTO serosIT.mst_contact_exposure_type
    (contact_expo_type_id, contact_expo_type_name, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT Contact_Expo_Type_Id, Contact_Expo_Type_Name, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Mst_Contact_Exposure_Type;

INSERT INTO serosIT.mst_indicator_type
    (indicator_type_id, indicator_type_name, indicator_type_order, report_type, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT Indicator_Type_Id, Indicator_Type_Name, Indicator_Type_Order, Report_Type, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Mst_Indicator_Type;

INSERT INTO serosIT.mst_indicator_subtype
    (indicator_subtype_id, indicator_type_id, indicator_subtype_name, indicator_subtype_order, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT Indicator_Subtype_Id, Indicator_Type_Id, Indicator_Subtype_Name, Indicator_Subtype_Order, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Mst_Indicator_Subtype;

INSERT INTO serosIT.mst_parts_of_body
    (part_of_body_id, part_of_body_name, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT Part_Of_Body_Id, Part_Of_Body_Name, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Mst_Parts_Of_Body;

INSERT INTO serosIT.mst_qhse_category
    (qhse_category_id, qhse_category_name, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT QHSE_Category_Id, QHSE_Category_Name, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Mst_QHSE_Category;

INSERT INTO serosIT.mst_hse_activity
    (hse_activity_id, hse_activity_name, hse_activity_type, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT HSE_Activity_Id, HSE_Activity_Name, HSE_Activity_Type, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Mst_HSE_Activity;

INSERT INTO serosIT.mst_hse_consumable
    (hse_consumable_id, hse_consumable_name, hse_consumption_unit, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT HSE_Consumable_Id, HSE_Consumable_Name, HSE_Consumption_Unit, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Mst_HSE_Consumable;

INSERT INTO serosIT.mst_hazard_type
    (haz_type_id, haz_type_name, haz_type_class, haz_type_active, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT Haz_Type_Id, Haz_Type_Name, Haz_Type_Class, Haz_Type_Active, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Mst_Hazard_Type;

-- Reseed AUTO_INCREMENT on every table above.
SET @s = (SELECT CONCAT('ALTER TABLE serosIT.mst_rig_operation AUTO_INCREMENT = ', MAX(rig_operation_id) + 1) FROM serosIT.mst_rig_operation);
PREPARE stmt FROM @s; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @s = (SELECT CONCAT('ALTER TABLE serosIT.mst_contact_exposure_type AUTO_INCREMENT = ', MAX(contact_expo_type_id) + 1) FROM serosIT.mst_contact_exposure_type);
PREPARE stmt FROM @s; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @s = (SELECT CONCAT('ALTER TABLE serosIT.mst_indicator_type AUTO_INCREMENT = ', MAX(indicator_type_id) + 1) FROM serosIT.mst_indicator_type);
PREPARE stmt FROM @s; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @s = (SELECT CONCAT('ALTER TABLE serosIT.mst_indicator_subtype AUTO_INCREMENT = ', MAX(indicator_subtype_id) + 1) FROM serosIT.mst_indicator_subtype);
PREPARE stmt FROM @s; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @s = (SELECT CONCAT('ALTER TABLE serosIT.mst_parts_of_body AUTO_INCREMENT = ', MAX(part_of_body_id) + 1) FROM serosIT.mst_parts_of_body);
PREPARE stmt FROM @s; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @s = (SELECT CONCAT('ALTER TABLE serosIT.mst_qhse_category AUTO_INCREMENT = ', MAX(qhse_category_id) + 1) FROM serosIT.mst_qhse_category);
PREPARE stmt FROM @s; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @s = (SELECT CONCAT('ALTER TABLE serosIT.mst_hse_activity AUTO_INCREMENT = ', MAX(hse_activity_id) + 1) FROM serosIT.mst_hse_activity);
PREPARE stmt FROM @s; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @s = (SELECT CONCAT('ALTER TABLE serosIT.mst_hse_consumable AUTO_INCREMENT = ', MAX(hse_consumable_id) + 1) FROM serosIT.mst_hse_consumable);
PREPARE stmt FROM @s; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @s = (SELECT CONCAT('ALTER TABLE serosIT.mst_hazard_type AUTO_INCREMENT = ', MAX(haz_type_id) + 1) FROM serosIT.mst_hazard_type);
PREPARE stmt FROM @s; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SELECT 'rig_operation' t, COUNT(*) FROM serosIT.mst_rig_operation
UNION ALL SELECT 'contact_exposure_type', COUNT(*) FROM serosIT.mst_contact_exposure_type
UNION ALL SELECT 'indicator_type', COUNT(*) FROM serosIT.mst_indicator_type
UNION ALL SELECT 'indicator_subtype', COUNT(*) FROM serosIT.mst_indicator_subtype
UNION ALL SELECT 'parts_of_body', COUNT(*) FROM serosIT.mst_parts_of_body
UNION ALL SELECT 'qhse_category', COUNT(*) FROM serosIT.mst_qhse_category
UNION ALL SELECT 'hse_activity', COUNT(*) FROM serosIT.mst_hse_activity
UNION ALL SELECT 'hse_consumable', COUNT(*) FROM serosIT.mst_hse_consumable
UNION ALL SELECT 'hazard_type', COUNT(*) FROM serosIT.mst_hazard_type;
