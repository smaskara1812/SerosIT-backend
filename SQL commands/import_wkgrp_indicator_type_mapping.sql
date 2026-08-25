INSERT INTO serosIT.mst_workgroup
    (workgroup_id, workgroup_name, workgroup_order, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT Workgroup_Id, Workgroup_Name, Workgroup_Order, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Mst_Workgroup;
ALTER TABLE serosIT.mst_workgroup AUTO_INCREMENT = 4;

INSERT INTO serosIT.wkgrp_indicator_type_mapping
    (wkgrp_ind_type_map_id, workgroup_id, indicator_type_id, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT Wkgrp_Ind_Type_Map_Id, Workgroup_Id, Indicator_Type_Id, Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.eos_Wkgrp_Indicator_Type_Mapping;
ALTER TABLE serosIT.wkgrp_indicator_type_mapping AUTO_INCREMENT = 45;

SELECT COUNT(*) FROM serosIT.mst_workgroup;
SELECT COUNT(*) FROM serosIT.wkgrp_indicator_type_mapping;
