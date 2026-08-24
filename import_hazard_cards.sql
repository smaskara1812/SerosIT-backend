INSERT INTO serosIT.hazard_card
    (haz_card_id, haz_id_card_no, prj_contract_id, rig_id, event_dt,
     reported_by_party, reported_by_fs_emp_id, reported_by_name, work_location_id,
     haz_type_id, timeout_for_safety, hazard_desc, action_taken, resp_dept_id, resp_rank_id,
     close_out_dt, haz_id_card_status, marked_as_deleted, deleted_remarks,
     client_key_id, mac_address, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Haz_Card_Id, Haz_ID_Card_No, Prj_Contract_Id, Rig_Id, Event_Dt,
    Reported_By_Party, Reported_By_Fs_Emp_Id, Reported_By_Name, Work_Location_Id,
    Haz_Type_Id, Timeout_For_Safety, Hazard_Desc, Action_Taken, Resp_Dept_Id, Resp_Rank_Id,
    Close_Out_Dt, Haz_ID_Card_Status, Marked_As_Deleted, Deleted_Remarks,
    Client_Key_Id, MAC_Address, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Hazard_ID_Card;

ALTER TABLE serosIT.hazard_card AUTO_INCREMENT = 31438;

SELECT COUNT(*) FROM serosIT.hazard_card;
