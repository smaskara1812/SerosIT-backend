-- Backfills the Business_System_Id_N "Extended to" flags onto mst_emp_type
-- — these columns were added to the model after the original bulk-migration
-- import, so they need a separate pass rather than being part of that
-- INSERT. Idempotent: safe to re-run, always sets to the current legacy
-- value.

UPDATE serosIT.mst_emp_type se
JOIN Seros_Data.Mst_Emp_Type le ON le.emp_type_id = se.emp_type_id
SET se.business_system_id_2 = le.Business_System_Id_2,
    se.business_system_id_5 = le.Business_System_Id_5,
    se.business_system_id_6 = le.Business_System_Id_6,
    se.business_system_id_11 = le.Business_System_Id_11,
    se.business_system_id_16 = le.Business_System_Id_16;
