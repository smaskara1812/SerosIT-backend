INSERT INTO serosIT.incident
    (incident_id, work_location_id, rig_id, unit_name, rig_incident_no, incident_no, incident_date,
     financial_year_id, country_id, well_no, drilling_superintendent, safety_officer, incident_party,
     incident_descr, incident_severity_potential, incident_severity, incident_type_id,
     immediate_incident_cause_id, immediate_incident_cause_id_2, immediate_cause_descr,
     rig_operation_id, contact_expo_type_id, corrective_action, preventive_action,
     npt_hrs_loss, manhours_loss, financial_loss_currency_id, financial_loss_amt, exchange_rate,
     financial_loss_bc_amt, comments, third_party, contractor_id, operator_id, incident_reported_dt,
     person_injured, fs_emp_id, emp_name, rank_id, rank_name, total_rig_exp_months,
     part_of_body_id_1, part_of_body_id_2, part_of_body_id_3, part_of_body_id_4,
     reported_by, rptd_by_rank_id, dms_path_qhse, marked_as_deleted, deleted_remarks,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Incident_Id, Work_Location_Id, Rig_Id, Unit_Name, Rig_Incident_No, Incident_No, Incident_Date,
    Financial_Year_Id, Country_Id, Well_No, Drilling_Superintendent, Safety_Officer, Incident_Party,
    Incident_Descr, Incident_Severity_Potential, Incident_Severity, Incident_Type_Id,
    Immediate_Incident_Cause_Id, Immediate_Incident_Cause_Id_2, Immediate_Cause_Descr,
    -- Rig_Operation_Id=32 and Contact_Expo_Type_Id=22 are dangling refs in the
    -- legacy data itself (no such row in either Seros_Data or serosIT) —
    -- nulled out rather than blocking the whole import; both columns are
    -- already nullable in the legacy schema.
    NULLIF(Rig_Operation_Id, 32), NULLIF(Contact_Expo_Type_Id, 22),
    Corrective_Action, Preventive_Action,
    NPT_Hrs_Loss, Manhours_Loss, Financial_Loss_Currency_Id, Financial_Loss_Amt, Exchange_Rate,
    Financial_Loss_BC_Amt, Comments, Third_Party, Contractor_Id, Operator_Id, Incident_Reported_Dt,
    Person_Injured, Fs_Emp_Id, Emp_Name, Rank_Id, Rank_Name, Total_Rig_Exp_Months,
    Part_Of_Body_Id_1, Part_Of_Body_Id_2, Part_Of_Body_Id_3, Part_Of_Body_Id_4,
    Reported_By, Rptd_By_Rank_Id, DMS_Path_QHSE, Marked_As_Deleted, Deleted_Remarks,
    Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Incident_Details;

ALTER TABLE serosIT.incident AUTO_INCREMENT = 523;

SELECT COUNT(*) FROM serosIT.incident;
