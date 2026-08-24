INSERT INTO serosIT.fs_catg_to_rig_type_mapping
    (fs_catg_to_rig_type_mapping_id, fs_category_id, rig_type_id, mapping_active,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Fs_Catg_To_Rig_Type_Mapping_Id, Fs_Category_Id, Rig_Type_Id,
    IF(Mapping_Active = 'Y', 'Y', 'N'),
    Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Fs_Catg_To_Rig_Type_Mapping;

ALTER TABLE serosIT.fs_catg_to_rig_type_mapping AUTO_INCREMENT = 7;

SELECT * FROM serosIT.fs_catg_to_rig_type_mapping;
