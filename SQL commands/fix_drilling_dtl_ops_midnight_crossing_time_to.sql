-- Fixes a real, pre-existing legacy data quirk affecting 3,467 of 38,898
-- imported Drilling_Dtl_Ops rows (8.9%): for any shift crossing midnight
-- (e.g. 22:30 -> 00:00), the legacy source stored Time_To on the SAME
-- calendar date as Time_From instead of rolling over to the next day —
-- even though Duration was always computed correctly assuming that
-- rollover (verified: 0 mismatches between stored Duration and
-- (Time_To + 1 day - Time_From) across every affected row before this fix
-- ran). This raw-timestamp inconsistency only surfaced once the app added
-- real "Time To must be after Time From" validation on save (something the
-- legacy system never enforced) — editing an unrelated field on any
-- Drilling_Dtl whose Ops includes one of these rows would fail validation
-- on a row the user never touched, since the whole Ops array is resent on
-- every save.
--
-- This aligns every affected row with the same next-day-rollover
-- convention the frontend's own toIso() already uses for newly-entered
-- rows, rather than special-casing the validation to tolerate bad data
-- forever.

UPDATE serosIT.drilling_dtl_ops
SET time_to = time_to + INTERVAL 1 DAY
WHERE time_to <= time_from;
