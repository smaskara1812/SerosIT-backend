INSERT INTO serosIT.mst_it_application_type
    (it_appl_type_id, it_appl_type_name, max_resources, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT IT_Appl_Type_Id, IT_Appl_Type, Max_Resources, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.Mst_IT_Application_Type;
ALTER TABLE serosIT.mst_it_application_type AUTO_INCREMENT = 6;

INSERT INTO serosIT.mst_it_application_subtype
    (it_appl_subtype_id, it_appl_type_id, it_appl_subtype_name, max_resources, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT IT_Appl_Subtype_Id, IT_Appl_Type_Id, IT_Appl_Subtype, Max_Resources, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.it_Mst_IT_Application_Subtype;
ALTER TABLE serosIT.mst_it_application_subtype AUTO_INCREMENT = 63;

SELECT 'it_appl_type' t, COUNT(*) c FROM serosIT.mst_it_application_type
UNION ALL SELECT 'it_appl_subtype', COUNT(*) FROM serosIT.mst_it_application_subtype;
