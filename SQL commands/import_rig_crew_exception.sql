INSERT INTO serosIT.rig_crew_exception
    (rig_crew_exception_id, fs_category_id, emp_type_id, rank_id, fs_emp_id,
     exception_from, exception_to, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT Rig_Crew_Exception_Id, Fs_Category_Id, Emp_Type_Id, Rank_Id, Fs_Emp_Id,
       Exception_From, Exception_To, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Rig_Crew_Exceptions;

ALTER TABLE serosIT.rig_crew_exception AUTO_INCREMENT = 3;

SELECT COUNT(*) FROM serosIT.rig_crew_exception;
