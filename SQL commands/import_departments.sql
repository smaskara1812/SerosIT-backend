-- Import Mst_Department from the legacy ops-data DB into SerosIT.
-- Preserves the legacy Dept_Id as the primary key, then reseeds
-- AUTO_INCREMENT past the max imported id so future inserts don't collide.

INSERT INTO serosIT.mst_department
    (dept_id, dept_name, dept_dispname, dept_abrv, dept_order, dept_active,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    Dept_Id, Dept_Name, Dept_Dispname, Dept_Abrv, Dept_Order, Dept_Active,
    Cr_User_Id, Cr_Dt, Mod_User_Id, Mod_Dt
FROM Seros_Data.Mst_Department;

SET @next_id = (SELECT MAX(dept_id) + 1 FROM serosIT.mst_department);
SET @sql = CONCAT('ALTER TABLE serosIT.mst_department AUTO_INCREMENT = ', @next_id);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT COUNT(*) AS imported_departments FROM serosIT.mst_department;
