-- Populates mst_hse_drill from the legacy Mst_HSE_Drill table — HSE
-- Drills/Exercises' "Type of Drill/Training" master. rig_type_id already
-- matches between the two schemas (1=Offshore Rig, 2=Onshore Rig — same
-- ids as serosIT.mst_rig_type), so it's a straight passthrough.

INSERT INTO serosIT.mst_hse_drill
    (hse_drill_id, hse_drill_name, hse_drill_frequency, rig_type_id, hse_drill_active,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    HSE_Drill_Id, HSE_Drill_Name, HSE_Drill_Frequency, Rig_Type_Id, HSE_Drill_Active,
    Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Mst_HSE_Drill;

ALTER TABLE serosIT.mst_hse_drill AUTO_INCREMENT = 27;

SELECT COUNT(*) FROM serosIT.mst_hse_drill;
