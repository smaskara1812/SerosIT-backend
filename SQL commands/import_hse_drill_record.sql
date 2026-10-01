-- Populates HSE Drill Record (header + its five child tables) from the
-- legacy eos_HSE_Drill_Record_* tables. ID alignment verified before
-- writing this: mst_rig, mst_employee and mst_hse_drill all carry the
-- same ids as their Seros_Data source tables (mst_hse_drill was imported
-- fresh in import_mst_hse_drill.sql specifically so this would hold), so
-- every FK below is a straight passthrough.
--
-- Not migrated: the actual photo files behind
-- hse_drill_record_photo_upload.drill_rec_photo_upload_path — they lived
-- on the legacy IIS file server (/Images/HSE_Drills_Photos/*.jpg), which
-- isn't available here. The path strings themselves are migrated as a
-- historical record; they won't resolve to a real image in this app.

INSERT INTO serosIT.hse_drill_record_hdr
    (drill_record_hdr_id, rig_id, drill_record_sr_no, drill_record_no, drill_dt, drill_location,
     hse_drill_id_1, hse_drill_id_2, head_count, initiated_by_fs_emp_id_1, initiated_by_fs_emp_id_2,
     initial_response_time, no_of_participants, control_room_on_shore, fire_team_1_size, fire_team_1_duration,
     fire_team_2_size, fire_team_2_duration, stretcher_team_size, maintenance_team_size, snr_team_size,
     snr_team_duration, drill_muster, abandon_muster_offshore, total_time_of_drill, approved_by_oim_fs_emp_id,
     approved_by_companyman, revision_value, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Drill_Record_Hdr_Id, Rig_Id, Drill_Record_Sr_No, Drill_Record_No, Drill_Dt, Drill_Location,
    HSE_Drill_Id_1, HSE_Drill_Id_2, Head_Count, Initiated_By_Fs_Emp_Id_1, Initiated_By_Fs_Emp_Id_2,
    Initial_Response_Time, No_Of_Participants, Control_Room_On_Shore, Fire_Team_1_Size, Fire_Team_1_Duration,
    Fire_Team_2_Size, Fire_Team_2_Duration, Stretcher_Team_Size, Maintenance_Team_Size, SNR_Team_Size,
    SNR_Team_Duration, Drill_Muster, Abandon_Muster_Offshore, Total_Time_Of_Drill, Approved_By_OIM_Fs_Emp_Id,
    Approved_By_Companyman, Revision_Value, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_HSE_Drill_Record_Hdr;
ALTER TABLE serosIT.hse_drill_record_hdr AUTO_INCREMENT = 64;

INSERT INTO serosIT.hse_drill_record_event
    (drill_rec_event_id, drill_record_hdr_id, drill_rec_event_time, drill_rec_event_desc,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Drill_Rec_Event_Id, Drill_Record_Hdr_Id, Drill_Rec_Event_Time, Drill_Rec_Event_Desc,
    Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_HSE_Drill_Record_Event;
ALTER TABLE serosIT.hse_drill_record_event AUTO_INCREMENT = 452;

INSERT INTO serosIT.hse_drill_record_observation
    (drill_rec_observation_id, drill_record_hdr_id, drill_rec_observation_desc,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Drill_Rec_Observation_Id, Drill_Record_Hdr_Id, Drill_Rec_Observation_Desc,
    Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_HSE_Drill_Record_Observation;
ALTER TABLE serosIT.hse_drill_record_observation AUTO_INCREMENT = 127;

INSERT INTO serosIT.hse_drill_record_improvement
    (drill_rec_improvement_id, drill_record_hdr_id, drill_rec_improvement_desc,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Drill_Rec_Improvement_Id, Drill_Record_Hdr_Id, Drill_Rec_Improvement_Desc,
    Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_HSE_Drill_Record_Improvement;
ALTER TABLE serosIT.hse_drill_record_improvement AUTO_INCREMENT = 87;

INSERT INTO serosIT.hse_drill_record_corrective_action
    (drill_rec_corrective_action_id, drill_record_hdr_id, drill_rec_corrective_action_desc,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Drill_Rec_Corrective_Action_Id, Drill_Record_Hdr_Id, Drill_Rec_Corrective_Action_Desc,
    Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_HSE_Drill_Record_Corrective_Action;
ALTER TABLE serosIT.hse_drill_record_corrective_action AUTO_INCREMENT = 91;

INSERT INTO serosIT.hse_drill_record_photo_upload
    (drill_rec_photo_upload_id, drill_record_hdr_id, drill_rec_photo_upload_path, drill_rec_photo_active,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Drill_Rec_Photo_Upload_Id, Drill_Record_Hdr_Id, Drill_Rec_Photo_Upload_Path, Drill_Rec_Photo_Active,
    Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_HSE_Drill_Record_Photo_Upload;
ALTER TABLE serosIT.hse_drill_record_photo_upload AUTO_INCREMENT = 188;

SELECT
    (SELECT COUNT(*) FROM serosIT.hse_drill_record_hdr) AS headers,
    (SELECT COUNT(*) FROM serosIT.hse_drill_record_event) AS events,
    (SELECT COUNT(*) FROM serosIT.hse_drill_record_observation) AS observations,
    (SELECT COUNT(*) FROM serosIT.hse_drill_record_improvement) AS improvements,
    (SELECT COUNT(*) FROM serosIT.hse_drill_record_corrective_action) AS corrective_actions,
    (SELECT COUNT(*) FROM serosIT.hse_drill_record_photo_upload) AS photo_uploads;
