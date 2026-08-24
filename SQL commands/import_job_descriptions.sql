-- Import Job Descriptions (header + detail), depends on mst_rank and
-- mst_fs_category already being imported.

SET SQL_SAFE_UPDATES = 0;
DELETE FROM serosIT.job_description_dtl;
DELETE FROM serosIT.job_description_hdr;
SET SQL_SAFE_UPDATES = 1;

INSERT INTO serosIT.job_description_hdr
    (jd_hdr_id, fs_category_id, rank_id, jd_hdr_description, jd_hdr_order, jd_hdr_active,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    JD_Hdr_Id, Fs_Category_Id, Rank_Id, JD_Hdr_Description, JD_Hdr_Order, JD_Hdr_Active,
    Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Job_Description_Hdr;

INSERT INTO serosIT.job_description_dtl
    (jd_dtl_id, jd_hdr_id, jd_dtl_description, jd_dtl_order, jd_dtl_active,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    JD_Dtl_Id, JD_Hdr_Id, JD_Dtl_Description, JD_Dtl_Order, JD_Dtl_Active,
    Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Job_Description_Dtl;

SET @s = (SELECT CONCAT('ALTER TABLE serosIT.job_description_hdr AUTO_INCREMENT = ', MAX(jd_hdr_id) + 1) FROM serosIT.job_description_hdr);
PREPARE stmt FROM @s; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @s = (SELECT CONCAT('ALTER TABLE serosIT.job_description_dtl AUTO_INCREMENT = ', MAX(jd_dtl_id) + 1) FROM serosIT.job_description_dtl);
PREPARE stmt FROM @s; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SELECT 'job_description_hdr' AS t, COUNT(*) FROM serosIT.job_description_hdr
UNION ALL SELECT 'job_description_dtl', COUNT(*) FROM serosIT.job_description_dtl;
