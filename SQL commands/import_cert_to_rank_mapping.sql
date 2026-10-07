-- Populates Training Certificate to Rank Mapping from the legacy
-- eos_Cert_To_Rank_Mapping table. Verified before writing: every certificate,
-- rank and category id exists here with the same id. Kept as-is on purpose:
-- rank 127 repeats under certificates 61 (x3) and 62 (x5).
INSERT INTO serosIT.cert_to_rank_mapping
    (cert_to_rank_mapping_id, cert_id, fs_category_id, rank_id, cert_to_rank_mapping_active, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT Cert_To_Rank_Mapping_Id, Cert_Id, Fs_Category_Id, Rank_Id, Cert_To_Rank_Mapping_Active, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Cert_To_Rank_Mapping;
ALTER TABLE serosIT.cert_to_rank_mapping AUTO_INCREMENT = 47;

SELECT COUNT(*) AS mappings FROM serosIT.cert_to_rank_mapping;
