-- Populates company_name_change from the legacy eos_Company_Name_Change
-- table — tracks each company's name/short-name/logo assets over a
-- From_Date/To_Date range (NULL To_Date = current). Backing data for the
-- still-unbuilt "which company name + logo applies to this record"
-- resolver (see project memory qhse_incident_report_dynamic_branding).
-- Legacy's own PK is preserved — only 6 rows, a small stable reference
-- table like Mst_Organisational_Grp/Mst_Business_Grp above.

INSERT INTO serosIT.company_name_change
    (company_name_change_id, company_id, company_name, company_short_name,
     image_path_header, image_path_footer, image_path_stamp,
     from_date, to_date, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Company_Name_Change_Id, Company_Id, Company_Name, Company_Short_Name,
    Image_Path_Header, Image_Path_Footer, Image_Path_Stamp,
    From_Date, To_Date, Cr_User_id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Company_Name_Change;

ALTER TABLE serosIT.company_name_change AUTO_INCREMENT = 7;

SELECT COUNT(*) FROM serosIT.company_name_change;
