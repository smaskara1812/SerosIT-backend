-- Populates rig_cert from the legacy eos_Buss_Cert_Dtl table — QHSE's Rig
-- Certificates page. Buss_Cert_Path isn't carried over: those paths point
-- to files on the legacy file server that were never part of this
-- migration, so certificate_path is left NULL rather than storing a path
-- that would 404 against this app's own MEDIA_ROOT. Buss_Cert_Active is
-- skipped too — blank on all but 4 of the 37 legacy rows (never a real
-- Y/N toggle) and isn't part of the QHSE page this table backs.
-- Requires mst_rig, mst_buss_cert, mst_buss_cert_issue_authority already
-- populated — Rig_Id/Buss_Cert_Id/Buss_Cert_Issue_Auth_Id line up 1:1 with
-- those (verified by name), so no remapping is needed.

INSERT INTO serosIT.rig_cert
    (rig_cert_id, rig_id, buss_cert_id, buss_cert_issue_auth_id, certificate_no,
     cert_date, valid_till, remark, certificate_path,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Buss_Cert_Dtl_Id, Rig_Id, Buss_Cert_Id, Buss_Cert_Issue_Auth_Id, Buss_Cert_No,
    Buss_Cert_Dt, Buss_Cert_Valid_Till, Remarks, NULL,
    Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Buss_Cert_Dtl;

ALTER TABLE serosIT.rig_cert AUTO_INCREMENT = 38;

-- Populates rig_cert_schedule from the legacy eos_Buss_Cert_Schedule_Dtl
-- table. Schedule_Type is stored here as a single-char code (A/I) rather
-- than the legacy free-text label, matching RigCertSchedule.SCHEDULE_TYPE_CHOICES.
-- Requires rig_cert already populated (above).

INSERT INTO serosIT.rig_cert_schedule
    (rig_cert_schedule_id, rig_cert_id, scheduled_dt, schedule_type,
     remark, completion_dt, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Buss_Cert_Schedule_Id, Buss_Cert_Dtl_Id, Buss_Cert_Schd_Dt,
    CASE Buss_Cert_Schd_Type
        WHEN 'Annual Survey' THEN 'A'
        WHEN 'Intermediate Survey' THEN 'I'
    END,
    Remarks, Buss_Cert_Schd_Complete_Dt, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Buss_Cert_Schedule_Dtl;

ALTER TABLE serosIT.rig_cert_schedule AUTO_INCREMENT = 13;

SELECT COUNT(*) FROM serosIT.rig_cert;
SELECT COUNT(*) FROM serosIT.rig_cert_schedule;
