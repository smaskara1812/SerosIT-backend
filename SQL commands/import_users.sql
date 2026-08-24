-- Import Mst_User from the legacy ops-data DB into SerosIT.
--
-- The test rows created during dev (jdoe, asmith, and your own smaskara /
-- sbodake accounts under fake local ids 3/4) collide with real legacy data:
--   - USER_ID 1-4 are already real legacy users (jagdish_j, moraesr, ...)
--   - smaskara/sbodake exist for real under USER_ID 28262/28073
-- so the test rows have to go before this import, or it fails on the PK /
-- unique(user_login_id) constraints. This wipes mst_user and everything
-- keyed off it (local passwords, admin/permission profiles) — all of it is
-- throwaway test data, not anything imported or real.

SET SQL_SAFE_UPDATES = 0;

DELETE FROM serosIT.mst_user_password;
DELETE FROM serosIT.sys_user_permissions;
DELETE FROM serosIT.sys_user_profile;
DELETE FROM serosIT.mst_user;

SET SQL_SAFE_UPDATES = 1;

-- Without this, MySQL treats an explicit 0 in an AUTO_INCREMENT column the
-- same as NULL and silently generates a new value instead — and the source
-- data has exactly one such row: USER_ID 0, a legacy "System" placeholder
-- user, which needs to import as literally 0, not some new auto value.
SET SESSION sql_mode = CONCAT(@@sql_mode, ',NO_AUTO_VALUE_ON_ZERO');

INSERT INTO serosIT.mst_user
    (user_id, user_name, emp_id, nonemp_id, dept_id, user_login_id,
     user_active, user_type_id, mac_address, user_from, user_to, user_email,
     cr_user_id, cr_dt, mod_user_id, mod_dt)
SELECT
    USER_ID, USER_NAME, EMP_ID, NONEMP_ID, DEPT_ID, USER_LOGIN_ID,
    USER_ACTIVE, USER_TYPE_ID, MAC_ADDRESS, USER_FROM, USER_TO, USER_EMAIL,
    CR_USER_ID, CR_DT, MOD_USER_ID, MOD_DT
FROM Seros_Data.Mst_User;

SET @next_id = (SELECT MAX(user_id) + 1 FROM serosIT.mst_user);
SET @sql = CONCAT('ALTER TABLE serosIT.mst_user AUTO_INCREMENT = ', @next_id);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT COUNT(*) AS imported_users FROM serosIT.mst_user;
