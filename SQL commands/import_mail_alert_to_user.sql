-- Populates mail_alert_to_user from the legacy Mail_Alert_To_User table —
-- a brand-new table in this app, no prior import_*.sql this rides along
-- with. Requires mail_alert_dtl already populated (see
-- import_mail_alert_dtl.sql). Read_Receipt stores '' for "unchecked" here
-- (see import_mail_alert_dtl.sql's note) — NULLIF normalizes it to NULL.

INSERT INTO serosIT.mail_alert_to_user
    (mail_alert_to_user_id, alert_id, emp_id, email_addr, read_receipt,
     mail_alert_from, mail_alert_to, addressee_type, mail_alert_order,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Mail_Alert_To_User_Id,
    Alert_Id,
    EMP_ID,
    EMAIL_Addr,
    NULLIF(Read_Receipt, ''),
    Mail_Alert_From,
    Mail_Alert_To,
    Addressee_Type,
    Mail_Alert_Order,
    CR_USER_ID,
    CR_DT,
    MOD_USER_ID,
    MOD_DT
FROM Seros_Data.Mail_Alert_To_User;
