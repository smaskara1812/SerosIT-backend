-- Populates Training Log (sessions + trainees) from the legacy
-- eos_HSE_Training_Log_* tables. Verified before writing: every rig,
-- certificate, training org, trainer, employee and category id exists here
-- with the same id, and each trainer belongs to the org on its log.
-- Cleaned on the way in (confirmed): the three blank "Certificate Issued"
-- flags and one blank "Assessment Conducted" flag become 'N', and the
-- placeholder certificate paths ("N/Images/Training_Cert/…", no real file)
-- become empty. The old company name "EOSIL" on trainee rows (party and company) is
-- shown as "Seros" — on this page only.
INSERT INTO serosIT.hse_training_log_hdr
    (training_log_hdr_id, rig_id, cert_id, training_location, training_dt, training_type, course_duration,
     training_org_hdr_id, training_org_dtl_id, assessment_conducted, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT Training_Log_Hdr_Id, Rig_Id, Cert_Id, Training_Location, Training_Dt, Training_Type, Course_Duration,
       Training_Org_Hdr_Id, Training_Org_Dtl_Id, CASE WHEN Assessment_Conducted = 'Y' THEN 'Y' ELSE 'N' END,
       Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_HSE_Training_Log_Hdr;
ALTER TABLE serosIT.hse_training_log_hdr AUTO_INCREMENT = 3;

INSERT INTO serosIT.hse_training_log_dtl
    (training_log_dtl_id, training_log_hdr_id, training_party, fs_emp_id, trainee_fname, trainee_mname, trainee_lname,
     fs_category_id, trainee_designation, trainee_department, company_name, certificate_issued, certificate_no,
     certificate_dt, cert_valid_upto, certificate_path, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT Training_Log_Dtl_Id, Training_Log_Hdr_Id, CASE WHEN Training_Party = 'EOSIL' THEN 'Seros' ELSE Training_Party END,
       Fs_Emp_Id, Trainee_Fname, Trainee_Mname, Trainee_Lname,
       Fs_Category_Id, Trainee_Designation, Trainee_Department, CASE WHEN Company_Name = 'EOSIL' THEN 'Seros' ELSE Company_Name END,
       CASE WHEN Certificate_Issued = 'Y' THEN 'Y' ELSE 'N' END, Certificate_No,
       Certificate_Dt, Cert_Valid_Upto, CASE WHEN Certificate_Path LIKE 'N/%' THEN NULL ELSE Certificate_Path END,
       Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_HSE_Training_Log_Dtl;
ALTER TABLE serosIT.hse_training_log_dtl AUTO_INCREMENT = 4;

SELECT (SELECT COUNT(*) FROM serosIT.hse_training_log_hdr) AS logs, (SELECT COUNT(*) FROM serosIT.hse_training_log_dtl) AS trainees;
