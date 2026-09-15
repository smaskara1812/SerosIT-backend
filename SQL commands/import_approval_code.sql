-- Populates mst_approval_code from the legacy eos_Approval_Code table —
-- part of the new generic approval engine (Approval Code / Approver
-- Mapping / Approver Mapping Dtl), reused across every approval-driven
-- transaction form, not just Drilling Report.

INSERT INTO serosIT.mst_approval_code
    (approval_code_id, approval_code, approval_desc, approval_active,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Approval_Code_Id,
    Approval_Code,
    Approval_Desc,
    Approval_Active,
    Cr_User_Id,
    Cr_Dt,
    Mod_User_Id,
    Mod_Dt
FROM Seros_Data.eos_Approval_Code;
