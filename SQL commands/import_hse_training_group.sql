-- Populates Training Group (header + rank rows) and the category-to-rank
-- mapping the rank picker reads, from the legacy tables. Verified before
-- writing: every rank, category and vessel dept id already exists here with
-- the same id, no orphaned rank rows. Kept as-is on purpose: rank 127 repeats
-- inside groups 1, 2 and 5, one rank row has a blank Mandatory flag, and the
-- mapping repeats rank 127 under categories 4 and 5.
INSERT INTO serosIT.hse_training_group_hdr
    (training_group_hdr_id, training_group_hdr_name, training_group_hdr_active, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT Training_Group_Hdr_Id, Training_Group_Hdr_Name, Training_Group_Hdr_Active, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_HSE_Training_Group_Hdr;
ALTER TABLE serosIT.hse_training_group_hdr AUTO_INCREMENT = 11;

INSERT INTO serosIT.hse_training_group_dtl
    (training_group_dtl_id, training_group_hdr_id, fs_category_id, rank_id, mandatory_training, training_group_dtl_active,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT Training_Group_Dtl_Id, Training_Group_Hdr_Id, Fs_Category_Id, Rank_Id, Mandatory_Training, Training_Group_Dtl_Active,
       Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_HSE_Training_Group_Dtl;
ALTER TABLE serosIT.hse_training_group_dtl AUTO_INCREMENT = 75;

-- Nothing refers to a mapping row by id (and the legacy table repeats id 116),
-- so these take fresh ids, in legacy id order.
INSERT INTO serosIT.fs_catg_to_rank_mapping
    (fs_category_id, vessel_dept_id, rank_id, rank_order, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT Fs_Category_Id, Vessel_Dept_Id, Rank_Id, Rank_Order, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.Fs_Catg_To_Rank_Mapping
ORDER BY Fs_Catg_To_Rank_Mapping_Id;

SELECT (SELECT COUNT(*) FROM serosIT.hse_training_group_hdr) AS groups_,
       (SELECT COUNT(*) FROM serosIT.hse_training_group_dtl) AS ranks_,
       (SELECT COUNT(*) FROM serosIT.fs_catg_to_rank_mapping) AS mappings;
