-- Additive migration; preserves existing Stars receipts and immutable ledger.
ALTER TABLE payments ADD COLUMN provider text NOT NULL DEFAULT 'telegram' CHECK(provider IN ('telegram','platega'));
ALTER TABLE payments DROP CONSTRAINT payments_currency_check;
ALTER TABLE payments ADD CONSTRAINT provider_currency CHECK((provider='telegram' AND currency='XTR') OR (provider='platega' AND currency='RUB'));
ALTER TABLE payments ADD COLUMN remote_id uuid UNIQUE;
ALTER TABLE payments ADD COLUMN remote_status text;
ALTER TABLE payments ADD COLUMN checkout_url text;
ALTER TABLE payments ADD COLUMN creation_state text CHECK(creation_state IN ('new','sending','created','uncertain'));
ALTER TABLE payments ADD COLUMN refund_remote_id uuid;
CREATE TABLE payment_callback_events(id bigserial PRIMARY KEY, provider text NOT NULL CHECK(provider='platega'),
 remote_id uuid NOT NULL, status text NOT NULL, received_at timestamptz NOT NULL DEFAULT now());
CREATE FUNCTION preserve_payment_provider() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF NEW.provider<>OLD.provider OR (OLD.remote_id IS NOT NULL AND NEW.remote_id IS DISTINCT FROM OLD.remote_id) THEN RAISE EXCEPTION 'payment provider immutable'; END IF;
 RETURN NEW; END $$;
CREATE TRIGGER payment_provider_guard BEFORE UPDATE ON payments FOR EACH ROW EXECUTE FUNCTION preserve_payment_provider();
