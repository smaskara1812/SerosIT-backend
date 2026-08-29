INSERT INTO serosIT.mst_vendor_type
    (vendor_type_id, vendor_type_name, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT Vendor_Type_Id, Vendor_Type, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.Mst_Vendor_Type;
ALTER TABLE serosIT.mst_vendor_type AUTO_INCREMENT = 6;

INSERT INTO serosIT.mst_company_location
    (company_loc_id, company_loc_name, company_loc_abrv, company_loc_address, location_id,
     postal_code, country_id, latitude, longitude, company_loc_type, company_loc_ownership,
     company_loc_order, company_loc_active, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT Company_Loc_Id, Company_Loc_NAME, Company_Loc_ABRV, Company_Loc_Address, Location_Id,
       Postal_Code, Country_Id, Latitude, Longitude, Company_Loc_Type, Company_Loc_Ownership,
       Company_Loc_Order, Company_Loc_Active, Cr_User_Id, CR_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.Mst_Company_Location;
ALTER TABLE serosIT.mst_company_location AUTO_INCREMENT = 296;

INSERT INTO serosIT.mstx_vendor
    (vendor_id, vendor_name, vendor_type_id, vendor_sap_code, vendor_address, country_id,
     vendor_tel_no, vendor_email, currency_id, vendor_active, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT Vendor_Id, Vendor_Name, Vendor_Type_Id, Vendor_SAP_Code, Vendor_Address, Country_id,
       Vendor_Tel_No, Vendor_Email, Currency_Id, Vendor_Active, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.Mstx_Vendor;
ALTER TABLE serosIT.mstx_vendor AUTO_INCREMENT = 3226;

INSERT INTO serosIT.mst_it_asset_mfg
    (it_asset_mfg_id, it_asset_mfg_name, it_asset_mfg_active, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT IT_Asset_Mfg_id, IT_Asset_Mfg, IT_Asset_Mfg_ACTIVE, CR_USER_ID, CR_DT, MOD_USER_ID, MOD_DT
FROM Seros_Data.Mst_IT_Asset_Mfg;
ALTER TABLE serosIT.mst_it_asset_mfg AUTO_INCREMENT = 45;

INSERT INTO serosIT.mst_it_asset_type
    (it_asset_type_id, it_asset_type_name, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT it_asset_type_id, it_asset_type, CR_USER_ID, CR_DT, MOD_USER_ID, MOD_DT
FROM Seros_Data.Mst_IT_Asset_Type;
ALTER TABLE serosIT.mst_it_asset_type AUTO_INCREMENT = 12;

INSERT INTO serosIT.mst_it_asset_subtype
    (it_asset_subtype_id, it_asset_type_id, it_asset_subtype_name, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT it_asset_SubType_id, it_asset_type_id, it_asset_SubType, CR_USER_ID, CR_DT, MOD_USER_ID, MOD_DT
FROM Seros_Data.Mst_IT_Asset_SubType;
ALTER TABLE serosIT.mst_it_asset_subtype AUTO_INCREMENT = 23;

INSERT INTO serosIT.mst_it_asset_model
    (it_asset_model_id, it_asset_mfg_id, it_asset_subtype_id, it_asset_model_name, it_asset_model_active,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT IT_Asset_Model_id, IT_Asset_Mfg_id, IT_Asset_SubType_id, IT_Asset_Model, IT_Asset_Model_Active,
       CR_USER_ID, CR_DT, MOD_USER_ID, MOD_DT
FROM Seros_Data.Mst_IT_Asset_Model;
ALTER TABLE serosIT.mst_it_asset_model AUTO_INCREMENT = 435;

INSERT INTO serosIT.mst_it_accessory
    (it_accessory_id, it_accessory_name, it_accessory_active, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT IT_Accessory_Id, IT_Accessory_Name, IT_Accessory_Active, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.Mst_IT_Accessory;
ALTER TABLE serosIT.mst_it_accessory AUTO_INCREMENT = 19;

SELECT 'vendor_type' t, COUNT(*) c FROM serosIT.mst_vendor_type
UNION ALL SELECT 'company_location', COUNT(*) FROM serosIT.mst_company_location
UNION ALL SELECT 'vendor', COUNT(*) FROM serosIT.mstx_vendor
UNION ALL SELECT 'it_asset_mfg', COUNT(*) FROM serosIT.mst_it_asset_mfg
UNION ALL SELECT 'it_asset_type', COUNT(*) FROM serosIT.mst_it_asset_type
UNION ALL SELECT 'it_asset_subtype', COUNT(*) FROM serosIT.mst_it_asset_subtype
UNION ALL SELECT 'it_asset_model', COUNT(*) FROM serosIT.mst_it_asset_model
UNION ALL SELECT 'it_accessory', COUNT(*) FROM serosIT.mst_it_accessory;
