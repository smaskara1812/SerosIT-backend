-- Populates mst_relation_dtl from the legacy Mst_Relation_Dtl table — a
-- brand-new table in this app, no prior import_*.sql this rides along with.

INSERT INTO serosIT.mst_relation_dtl
    (relation_id, relation, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    relation_id,
    relation,
    CR_USER_ID,
    CR_DT,
    MOD_USER_ID,
    MOD_DT
FROM Seros_Data.Mst_Relation_Dtl;
