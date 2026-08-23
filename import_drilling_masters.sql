INSERT INTO serosIT.mst_drilling_operation
    (drilling_ops_id, drilling_ops_code_no, drilling_ops_name,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Drilling_Ops_Id, Drilling_Ops_Code_No, Drilling_Ops_Name,
    Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Mst_Drilling_Operations;

INSERT INTO serosIT.mst_drilling_section
    (drilling_section_id, drilling_section_name,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Drilling_Section_Id, Drilling_Section_Name,
    Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Mst_Drilling_Section;

SELECT 'mst_drilling_operation' t, COUNT(*) n FROM serosIT.mst_drilling_operation
UNION ALL SELECT 'mst_drilling_section', COUNT(*) FROM serosIT.mst_drilling_section;
