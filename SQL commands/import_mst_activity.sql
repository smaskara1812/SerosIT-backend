-- Populates mst_activity from the legacy Mst_Activity table — QHSE's
-- Activity master. This app only concerns itself with Oilfield Services
-- rigs, so only the legacy rows extended to Business_System_Id_6
-- (Oilfield Services) are imported (93 of 283) — the legacy "Extended to"
-- business-system checkboxes themselves have no equivalent column here at
-- all, since every imported row already only applies to this one system.

INSERT INTO serosIT.mst_activity
    (activity_id, activity_name, activity_type, activity_nature, activity_location,
     intimate_vessel, activity_validity_days, activity_active,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Activity_Id, Activity_Name, Activity_Type, Activity_Nature, Activity_Location,
    Intimate_Vessel, Activity_Validity_Days, Activity_Active,
    Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.Mst_Activity
WHERE Business_System_Id_6 = 'Y';

-- Bumped past the legacy table's own overall max id (283, not just the
-- Oilfield Services subset's 282) so a later re-import with a broader
-- scope can't collide with a row a UI-driven Create already claimed here.
ALTER TABLE serosIT.mst_activity AUTO_INCREMENT = 284;

SELECT COUNT(*) FROM serosIT.mst_activity;
