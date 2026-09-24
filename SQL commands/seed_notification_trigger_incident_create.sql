-- Wires the QHSE Incident Details "create" action to legacy Mail_Alert_Dtl
-- Alert_Id 240 ("Incident Report Added") via the new generic
-- notification_trigger table — see core/notification_triggers.py. This is
-- config, not code: entity_key/action match IncidentDetailViewSet's own
-- entity_key ("qhse.incident_details") and the perform_create hook's
-- action string ("create").

INSERT INTO serosIT.notification_trigger
    (entity_key, action, alert_id, notification_trigger_active, cr_user_id, cr_dt)
VALUES
    ('qhse.incident_details', 'create', 240, 'Y', 1, NOW());

SELECT * FROM serosIT.notification_trigger;
