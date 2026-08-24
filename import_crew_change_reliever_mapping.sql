INSERT INTO serosIT.crew_change_reliever_mapping
    (cc_reliever_mapping_id, fs_category_id, rank_id, reliever_rank_id, active,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT CC_Reliever_Mapping_Id, Fs_Category_Id, Rank_Id, Reliever_Rank_Id, Active,
       Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Crew_Change_Reliever_Mapping;

ALTER TABLE serosIT.crew_change_reliever_mapping AUTO_INCREMENT = 8;

SELECT COUNT(*) FROM serosIT.crew_change_reliever_mapping;
