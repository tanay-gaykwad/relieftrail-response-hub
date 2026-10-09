-- Reporting view: response-level totals without storing duplicate aggregates.
SELECT code, title, status, organization_name, contributions, disbursements,
       contributions - disbursements AS recorded_net
FROM response_funding_summary
ORDER BY title;

-- Join reported entries to response, organization and source context.
SELECT r.code, r.title, o.name AS organization, f.record_type, f.amount,
       f.currency, f.recorded_on, f.reference, s.name AS source
FROM funding_records f
JOIN responses r ON r.id = f.response_id
JOIN organizations o ON o.id = r.organization_id
JOIN funding_sources s ON s.id = f.source_id
ORDER BY f.recorded_on DESC;

-- Review open items with any associated funding record.
SELECT i.issue_type, i.description, r.code, f.reference, f.amount, f.currency
FROM reconciliation_issues i
JOIN responses r ON r.id = i.response_id
LEFT JOIN funding_records f ON f.id = i.funding_record_id
WHERE i.status = 'open'
ORDER BY i.created_at;

-- Example response creation. The API also writes its audit event in the same transaction.
BEGIN;
INSERT INTO responses(organization_id, code, title, location, summary, status)
VALUES (1, 'DEMO-26-99', 'Fictional Example Response', 'Example Ward',
        'A fictional response record for practicing SQL inserts.', 'draft');
COMMIT;

-- Re-import guard: the database unique constraint means this source item can be added once.
INSERT INTO funding_records(response_id, source_id, record_type, amount, currency,
                            recorded_on, reference, source_reference)
VALUES (1, 2, 'contribution', 10.00, 'USD', CURRENT_DATE,
        'EXAMPLE-REF', 'EXAMPLE-SOURCE-ID')
ON CONFLICT (response_id, source_id, source_reference) DO NOTHING;

