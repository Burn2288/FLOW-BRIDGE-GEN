ALTER TABLE jobs ADD COLUMN provider_request_id text;
ALTER TABLE jobs ADD COLUMN provider_usage_characters bigint CHECK(provider_usage_characters>=0);
CREATE VIEW financial_journal AS SELECT id,user_id,mode,kind,da AS available_delta,dr AS reserved_delta,job_id,payment_id,created_at FROM ledger;
