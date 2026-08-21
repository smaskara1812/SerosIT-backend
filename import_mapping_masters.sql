-- Import Mapping masters. Doc_To_Sign_Mapping depends on mst_employee.

SET SQL_SAFE_UPDATES = 0;
DELETE FROM serosIT.mst_interviewer;
DELETE FROM serosIT.doc_to_sign_mapping;
DELETE FROM serosIT.user_fs_catg_mapping;
DELETE FROM serosIT.user_rig_mapping;
DELETE FROM serosIT.mst_employee;
SET SQL_SAFE_UPDATES = 1;

INSERT INTO serosIT.mst_employee (emp_id, emp_fname, emp_mname, emp_sname, emp_active)
SELECT EMP_ID, NULLIF(Emp_Fname, ''), NULLIF(Emp_Mname, ''), Emp_Sname, EMP_ACTIVE
FROM Seros_Data.Mst_Employee;

INSERT INTO serosIT.user_rig_mapping
    (user_rig_mapping_id, user_id, rig_id, mapping_from, mapping_to, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT User_Rig_Mapping_Id, User_Id, Rig_Id, User_Rig_Mapping_From, User_Rig_Mapping_To, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Mst_User_Rig_Mapping;

INSERT INTO serosIT.user_fs_catg_mapping
    (user_fs_catg_mapping_id, user_id, fs_category_id, mapping_from, mapping_to, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT User_Fs_Catg_Mapping_Id, User_Id, Fs_Category_Id, User_Fs_Catg_Mapping_From, User_Fs_Catg_Mapping_To, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Mst_User_Fs_Catg_Mapping;

INSERT INTO serosIT.doc_to_sign_mapping
    (doc_to_sign_id, doc_name, emp_id, sign_path, sign_from, sign_to, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT Doc_To_Sign_Id, Doc_Name, Emp_Id, Sign_Path, Sign_From, Sign_To, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Doc_To_Sign_Mapping;

INSERT INTO serosIT.mst_interviewer
    (interviewer_id, user_id, dept_id, sign_path, active, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT Interviewer_Id, User_Id, Dept_Id, NULL, Active, Cr_User_Id, COALESCE(Cr_Dt, NOW()), Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Mst_Interviewer;

-- Reseed AUTO_INCREMENT on every table above (mst_employee's PK is a plain
-- non-auto field, so it's excluded).
SET @s = (SELECT CONCAT('ALTER TABLE serosIT.user_rig_mapping AUTO_INCREMENT = ', MAX(user_rig_mapping_id) + 1) FROM serosIT.user_rig_mapping);
PREPARE stmt FROM @s; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @s = (SELECT CONCAT('ALTER TABLE serosIT.user_fs_catg_mapping AUTO_INCREMENT = ', MAX(user_fs_catg_mapping_id) + 1) FROM serosIT.user_fs_catg_mapping);
PREPARE stmt FROM @s; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @s = (SELECT CONCAT('ALTER TABLE serosIT.doc_to_sign_mapping AUTO_INCREMENT = ', MAX(doc_to_sign_id) + 1) FROM serosIT.doc_to_sign_mapping);
PREPARE stmt FROM @s; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @s = (SELECT CONCAT('ALTER TABLE serosIT.mst_interviewer AUTO_INCREMENT = ', MAX(interviewer_id) + 1) FROM serosIT.mst_interviewer);
PREPARE stmt FROM @s; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SELECT 'mst_employee' t, COUNT(*) FROM serosIT.mst_employee
UNION ALL SELECT 'user_rig_mapping', COUNT(*) FROM serosIT.user_rig_mapping
UNION ALL SELECT 'user_fs_catg_mapping', COUNT(*) FROM serosIT.user_fs_catg_mapping
UNION ALL SELECT 'doc_to_sign_mapping', COUNT(*) FROM serosIT.doc_to_sign_mapping
UNION ALL SELECT 'mst_interviewer', COUNT(*) FROM serosIT.mst_interviewer;
