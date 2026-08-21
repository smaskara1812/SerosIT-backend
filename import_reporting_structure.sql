-- Import Reporting Structure. Depends on mst_rank / mst_fs_category.

SET SQL_SAFE_UPDATES = 0;
DELETE FROM serosIT.reporting_structure;
SET SQL_SAFE_UPDATES = 1;

INSERT INTO serosIT.reporting_structure
    (reporting_structure_id, fs_category_id, rank_id, reporting_rank_id,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Reporting_Structure_Id, Fs_Category_Id, Rank_Id, Reporting_Rank_Id,
    Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Reporting_Structure;

SET @s = (SELECT CONCAT('ALTER TABLE serosIT.reporting_structure AUTO_INCREMENT = ', MAX(reporting_structure_id) + 1) FROM serosIT.reporting_structure);
PREPARE stmt FROM @s; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SELECT COUNT(*) AS imported_reporting_structure FROM serosIT.reporting_structure;
