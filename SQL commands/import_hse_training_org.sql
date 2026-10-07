-- Populates Training Org (organisations + their trainers) from the legacy
-- eos_HSE_Training_Org_* tables. Verified before writing: every location id
-- exists here with the same id and agrees with the stored country. Ids are
-- kept because the legacy Training Log points at them.
INSERT INTO serosIT.hse_training_org_hdr
    (training_org_hdr_id, training_org_name, training_org_address, location_id, country_id,
     contact_person_1, tel_no_1, contact_person_2, tel_no_2, training_org_email, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT Training_Org_Hdr_Id, Training_Org_Name, Training_Org_Address, Location_Id, Country_Id,
       Contact_Person_1, Tel_No_1, Contact_Person_2, Tel_No_2, Training_Org_Email, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_HSE_Training_Org_Hdr;
ALTER TABLE serosIT.hse_training_org_hdr AUTO_INCREMENT = 6;

INSERT INTO serosIT.hse_training_org_dtl
    (training_org_dtl_id, training_org_hdr_id, trainer_fname, trainer_mname, trainer_lname, trainer_qualification,
     trainer_mobile_no, trainer_email_id, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT Training_Org_Dtl_Id, Training_Org_Hdr_Id, Trainer_Fname, Trainer_Mname, Trainer_Lname, Trainer_Qualification,
       Trainer_Mobile_No, Trainer_Email_Id, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_HSE_Training_Org_Dtl;
ALTER TABLE serosIT.hse_training_org_dtl AUTO_INCREMENT = 9;

SELECT (SELECT COUNT(*) FROM serosIT.hse_training_org_hdr) AS orgs, (SELECT COUNT(*) FROM serosIT.hse_training_org_dtl) AS trainers;
