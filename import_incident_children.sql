INSERT INTO serosIT.mst_incident_subcause
    (incident_subcause_id, incident_subcause, incident_cause_id, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT Incident_Subcause_Id, Incident_Subcause, Incident_Cause_Id, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.Mstx_Incident_Subcause;
ALTER TABLE serosIT.mst_incident_subcause AUTO_INCREMENT = 128;

INSERT INTO serosIT.incident_action
    (incident_action_id, incident_id, action_recommended, action_taken, action_party,
     target_date, completion_dt, action_status, marked_as_deleted, deleted_remarks,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT Incident_Action_Id, Incident_Id, Action_Recommended, Action_Taken, Action_Party,
       Target_Date, Completion_Dt, Action_Status, Marked_As_Deleted, Deleted_Remarks,
       Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Incident_Actions;
ALTER TABLE serosIT.incident_action AUTO_INCREMENT = 84;

INSERT INTO serosIT.incident_photo
    (incident_photo_id, incident_id, incident_photo_path, incident_photo_active,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT Incident_Photo_Id, Incident_Id, Incident_Photo_Path, Incident_Photo_Active,
       Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Incident_Photos;
ALTER TABLE serosIT.incident_photo AUTO_INCREMENT = 595;

INSERT INTO serosIT.incident_root_cause
    (incident_root_cause_id, incident_id, root_cause_id, root_subcause_id, root_subcause_others,
     marked_as_deleted, deleted_remarks, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT Incident_Root_Cause_Id, Incident_Id, Root_Cause_Id, Root_Subcause_Id, Root_Subcause_Others,
       Marked_As_Deleted, Deleted_Remarks, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Incident_Root_Cause;
ALTER TABLE serosIT.incident_root_cause AUTO_INCREMENT = 51;

SELECT COUNT(*) FROM serosIT.mst_incident_subcause;
SELECT COUNT(*) FROM serosIT.incident_action;
SELECT COUNT(*) FROM serosIT.incident_photo;
SELECT COUNT(*) FROM serosIT.incident_root_cause;
