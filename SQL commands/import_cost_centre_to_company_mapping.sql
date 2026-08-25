INSERT INTO serosIT.mst_organisational_grp
    (organisational_grp_id, organisational_grp_name, organisational_grp_abrv, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT Organisational_Grp_Id, Organisational_Grp_Name, Organisational_Grp_Abrv, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.Mst_Organisational_Grp;
ALTER TABLE serosIT.mst_organisational_grp AUTO_INCREMENT = 5;

-- Business Grp and Company both self-reference — disable FK checks for
-- this bulk load so row order doesn't matter, matching legacy's own lack
-- of a real constraint here.
SET FOREIGN_KEY_CHECKS = 0;

INSERT INTO serosIT.mst_business_grp
    (business_grp_id, business_grp_name, parent_business_grp_id, business_grp_abrv, business_grp_order,
     business_grp_from, business_grp_to, business_grp_active, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT BUSINESS_GRP_ID, BUSINESS_GRP_NAME, Parent_Business_Grp_Id, BUSINESS_GRP_ABRV, BUSINESS_GRP_ORDER,
       BUSINESS_GRP_FROM, BUSINESS_GRP_TO, BUSINESS_GRP_ACTIVE, CR_USER_ID, CR_DT, MOD_USER_ID, MOD_DT
FROM Seros_Data.Mst_Business_Grp;
ALTER TABLE serosIT.mst_business_grp AUTO_INCREMENT = 15;

INSERT INTO serosIT.mst_company
    (company_id, organisational_grp_id, business_grp_id, company_name, parent_company_id, company_abrv,
     company_code, country_id, currency_id, company_order, company_from, company_to, company_active,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT COMPANY_ID, Organisational_Grp_Id, Business_Grp_Id, Company_Name, Parent_Company_Id, Company_ABRV,
       Company_Code, Country_Id, Currency_Id, Company_Order, Company_From, Company_To,
       IF(Company_Active = 'Y', 'Y', 'N'),
       Cr_User_Id, CR_DT, Mod_User_Id, Mod_Dt
FROM Seros_Data.Mst_Company;
ALTER TABLE serosIT.mst_company AUTO_INCREMENT = 322;

SET FOREIGN_KEY_CHECKS = 1;

-- Legacy's own id column isn't unique (Comp_To_CC_Map_Id=13 had 2 rows) —
-- let the target table assign fresh ids instead of preserving it.
INSERT INTO serosIT.cost_centre_to_company_mapping
    (company_id, cost_centre_id, mapping_from, mapping_to, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT Company_Id, Cost_Centre_Id, Mapping_From, Mapping_To, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Cost_Centre_To_Company_Mapping;

SELECT COUNT(*) FROM serosIT.mst_organisational_grp;
SELECT COUNT(*) FROM serosIT.mst_business_grp;
SELECT COUNT(*) FROM serosIT.mst_company;
SELECT COUNT(*) FROM serosIT.cost_centre_to_company_mapping;
