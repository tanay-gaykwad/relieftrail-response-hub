INSERT INTO organizations(name,kind) VALUES
('ReliefTrail Demo Network','local_ngo'),
('Community Response Collective','community_group');

INSERT INTO responses(organization_id,code,title,location,summary,status,start_date) VALUES
(1,'FLOOD-26-01','River District Flood Response','River District','Fictional emergency response supporting temporary shelter and essential supplies.','approved','2026-09-18'),
(1,'HEAT-26-02','Community Heat Support','North Ward','Fictional response coordinating cooling spaces and water access.','in_review','2026-10-02'),
(2,'STORM-26-03','Coastal Storm Preparedness','Coastal Ward','Fictional preparedness response for local community groups.','draft','2026-10-06');

INSERT INTO funding_sources(name,source_type) VALUES
('Manual entry','manual'),('Demo partner CSV','csv_import'),('ReliefTrail contract demo','blockchain');

INSERT INTO funding_records(response_id,source_id,record_type,amount,currency,recorded_on,reference,description,source_reference) VALUES
(1,2,'contribution',12500.00,'USD','2026-09-19','PARTNER-0921','Fictional partner funding batch','DEMO-CSV-001'),
(1,3,'contribution',4200.00,'USD','2026-09-22','CHAIN-0XA31','Simulated contract event; not real funds','0xa31-demo'),
(1,1,'disbursement',3800.00,'USD','2026-09-24','PAY-1048','Fictional supply vendor payment record','DEMO-PAY-1048'),
(1,2,'contribution',6500.00,'USD','2026-10-01','PARTNER-1001','Fictional partner funding batch','DEMO-CSV-002'),
(2,2,'contribution',7200.00,'USD','2026-10-03','PARTNER-1003','Fictional restricted grant record','DEMO-CSV-003'),
(2,1,'disbursement',1250.00,'USD','2026-10-04','PAY-2204','Fictional logistics cost record','DEMO-PAY-2204'),
(1,1,'disbursement',900.00,'USD','2026-10-05','PAY-1053','Fictional transport cost record','DEMO-PAY-1053');

INSERT INTO reconciliation_issues(response_id,funding_record_id,issue_type,description) VALUES
(1,3,'needs_review','Confirm supporting reference for this fictional disbursement.'),
(2,5,'missing_reference','Partner batch needs a source document reference before report approval.'),
(2,6,'possible_duplicate','Review this payment reference against the partner statement.');

INSERT INTO import_batches(organization_id,source_name,file_name,rows_received,rows_imported,rows_skipped,status)
VALUES (1,'CSV upload','partner-october-demo.csv',4,3,1,'completed_with_skips');

INSERT INTO audit_events(organization_id,action,entity_type,entity_id,actor_label,details) VALUES
(1,'seeded','workspace',1,'Demo system','{"note":"Fictional sample history for portfolio walkthrough"}'),
(1,'imported','funding_batch',1,'Demo operator','{"source":"Demo partner CSV","rows":4}'),
(1,'flagged','reconciliation_issue',1,'Demo system','{"reason":"Missing supporting reference"}');

