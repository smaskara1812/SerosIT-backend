INSERT INTO serosIT.mst_it_asset
    (it_asset_id, it_asset_model_id, it_asset_type_id, it_asset_subtype_id, it_asset_mfg_id,
     own_company_id, it_asset_mac_addr, it_asset_sr_no, it_asset_tag, it_asset_sap_code,
     it_asset_ram, it_asset_hdd, it_asset_particulars, it_asset_product_no, cur_company_id,
     emp_id, dept_id, company_loc_id, po_no, po_dt, vendor_id, invoice_no,
     it_asset_pur_dt, it_asset_warranty_upto, it_asset_amc_dt, it_asset_holder_type,
     remarks, it_asset_allocated, it_asset_active, it_asset_to_dt,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    IT_Asset_Id,
    -- IT_Asset_Model_Id 435-438 and IT_Asset_Mfg_Id 45 are dangling refs in
    -- the legacy data itself (no such row even in the raw legacy lookup
    -- tables) — nulled out rather than blocking the whole import.
    IF(IT_Asset_Model_Id IN (435, 436, 437, 438), NULL, IT_Asset_Model_Id),
    IT_Asset_Type_Id, IT_Asset_SubType_Id,
    IF(IT_Asset_Mfg_Id = 45, NULL, IT_Asset_Mfg_Id),
    Own_Company_Id, IT_Asset_Mac_Addr, IT_Asset_Sr_No, IT_Asset_Tag, IT_Asset_SAP_Code,
    IT_Asset_RAM, IT_Asset_HDD, IT_Asset_Particulars, IT_Asset_Product_No, Cur_Company_Id,
    Emp_Id, Dept_Id, Company_Loc_Id, PO_No, PO_Dt, Vendor_Id, Invoice_No,
    IT_Asset_Pur_Dt, IT_Asset_Warranty_Upto, IT_Asset_AMC_Dt, IT_Asset_Holder_Type,
    Remarks, IT_Asset_Allocated, IT_Asset_Active, IT_Asset_To_Dt,
    Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.it_Mst_IT_Asset;

ALTER TABLE serosIT.mst_it_asset AUTO_INCREMENT = 10787;

INSERT INTO serosIT.it_asset_holder
    (it_asset_holder_id, it_asset_id, it_asset_holder_from, holder_company_id,
     emp_id, dept_id, company_loc_id, holder_name, holder_remark, vessel_id,
     it_asset_holder_to, mod_user_id, mod_dt)
SELECT IT_Asset_Holder_Id, IT_Asset_Id, IT_Asset_Holder_From, Holder_Company_Id,
       Emp_Id, Dept_Id, Company_Loc_Id, Holder_Name, Holder_Remark, Vessel_Id,
       IT_Asset_Holder_To, Mod_User_Id, Mod_Dt
FROM Seros_Data.it_IT_Asset_Holder;
ALTER TABLE serosIT.it_asset_holder AUTO_INCREMENT = 12766;

INSERT INTO serosIT.it_accessory_holder
    (it_accessory_holder_id, it_accessory_id, emp_id, it_accessory_holder_name, it_asset_mfg_id,
     it_accessory_model, it_accessory_sr_no, it_accessory_product_no, it_accessory_holder_from,
     it_accessory_holder_remark, it_accessory_holder_to, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT IT_Accessory_Holder_Id, IT_Accessory_Id, Emp_Id, IT_Accessory_Holder_Name, IT_Asset_Mfg_Id,
       IT_Accessory_Model, IT_Accessory_Sr_No, IT_Accessory_Product_No, IT_Accessory_Holder_From,
       IT_Accessory_Holder_Remark, IT_Accessory_Holder_To, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.it_IT_Accessory_Holder;
ALTER TABLE serosIT.it_accessory_holder AUTO_INCREMENT = 229;

SELECT 'mst_it_asset' t, COUNT(*) c FROM serosIT.mst_it_asset
UNION ALL SELECT 'it_asset_holder', COUNT(*) FROM serosIT.it_asset_holder
UNION ALL SELECT 'it_accessory_holder', COUNT(*) FROM serosIT.it_accessory_holder;
