-- Populates mail_alert_dtl from the legacy Mail_Alert_Dtl table — a
-- brand-new table in this app, no prior import_*.sql this rides along
-- with. Business_System_Id and Menu_Id are deliberately dropped (by
-- request) — no Business System FK and no Menu field on this master.
--
-- Additional_Alert/Alert_Active store '' (empty string) for "unchecked"
-- here, unlike every other Y/NULL flag imported so far this app — NULLIF
-- normalizes them to real NULL so the frontend's flag-id checkbox (which
-- checks `value != null`) doesn't render '' as checked.
--
-- Legacy Alert_Id starts at 0 (a real row) — run this with
-- NO_AUTO_VALUE_ON_ZERO on, or MySQL silently auto-assigns that row the
-- next identity value instead of storing 0 literally, colliding with the
-- real id-1 row (same landmine import_all_tables.py already documents):
--   SET SESSION sql_mode = CONCAT(@@sql_mode, ',NO_AUTO_VALUE_ON_ZERO');

INSERT INTO serosIT.mail_alert_dtl
    (alert_id, alert_type, alert_category, alert_name, alert_window, alert_freq,
     mail_subject, particulars, next_mail_dt, start_time, additional_alert,
     alert_display_name, alert_active,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Alert_Id,
    Alert_Type,
    Alert_Category,
    Alert_Name,
    Alert_Window,
    Alert_Freq,
    Mail_Subject,
    Particulars,
    Next_Mail_Dt,
    Start_Time,
    NULLIF(Additional_Alert, ''),
    Alert_Display_Name,
    NULLIF(Alert_Active, ''),
    Cr_User_Id,
    CR_DT,
    Mod_User_Id,
    Mod_Dt
FROM Seros_Data.Mail_Alert_Dtl;
