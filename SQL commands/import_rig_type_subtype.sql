INSERT INTO serosIT.mst_rig_type
    (rig_type_id, rig_type_name, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT Rig_Type_Id, Rig_Type_Name, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.Mst_Rig_Type;

ALTER TABLE serosIT.mst_rig_type AUTO_INCREMENT = 6;

INSERT INTO serosIT.mst_rig_subtype
    (rig_subtype_id, rig_subtype_name, rig_type_id, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT Rig_Subtype_Id, Rig_Subtype_Name, Rig_Type_Id, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.Mst_Rig_Subtype;

ALTER TABLE serosIT.mst_rig_subtype AUTO_INCREMENT = 10;

SELECT COUNT(*) FROM serosIT.mst_rig_type;
SELECT COUNT(*) FROM serosIT.mst_rig_subtype;
