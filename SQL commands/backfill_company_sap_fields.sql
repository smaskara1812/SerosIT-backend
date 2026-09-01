-- Backfills SAP_Company/Cost_Center/Payroll_Area/Personnel_Area onto
-- mst_company — these columns were added to the model after the original
-- import_general_masters.sql run (see docs/migration_map.md), so they
-- needed a separate pass rather than being part of that INSERT.
-- Idempotent: safe to re-run, always sets to the current legacy value.

UPDATE serosIT.mst_company sc
JOIN Seros_Data.Mst_Company lc ON lc.COMPANY_ID = sc.company_id
SET sc.sap_company = lc.SAP_Company,
    sc.cost_center = lc.Cost_Center,
    sc.payroll_area = lc.Payroll_Area,
    sc.personnel_area = lc.Personnel_Area;
