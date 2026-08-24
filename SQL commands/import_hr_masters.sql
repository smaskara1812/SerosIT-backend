-- Import the "HR" masters group. Competency + Fs_Category + Rank now;
-- Travel Eligibility / Reporting Structure / Job Descriptions still deferred.

SET SQL_SAFE_UPDATES = 0;
DELETE FROM serosIT.mst_rank;
DELETE FROM serosIT.mst_fs_category;
DELETE FROM serosIT.mst_competency;
SET SQL_SAFE_UPDATES = 1;

INSERT INTO serosIT.mst_competency
    (competency_id, competency_name, dept_id, active, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Competency_Id, Competency_Name, Dept_Id, Active, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Mst_Competency;

INSERT INTO serosIT.mst_fs_category
    (fs_category_id, fs_category_name, business_system_id_2, business_system_id_5,
     business_system_id_6, business_system_id_11, business_system_id_16,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    fs_category_id, fs_category_name, Business_System_Id_2, Business_System_Id_5,
    Business_System_Id_6, Business_System_Id_11, Business_System_Id_16,
    cr_user_id, cr_dt, mod_user_id, mod_dt
FROM Seros_Data.Mst_Fs_Category;

INSERT INTO serosIT.mst_rank
    (rank_id, fs_category_id, vessel_dept_id, rank_name, rank_abrv, rank_order,
     business_system_id_2, business_system_id_5, business_system_id_6, business_system_id_11,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    rank_id, fs_category_id, vessel_dept_id, rank_name, rank_abrv, rank_order,
    Business_System_Id_2, Business_System_Id_5, Business_System_Id_6, Business_System_Id_11,
    cr_user_id, cr_dt, mod_user_id, mod_dt
FROM Seros_Data.Mst_Rank;

SET @s = (SELECT CONCAT('ALTER TABLE serosIT.mst_competency AUTO_INCREMENT = ', MAX(competency_id) + 1) FROM serosIT.mst_competency);
PREPARE stmt FROM @s; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @s = (SELECT CONCAT('ALTER TABLE serosIT.mst_fs_category AUTO_INCREMENT = ', MAX(fs_category_id) + 1) FROM serosIT.mst_fs_category);
PREPARE stmt FROM @s; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @s = (SELECT CONCAT('ALTER TABLE serosIT.mst_rank AUTO_INCREMENT = ', MAX(rank_id) + 1) FROM serosIT.mst_rank);
PREPARE stmt FROM @s; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SELECT 'mst_competency' AS t, COUNT(*) FROM serosIT.mst_competency
UNION ALL SELECT 'mst_fs_category', COUNT(*) FROM serosIT.mst_fs_category
UNION ALL SELECT 'mst_rank', COUNT(*) FROM serosIT.mst_rank;
