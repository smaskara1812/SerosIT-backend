-- Import Travel Eligibility. Depends on mst_rank / mst_fs_category already
-- being imported.

SET SQL_SAFE_UPDATES = 0;
DELETE FROM serosIT.travel_eligibility;
SET SQL_SAFE_UPDATES = 1;

INSERT INTO serosIT.travel_eligibility
    (travel_eligibility_id, fs_category_id, rank_id, travel_mode, travel_class,
     travel_preference, eligible_from, eligible_to, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Travel_Eligibility_Id, Fs_Category_Id, Rank_Id, Travel_Mode, Travel_Class,
    Travel_Preference, Eligible_From, Eligible_To, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Travel_Eligibility;

SET @s = (SELECT CONCAT('ALTER TABLE serosIT.travel_eligibility AUTO_INCREMENT = ', MAX(travel_eligibility_id) + 1) FROM serosIT.travel_eligibility);
PREPARE stmt FROM @s; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SELECT COUNT(*) AS imported_travel_eligibility FROM serosIT.travel_eligibility;
