INSERT INTO serosIT.mst_emp_nature
    (emp_nature_id, emp_nature_name, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT emp_nature_id, emp_nature_name, cr_user_id, cr_dt, mod_user_id, mod_dt
FROM Seros_Data.Mst_Emp_Nature;
ALTER TABLE serosIT.mst_emp_nature AUTO_INCREMENT = 4;

INSERT INTO serosIT.mst_emp_type
    (emp_type_id, emp_nature_id, emp_type_name, currency_id, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT emp_type_id, emp_nature_id, emp_type_name, Currency_Id, cr_user_id, cr_dt, mod_user_id, mod_dt
FROM Seros_Data.Mst_Emp_Type;
ALTER TABLE serosIT.mst_emp_type AUTO_INCREMENT = 26;

INSERT INTO serosIT.nationality_to_emp_type_mapping
    (nat_to_emp_type_map_id, fs_category_id, nationality, emp_type_id, active,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT Nat_To_Emp_Type_Map_Id, Fs_Category_Id, Nationality, Emp_Type_Id, Active,
       Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Nationality_To_Emp_Type_Mapping;
ALTER TABLE serosIT.nationality_to_emp_type_mapping AUTO_INCREMENT = 6;

SELECT COUNT(*) FROM serosIT.mst_emp_nature;
SELECT COUNT(*) FROM serosIT.mst_emp_type;
SELECT COUNT(*) FROM serosIT.nationality_to_emp_type_mapping;
