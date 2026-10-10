INSERT INTO organizations(name,kind) VALUES
('ReliefTrail Demo Network','local_ngo'),
('Community Response Collective','community_group');

INSERT INTO responses(organization_id,code,title,location,summary,status,start_date) VALUES
(1,'FLOOD-26-01','River District Flood Response','River District','Fictional emergency response supporting temporary shelter and essential supplies.','approved','2026-09-18'),
(1,'HEAT-26-02','Community Heat Support','North Ward','Fictional response coordinating cooling spaces and water access.','approved','2026-10-02'),
(2,'STORM-26-03','Coastal Storm Preparedness','Coastal Ward','Fictional preparedness response for local community groups.','draft','2026-10-06');

-- Seed only a fictional demo account; the API replaces this PBKDF2 hash during demo startup.
INSERT INTO users(email,full_name,password_hash) VALUES
('admin@relieftrail.test','Jamie Davis','pbkdf2_sha256$_0zuHb5qS-C2fO5vu_Ow2g==$5biVGq4E47Kz2uiLtwSg5Cg-4a69Fzf-NL9eFPCxq-M=')
ON CONFLICT(email) DO NOTHING;

INSERT INTO funders(organization_id,name,kind) VALUES
(1,'Northstar Relief Foundation','foundation'),
(1,'Civic Resilience Fund','government'),
(2,'Coastal Community Trust','institutional_donor');

INSERT INTO funding_awards(organization_id,funder_id,award_code,title,total_amount,currency,start_date,end_date,restricted_purpose,status,created_by)
SELECT 1,f.id,'NORTH-26-01','River District emergency response grant',25000.00,'USD','2026-09-18','2027-03-31',
       'Shelter, essential supplies, and transport for the River District response. Fictional portfolio sample.',
       'active',(SELECT id FROM users WHERE email='admin@relieftrail.test')
FROM funders f WHERE f.organization_id=1 AND f.name='Northstar Relief Foundation';
INSERT INTO funding_awards(organization_id,funder_id,award_code,title,total_amount,currency,start_date,end_date,restricted_purpose,status,created_by)
SELECT 1,f.id,'CIVIC-26-02','Community heat support award',14000.00,'USD','2026-10-02','2027-01-31',
       'Cooling spaces and water access for the North Ward response. Fictional portfolio sample.',
       'active',(SELECT id FROM users WHERE email='admin@relieftrail.test')
FROM funders f WHERE f.organization_id=1 AND f.name='Civic Resilience Fund';

INSERT INTO award_allocations(organization_id,award_id,response_id,category,budget_amount)
SELECT 1,a.id,r.id,b.category,b.amount
FROM (VALUES ('NORTH-26-01','FLOOD-26-01','Shelter and supplies',15000.00::numeric),
             ('NORTH-26-01','FLOOD-26-01','Transport and logistics',10000.00::numeric),
             ('CIVIC-26-02','HEAT-26-02','Water access',7000.00::numeric),
             ('CIVIC-26-02','HEAT-26-02','Cooling spaces',7000.00::numeric)) AS b(award_code,response_code,category,amount)
JOIN funding_awards a ON a.award_code=b.award_code AND a.organization_id=1
JOIN responses r ON r.code=b.response_code AND r.organization_id=1;

INSERT INTO reporting_milestones(organization_id,award_id,period_start,period_end,due_date,report_type,status)
SELECT 1,a.id,'2026-09-18','2026-10-31','2026-11-15','financial','upcoming'
FROM funding_awards a WHERE a.award_code='NORTH-26-01' AND a.organization_id=1;
INSERT INTO reporting_milestones(organization_id,award_id,period_start,period_end,due_date,report_type,status)
SELECT 1,a.id,'2026-10-02','2026-10-31','2026-11-20','programmatic','upcoming'
FROM funding_awards a WHERE a.award_code='CIVIC-26-02' AND a.organization_id=1;

INSERT INTO funding_sources(name,source_type) VALUES
('Manual entry','manual'),('Demo partner CSV','csv_import'),('ReliefTrail contract demo','blockchain');

INSERT INTO funding_records(response_id,award_allocation_id,source_id,record_type,amount,currency,recorded_on,reference,description,source_reference) VALUES
(1,NULL,2,'contribution',12500.00,'USD','2026-09-19','PARTNER-0921','Fictional partner funding batch','DEMO-CSV-001'),
(1,NULL,3,'contribution',4200.00,'USD','2026-09-22','CHAIN-0XA31','Simulated contract event; not real funds','0xa31-demo'),
(1,(SELECT id FROM award_allocations WHERE category='Shelter and supplies' AND award_id=(SELECT id FROM funding_awards WHERE award_code='NORTH-26-01')),1,'disbursement',3800.00,'USD','2026-09-24','PAY-1048','Fictional supply vendor payment record','DEMO-PAY-1048'),
(1,NULL,2,'contribution',6500.00,'USD','2026-10-01','PARTNER-1001','Fictional partner funding batch','DEMO-CSV-002'),
(2,NULL,2,'contribution',7200.00,'USD','2026-10-03','PARTNER-1003','Fictional restricted grant record','DEMO-CSV-003'),
(2,(SELECT id FROM award_allocations WHERE category='Cooling spaces' AND award_id=(SELECT id FROM funding_awards WHERE award_code='CIVIC-26-02')),1,'disbursement',1250.00,'USD','2026-10-04','PAY-2204','Fictional logistics cost record','DEMO-PAY-2204'),
(1,(SELECT id FROM award_allocations WHERE category='Transport and logistics' AND award_id=(SELECT id FROM funding_awards WHERE award_code='NORTH-26-01')),1,'disbursement',900.00,'USD','2026-10-05','PAY-1053','Fictional transport cost record','DEMO-PAY-1053');

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
