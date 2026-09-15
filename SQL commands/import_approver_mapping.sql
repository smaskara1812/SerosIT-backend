-- Populates approver_mapping (header) from the legacy eos_Approver_Mapping
-- table. Approver_Active stores '' (blank) for "inactive" in the real data
-- (170 rows: 61 explicit 'Y', 109 blank, never an explicit 'N') — same
-- convention as every other Active flag in this app (BaseMasterViewSet's
-- ?active=Y/N treats anything but explicit 'Y' as inactive), so no
-- normalization needed here, unlike the Dtl flags below.

INSERT INTO serosIT.approver_mapping
    (approver_mapping_id, approval_code_id, approver_user_id, approver_level,
     approver_active, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Approver_Mapping_Id,
    Approval_Code_Id,
    Approver_User_Id,
    Approver_Level,
    Approver_Active,
    Cr_User_Id,
    Cr_Dt,
    Mod_User_Id,
    Mod_Dt
FROM Seros_Data.eos_Approver_Mapping;
