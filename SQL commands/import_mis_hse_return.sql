-- Populates MIS Monthly HSE Return (header + all four editable-tab child
-- tables) plus its two new master lookups from the legacy
-- eos_MIS_Monthly_HSE_* tables. 157 real header records, spanning years of
-- real monthly returns.
--
-- Deliberately NOT imported:
--   * eos_MIS_Monthly_HSE_Incidents — every row except the one per header
--     for Incident_Type_Id=4 (LTI Free Days) is a frozen snapshot of a
--     count this app now always computes live against `incident` instead
--     (see core/mis_hse_return.py). Only the LTI Free Days value (the one
--     genuinely manual field on that tab) is carried over, via the
--     UPDATE at the bottom.
--   * eos_MIS_Monthly_HSE_Cards — legacy's own proc never wrote to this
--     table either (its Insert/Update branches are commented out in the
--     source stored proc); Cards has always been pure computed.
--   * eos_MIS_Monthly_HSE_Vehicle_Info — List of vehicles is out of scope
--     for this build (no master exists for it here).
--
-- Rebrand: legacy Mst_HSE_Manhours_Party has 'EOSIL'/'OGDSL' as two of its
-- Party Type values (pre-rebrand company names) — collapsed to 'SEROS' on
-- import so every row matches this app's SEROS-only Party Type choices,
-- the same treatment already applied to HazardCard's reported_by_party
-- elsewhere in this app (SEROS_PARTY_NAMES in mis_hse_return.py).
--
-- ID alignment verified before writing this: mst_cost_centre, mst_rig
-- (bar one legacy junk row, id 31 "t", referenced by nothing),
-- mst_incident_type, mst_hse_activity and mst_hse_consumable all carry
-- the exact same ids as their Seros_Data source tables, so every FK below
-- is a straight passthrough — no id remapping needed.

-- Replace the 3 manually-seeded starter rows with the real 12.
DELETE FROM serosIT.mst_hse_manhours_party;
INSERT INTO serosIT.mst_hse_manhours_party
    (hse_manhours_party_id, hse_manhours_party_name, hse_manhours_party_type, cost_centre_type_id,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    HSE_Manhours_Party_Id, HSE_Manhours_Party_Name,
    CASE WHEN HSE_Manhours_Party_Type IN ('EOSIL', 'OGDSL') THEN 'SEROS' ELSE HSE_Manhours_Party_Type END,
    Cost_Centre_Type_Id, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Mst_HSE_Manhours_Party;
ALTER TABLE serosIT.mst_hse_manhours_party AUTO_INCREMENT = 13;

-- Replace the 3 manually-seeded starter rows with the real 3 (same names,
-- real ids/audit stamps).
DELETE FROM serosIT.mst_hse_meeting;
INSERT INTO serosIT.mst_hse_meeting (hse_meeting_id, hse_meeting_type, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT HSE_Meeting_Id, HSE_Meeting_Type, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Mst_HSE_Meeting;
ALTER TABLE serosIT.mst_hse_meeting AUTO_INCREMENT = 4;

INSERT INTO serosIT.mis_monthly_hse_returns_hdr
    (monthly_hse_returns_hdr_id, cost_centre_id, rig_id, report_no, report_month,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Monthly_HSE_Returns_Hdr_Id, Cost_Centre_Id, Rig_Id, Report_No, Report_Month,
    Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_MIS_Monthly_HSE_Returns_Hdr;
ALTER TABLE serosIT.mis_monthly_hse_returns_hdr AUTO_INCREMENT = 158;

INSERT INTO serosIT.mis_monthly_hse_manhours
    (monthly_hse_manhours_id, monthly_hse_returns_hdr_id, hse_manhours_party_id, no_of_personnel, hours_worked,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Monthly_HSE_Manhours_Id, Monthly_HSE_Returns_Hdr_Id, HSE_Manhours_Party_Id, No_Of_Personnel, Hours_Worked,
    Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_MIS_Monthly_HSE_Manhours;
ALTER TABLE serosIT.mis_monthly_hse_manhours AUTO_INCREMENT = 444;

INSERT INTO serosIT.mis_monthly_hse_meetings
    (monthly_hse_meeting_id, monthly_hse_returns_hdr_id, hse_meeting_id, total_meetings, total_seros_employees,
     total_contractors, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Monthly_HSE_Meeting_Id, Monthly_HSE_Returns_Hdr_Id, HSE_Meeting_Id, Total_Meetings, Total_Eosil_Employees,
    Total_Contractors, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_MIS_Monthly_HSE_Meetings;
ALTER TABLE serosIT.mis_monthly_hse_meetings AUTO_INCREMENT = 396;

INSERT INTO serosIT.mis_monthly_hse_activities
    (monthly_hse_activity_id, monthly_hse_returns_hdr_id, hse_activity_id, total_activities, seros_emp_count,
     contractor_count, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Monthly_HSE_Activity_Id, Monthly_HSE_Returns_Hdr_Id, HSE_Activity_Id, Total_Activities, Eosil_Emp_Count,
    Contractor_Count, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_MIS_Monthly_HSE_Activities;
ALTER TABLE serosIT.mis_monthly_hse_activities AUTO_INCREMENT = 1052;

INSERT INTO serosIT.mis_monthly_hse_environment
    (monthly_hse_environment_id, monthly_hse_returns_hdr_id, hse_consumable_id, total_quantity, remarks,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Monthly_HSE_Environment_Id, Monthly_HSE_Returns_Hdr_Id, HSE_Consumable_Id, Total_Quantity, Remarks,
    Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_MIS_Monthly_HSE_Environment;
ALTER TABLE serosIT.mis_monthly_hse_environment AUTO_INCREMENT = 2321;

UPDATE serosIT.mis_monthly_hse_returns_hdr hdr
JOIN Seros_Data.eos_MIS_Monthly_HSE_Incidents lti
    ON lti.Monthly_HSE_Returns_Hdr_Id = hdr.monthly_hse_returns_hdr_id AND lti.Incident_Type_Id = 4
SET hdr.lti_free_days = lti.LTI_Free_Days;

SELECT
    (SELECT COUNT(*) FROM serosIT.mst_hse_manhours_party) AS parties,
    (SELECT COUNT(*) FROM serosIT.mst_hse_meeting) AS meetings,
    (SELECT COUNT(*) FROM serosIT.mis_monthly_hse_returns_hdr) AS headers,
    (SELECT COUNT(*) FROM serosIT.mis_monthly_hse_manhours) AS manhours,
    (SELECT COUNT(*) FROM serosIT.mis_monthly_hse_meetings) AS meeting_rows,
    (SELECT COUNT(*) FROM serosIT.mis_monthly_hse_activities) AS activity_rows,
    (SELECT COUNT(*) FROM serosIT.mis_monthly_hse_environment) AS environment_rows,
    (SELECT COUNT(*) FROM serosIT.mis_monthly_hse_returns_hdr WHERE lti_free_days IS NOT NULL) AS lti_backfilled;
