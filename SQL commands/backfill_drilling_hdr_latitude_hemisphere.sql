-- Backfills the missing hemisphere suffix on drilling_hdr.latitude — legacy
-- never actually wrote one for Latitude on any row (see DrillingHdr's model
-- docstring), even though every one of Seros' drilling operations (India,
-- Vietnam, Indonesia) sits in the Northern Hemisphere. Idempotent: only
-- touches rows that don't already end in N or S.

UPDATE serosIT.drilling_hdr
SET latitude = CONCAT(latitude, 'N')
WHERE latitude NOT LIKE '%N' AND latitude NOT LIKE '%S';
