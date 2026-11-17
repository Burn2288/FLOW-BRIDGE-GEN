CREATE TABLE users(id uuid PRIMARY KEY, blocked boolean NOT NULL DEFAULT false, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE identities(platform text NOT NULL CHECK(platform IN ('telegram','max')), external_id bigint NOT NULL,
 user_id uuid NOT NULL REFERENCES users, terms_version text, accepted_at timestamptz, PRIMARY KEY(platform,external_id));
CREATE TABLE wallets(user_id uuid REFERENCES users, mode text CHECK(mode IN ('demo','live')),
 available bigint NOT NULL DEFAULT 0 CHECK(available>=0), reserved bigint NOT NULL DEFAULT 0 CHECK(reserved>=0), PRIMARY KEY(user_id,mode));
CREATE TABLE settings(id int PRIMARY KEY CHECK(id=1), halted boolean NOT NULL DEFAULT false);
INSERT INTO settings(id) VALUES(1);
CREATE TABLE budgets(day date PRIMARY KEY, used bigint NOT NULL DEFAULT 0 CHECK(used>=0));
CREATE TABLE quotes(id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES users, mode text NOT NULL CHECK(mode IN ('demo','live')),
 text_content text, voice text NOT NULL, speed numeric NOT NULL CHECK(speed IN (0.9,1.0,1.1)),
 price bigint NOT NULL CHECK(price>0), cost_bound bigint NOT NULL CHECK(cost_bound>0), tariff text NOT NULL,
 expires_at timestamptz NOT NULL DEFAULT now()+interval '10 minutes', created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE jobs(id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES users, quote_id uuid NOT NULL UNIQUE REFERENCES quotes,
 mode text NOT NULL CHECK(mode IN ('demo','live')), price bigint NOT NULL CHECK(price>0), cost_bound bigint NOT NULL,
 budget_day date NOT NULL REFERENCES budgets, status text NOT NULL CHECK(status IN ('queued','dispatching','uncertain','succeeded','failed','cancelled')),
 settlement text CHECK(settlement IN ('capture','release')), fence uuid, lease_until timestamptz,
 error_code text, created_at timestamptz NOT NULL DEFAULT now(), completed_at timestamptz);
CREATE UNIQUE INDEX active_user ON jobs(user_id) WHERE status IN ('queued','dispatching','uncertain');
CREATE INDEX queue ON jobs(created_at) WHERE status='queued';
CREATE TABLE payments(id uuid PRIMARY KEY,user_id uuid NOT NULL REFERENCES users,amount bigint NOT NULL CHECK(amount>0),
 credits bigint NOT NULL CHECK(credits>0),currency text NOT NULL CHECK(currency='XTR'),tariff text NOT NULL,
 charge_id text UNIQUE, status text NOT NULL CHECK(status IN ('pending','succeeded','refunding','refunded','review')),
 created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE ledger(id uuid PRIMARY KEY,user_id uuid NOT NULL REFERENCES users,mode text NOT NULL CHECK(mode IN ('demo','live')),
 event_key text NOT NULL UNIQUE,kind text NOT NULL CHECK(kind IN ('demo_grant','payment','reserve','capture','release','refund_hold','refund_release','refund')),
 da bigint NOT NULL,dr bigint NOT NULL,job_id uuid REFERENCES jobs,payment_id uuid REFERENCES payments,
 created_at timestamptz NOT NULL DEFAULT now(),FOREIGN KEY(user_id,mode) REFERENCES wallets,
 CHECK(da<>0 OR dr<>0),CHECK((kind='reserve' AND da<0 AND dr=-da AND job_id IS NOT NULL)
 OR (kind='capture' AND da=0 AND dr<0 AND job_id IS NOT NULL)
 OR (kind='release' AND da>0 AND dr=-da AND job_id IS NOT NULL)
 OR (kind IN ('demo_grant','payment') AND da>0 AND dr=0)
 OR (kind='refund_hold' AND da<0 AND dr=-da AND payment_id IS NOT NULL)
 OR (kind='refund_release' AND da>0 AND dr=-da AND payment_id IS NOT NULL)
 OR (kind='refund' AND da=0 AND dr<0 AND payment_id IS NOT NULL)),
 CHECK(kind<>'demo_grant' OR mode='demo'), CHECK(kind NOT IN ('payment','refund','refund_hold','refund_release') OR mode='live'));
CREATE UNIQUE INDEX one_settlement ON ledger(job_id) WHERE kind IN ('capture','release');
CREATE UNIQUE INDEX one_reserve ON ledger(job_id) WHERE kind='reserve';
CREATE UNIQUE INDEX one_payment_credit ON ledger(payment_id) WHERE kind='payment';
CREATE FUNCTION immutable_row() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable ledger'; END $$;
CREATE TRIGGER ledger_immutable BEFORE UPDATE OR DELETE ON ledger FOR EACH ROW EXECUTE FUNCTION immutable_row();
CREATE FUNCTION apply_movement() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF NEW.job_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM jobs WHERE id=NEW.job_id AND user_id=NEW.user_id AND mode=NEW.mode AND price=greatest(abs(NEW.da),abs(NEW.dr))) THEN RAISE EXCEPTION 'job movement mismatch'; END IF;
 IF NEW.payment_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM payments WHERE id=NEW.payment_id AND user_id=NEW.user_id AND credits=greatest(abs(NEW.da),abs(NEW.dr))) THEN RAISE EXCEPTION 'payment movement mismatch'; END IF;
 UPDATE wallets SET available=available+NEW.da,reserved=reserved+NEW.dr WHERE user_id=NEW.user_id AND mode=NEW.mode;
 IF NOT FOUND THEN RAISE EXCEPTION 'wallet missing'; END IF; RETURN NEW;
END $$;
CREATE TRIGGER movement AFTER INSERT ON ledger FOR EACH ROW EXECUTE FUNCTION apply_movement();
CREATE FUNCTION verify_wallet() RETURNS trigger LANGUAGE plpgsql AS $$ DECLARE a bigint;r bigint; BEGIN
 SELECT coalesce(sum(da),0),coalesce(sum(dr),0) INTO a,r FROM ledger WHERE user_id=NEW.user_id AND mode=NEW.mode;
 IF NOT EXISTS(SELECT 1 FROM wallets WHERE user_id=NEW.user_id AND mode=NEW.mode AND available=a AND reserved=r) THEN RAISE EXCEPTION 'wallet ledger mismatch'; END IF; RETURN NULL; END $$;
CREATE CONSTRAINT TRIGGER wallet_consistent AFTER INSERT OR UPDATE ON wallets DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION verify_wallet();
CREATE FUNCTION verify_job() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF NEW.status IN ('succeeded','failed','cancelled') AND (NEW.settlement IS NULL OR NOT EXISTS(SELECT 1 FROM ledger WHERE job_id=NEW.id AND kind=NEW.settlement)) THEN RAISE EXCEPTION 'missing settlement'; END IF;
 IF NEW.status='succeeded' AND NEW.settlement IS DISTINCT FROM 'capture' THEN RAISE EXCEPTION 'bad success'; END IF;
 IF NEW.status IN ('failed','cancelled') AND NEW.settlement IS DISTINCT FROM 'release' THEN RAISE EXCEPTION 'bad failure'; END IF;
 IF OLD.settlement IS NOT NULL AND (NEW.settlement IS DISTINCT FROM OLD.settlement OR NEW.status IS DISTINCT FROM OLD.status) THEN RAISE EXCEPTION 'settled job immutable'; END IF;
 RETURN NEW; END $$;
CREATE TRIGGER job_consistent BEFORE UPDATE ON jobs FOR EACH ROW EXECUTE FUNCTION verify_job();
CREATE TABLE files(job_id uuid PRIMARY KEY REFERENCES jobs, storage_key text NOT NULL UNIQUE,sha256 text NOT NULL,size bigint NOT NULL CHECK(size>0),expires_at timestamptz NOT NULL,deleted_at timestamptz);
CREATE TABLE deliveries(job_id uuid PRIMARY KEY REFERENCES jobs,status text NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','sending','sent','retry','expired')),
 attempts int NOT NULL DEFAULT 0,next_at timestamptz NOT NULL DEFAULT now(),fence uuid,lease_until timestamptz,platform_message_id bigint);
CREATE TABLE conversations(user_id uuid PRIMARY KEY REFERENCES users,step text NOT NULL DEFAULT 'home',text_content text,voice text,speed numeric NOT NULL DEFAULT 1.0);
CREATE TABLE rate_limits(user_id uuid REFERENCES users,minute timestamptz,n int NOT NULL,PRIMARY KEY(user_id,minute));
CREATE TABLE inbox(update_id bigint PRIMARY KEY,payload jsonb NOT NULL,done boolean NOT NULL DEFAULT false,created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE poll_state(id int PRIMARY KEY CHECK(id=1),offset_id bigint NOT NULL DEFAULT 0);INSERT INTO poll_state(id) VALUES(1);
CREATE TABLE audit_events(id bigserial PRIMARY KEY,action text NOT NULL,target uuid,created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE heartbeat(component text PRIMARY KEY,seen_at timestamptz NOT NULL DEFAULT now());
