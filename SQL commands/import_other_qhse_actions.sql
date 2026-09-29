INSERT INTO serosIT.other_qhse_action
    (other_qhse_action_id, qhse_category_id, icr_no, other_qhse_action_dt, rig_id,
     action_recommended, action_taken, action_party, target_date, completion_dt, action_status,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Other_QHSE_Action_Id, QHSE_Category_Id, ICR_No, Other_QHSE_Action_Dt, Rig_Id,
    Action_Recommended, Action_Taken, Action_Party, Target_Date, Completion_Dt, Action_Status,
    Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Other_QHSE_Actions;

SELECT COUNT(*) FROM serosIT.other_qhse_action;
