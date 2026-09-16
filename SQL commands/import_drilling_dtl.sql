-- Populates drilling_dtl (Drilling Report / Daily Report header) from the
-- legacy eos_Drilling_Dtl table. Run BEFORE import_drilling_dtl_ops.sql —
-- Drilling_Dtl_Ops rows reference this table's PK.
--
-- Cr_Status/L1_Approval_Status store '' (blank) for "not yet set" in the
-- real data, same pattern as every other Y/blank flag imported this
-- project — NULLIF normalizes both to real NULL so core/approvals.py's
-- is_draft()/gate checks (which treat None as "no decision yet") read the
-- historical rows the same way a freshly-created draft reads.
--
-- No FK orphans and no explicit-PK-0 row in the source (verified before
-- writing this script) — no NO_AUTO_VALUE_ON_ZERO landmine here.
--
-- operating_hrs/standby_hrs/etc. are imported as the legacy trigger last
-- computed them, then recomputed in bulk by a follow-up Python pass
-- (recompute_dtl_totals over every imported row) so every row and its
-- parent DrillingHdr rollup is guaranteed consistent with this app's own
-- rate-bucket mapping, not just trusted as-is from the import.

INSERT INTO serosIT.drilling_dtl
    (drilling_dtl_id, rig_id, drilling_hdr_id, drilling_dtl_dt,
     pob_operator, pob_essar, pob_essar_serv, pob_others,
     wind_speed, current_k, at_press_mbar, vdl, avdl, tot_vdl, kg, kg_margin, draft,
     consumption_diesel, consumption_water, received_diesel, received_water, generated_water,
     operating_hrs, standby_hrs, repair_service_hrs, repair_rate_hrs, zero_rate_hrs, rig_move_hrs, drilling_meterage,
     remark, downtime_reason,
     cr_status, l1_approval_status, l1_approval_dt, l1_user_id,
     opened_for_revision_by, opened_for_revision_dt,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Drilling_Dtl_Id, Rig_Id, Drilling_Hdr_Id, Drilling_Dtl_Dt,
    POB_Operator, POB_Essar, POB_Essar_Serv, POB_Others,
    Wind_Speed, Current_K, At_Press_Mbar, VDL, AVDL, Tot_VDL, KG, KG_Margin, Draft,
    Consumption_Diesel, Consumption_Water, Received_Diesel, Received_Water, Generated_Water,
    Operating_Hrs, Standby_Hrs, Repair_Service_Hrs, Repair_Rate_Hrs, Zero_Rate_Hrs, Rig_Move_Hrs, Drilling_Meterage,
    Remark, Downtime_Reason,
    NULLIF(Cr_Status, ''), NULLIF(L1_Approval_Status, ''), L1_Approval_Dt, L1_User_Id,
    Opened_For_Revision_By, Opened_For_Revision_Dt,
    Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Drilling_Dtl;
