-- Populates the FS (field staff) employee master and each person's current
-- status from the legacy eos_Mst_Fs_Employee / eos_Fs_Emp_Cur_Status tables.
-- Verified before writing: every category, rank, employee type, rig, service,
-- nationality (a country id), qualification, country, state and location id
-- already exists here with the same id (26 people have no rig, in both
-- tables). The whole legacy row is copied, including identity and travel
-- document numbers. Legacy ids are kept (they are not the same people as
-- mst_employee).
INSERT INTO serosIT.mst_fs_employee
    (fs_emp_id, fs_emp_fname, fs_emp_mname, fs_emp_lname, permanent_addr, mailing_addr, emergency_addr,
     fs_emp_tel_no, fs_emp_mobile_no, fs_emp_email_pers, fs_emp_email_official, gender, blood_group, fs_emp_dob,
     fs_emp_pob, marital_status, marriage_dt, nationality_id, home_town_id, domicile_state_id, religion,
     qualification_id, pan_no, aadhaar_no, area_of_interest, fs_emp_photo_path, pp_no, pp_dt, pp_country_id,
     pin_code, pp_place_id, pp_valid_till, pp_ecnr, pp_name, cdc_no, cdc_dt, cdc_country_id, cdc_place_id,
     cdc_valid_till, fs_emp_staff_id, fs_emp_doj, hire_dt, fs_category_id, rank_id, rank_to_grade_id, emp_type_id,
     rig_id, dms_path_resume, key_personnel, vfd_rig_exp, scr_rig_exp, hpht_exp, erd_exp, nov_exp, canrig_exp,
     fs_emp_dol, off_hire_dt, fs_emp_temporary, fs_emp_active, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT Fs_Emp_Id, Fs_Emp_Fname, Fs_Emp_Mname, Fs_Emp_Lname, Permanent_Addr, Mailing_Addr, Emergency_Addr,
       Fs_Emp_Tel_No, Fs_Emp_Mobile_No, Fs_Emp_Email_Pers, Fs_Emp_Email_Official, Gender, Blood_Group, Fs_Emp_Dob,
       Fs_Emp_Pob, Marital_Status, Marriage_Dt, Nationality_Id, Home_Town_Id, Domicile_State_Id, Religion,
       Qualification_Id, PAN_No, Aadhaar_No, Area_Of_Interest, Fs_Emp_Photo_Path, PP_No, PP_Dt, PP_Country_Id,
       PIN_Code, PP_Place_Id, PP_Valid_Till, PP_Ecnr, PP_Name, CDC_No, CDC_Dt, CDC_Country_Id, CDC_Place_Id,
       CDC_Valid_Till, Fs_Emp_Staff_Id, Fs_Emp_Doj, Hire_Dt, Fs_Category_Id, Rank_Id, Rank_To_Grade_Id, Emp_Type_Id,
       Rig_Id, DMS_Path_Resume, Key_Personnel, VFD_Rig_Exp, SCR_Rig_Exp, HPHT_Exp, ERD_Exp, NOV_Exp, Canrig_Exp,
       Fs_Emp_Dol, Off_Hire_Dt, Fs_Emp_Temporary, Fs_Emp_Active, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Mst_Fs_Employee;
ALTER TABLE serosIT.mst_fs_employee AUTO_INCREMENT = 3302;

INSERT INTO serosIT.fs_emp_cur_status
    (fs_emp_id, fs_category_id, rank_id, emp_type_id, serv_type_id, serv_subtype_id, serv_subtype_from, appx_end_dt,
     rig_id, crew_shift, cur_rank_from, wage_process_dt, fs_emp_active, fs_emp_dol, mod_user_id, mod_dt)
SELECT Fs_Emp_Id, Fs_Category_Id, Rank_Id, Emp_Type_Id, Serv_Type_Id, Serv_Subtype_Id, Serv_Subtype_From, Appx_End_Dt,
       Rig_Id, Crew_Shift, Cur_Rank_From, Wage_Process_Dt, Fs_Emp_Active, Fs_Emp_Dol, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Fs_Emp_Cur_Status;

SELECT (SELECT COUNT(*) FROM serosIT.mst_fs_employee) AS staff, (SELECT COUNT(*) FROM serosIT.fs_emp_cur_status) AS statuses;
