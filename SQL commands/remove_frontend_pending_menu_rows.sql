DELETE FROM serosIT.sys_menu WHERE menu_key IN (
    'masters.continents', 'masters.countries', 'masters.country_states', 'masters.vessel_depts',
    'masters.rig_types', 'masters.rig_subtypes'
);

SELECT menu_key FROM serosIT.sys_menu WHERE menu_key IN (
    'masters.continents', 'masters.countries', 'masters.country_states', 'masters.vessel_depts',
    'masters.rig_types', 'masters.rig_subtypes'
);
