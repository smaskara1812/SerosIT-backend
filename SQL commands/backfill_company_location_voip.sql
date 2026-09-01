-- Backfills Company_Loc_VOIP_Code onto mst_company_location — added to
-- the model after the original import_general_masters.sql run (see
-- docs/migration_map.md), so it needed a separate pass rather than being
-- part of that INSERT.
-- Idempotent: safe to re-run, always sets to the current legacy value.

UPDATE serosIT.mst_company_location sc
JOIN Seros_Data.Mst_Company_Location lc ON lc.Company_Loc_Id = sc.company_loc_id
SET sc.company_loc_voip_code = lc.Company_Loc_VOIP_Code;
