-- Populates approver_mapping_dtl from the legacy eos_Approver_Mapping_Dtl
-- table — the Rig/Dept scoping grid nested under each Approver Mapping row.
--
-- Receive_Mail/Approve_YN/Open_For_Revision_YN/Create_YN store '' (empty
-- string) for "unchecked", same pattern as Mail Alert Dtl's flags — NULLIF
-- normalizes them to real NULL so the frontend's checkbox convention
-- (checked = value === 'Y') doesn't render '' as checked.
--
-- Run import_approver_mapping.sql first — approver_mapping_id here must
-- already exist as a parent row.

INSERT INTO serosIT.approver_mapping_dtl
    (approver_mapping_dtl_id, approver_mapping_id, rig_id, dept_id,
     receive_mail, approve_yn, open_for_revision_yn, create_yn,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Approver_Mapping_Dtl_Id,
    Approver_Mapping_Id,
    Rig_Id,
    Dept_Id,
    NULLIF(Receive_Mail, ''),
    NULLIF(Approve_YN, ''),
    NULLIF(Open_For_Revision_YN, ''),
    NULLIF(Create_YN, ''),
    Cr_User_Id,
    Cr_Dt,
    Mod_User_Id,
    Mod_Dt
FROM Seros_Data.eos_Approver_Mapping_Dtl
-- Dept_Id is a real, unmigrated FK in the legacy source (no Dept master
-- import has ever hit a bad row before this) — but if a future re-run of
-- this script ever meets a Dept_Id that doesn't exist in mst_department,
-- skip it rather than fail the whole import; check separately if 0 rows
-- come back missing here.
WHERE Rig_Id IN (SELECT rig_id FROM serosIT.mst_rig)
  AND (Dept_Id IS NULL OR Dept_Id IN (SELECT dept_id FROM serosIT.mst_department));
