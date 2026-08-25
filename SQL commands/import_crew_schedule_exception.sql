INSERT INTO serosIT.crew_schedule_exception
    (cs_exception_id, fs_category_id, emp_type_id, rank_id, fs_emp_id,
     exception_from, exception_to, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT CS_Exception_Id, Fs_Category_Id, Emp_Type_Id, Rank_Id, Fs_Emp_Id,
       Exception_From, Exception_To, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Crew_Schedule_Exceptions;

ALTER TABLE serosIT.crew_schedule_exception AUTO_INCREMENT = 36;

SELECT COUNT(*) FROM serosIT.crew_schedule_exception;
