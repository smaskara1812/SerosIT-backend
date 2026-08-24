INSERT INTO serosIT.rank_classification
    (rank_id, rank_class, cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT c.Rank_Id,
       IF(c.Rank_Class = 'Senior', 'S', 'J'),
       c.Cr_User_Id, c.Cr_Dt, c.Mod_User_Id, c.Mod_Dt
FROM Seros_Data.eos_Rank_Classification c
INNER JOIN (
    SELECT Rank_Id, MAX(Cr_Dt) AS max_cr_dt
    FROM Seros_Data.eos_Rank_Classification
    GROUP BY Rank_Id
) latest ON c.Rank_Id = latest.Rank_Id AND c.Cr_Dt = latest.max_cr_dt;

SELECT COUNT(*) FROM serosIT.rank_classification;
SELECT rank_class, COUNT(*) FROM serosIT.rank_classification GROUP BY rank_class;
