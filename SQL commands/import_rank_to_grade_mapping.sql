INSERT INTO serosIT.mst_grade
    (grade_id, grade_name, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT Grade_Id, Grade_Name, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Mst_Grade;
ALTER TABLE serosIT.mst_grade AUTO_INCREMENT = 2;

INSERT INTO serosIT.rank_to_grade_mapping
    (rank_to_grade_id, rank_id, grade_id, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT Rank_To_Grade_Id, Rank_Id, Grade_Id, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Rank_To_Grade_Mapping;
ALTER TABLE serosIT.rank_to_grade_mapping AUTO_INCREMENT = 2;

SELECT * FROM serosIT.mst_grade;
SELECT * FROM serosIT.rank_to_grade_mapping;
