INSERT INTO serosIT.rig_site_mapping
    (rig_site_mapping_id, rig_id, company_id, camp_office_addr,
     contact_fs_emp_id_1, contact_tel_no_1, contact_fs_emp_id_2, contact_tel_no_2,
     location_id, site_from, site_to, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT Rig_Site_Mapping_Id, Rig_Id, Company_Id, Camp_Office_Addr,
       Contact_Fs_Emp_Id_1, Contact_Tel_No_1, Contact_Fs_Emp_Id_2, Contact_Tel_No_2,
       Location_Id, Site_From, Site_To, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Rig_Site_Mapping;

ALTER TABLE serosIT.rig_site_mapping AUTO_INCREMENT = 71;

SELECT COUNT(*) FROM serosIT.rig_site_mapping;
