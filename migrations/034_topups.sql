CREATE TABLE topup_settings (
 id int PRIMARY KEY CHECK(id=1),
 custom_enabled boolean NOT NULL DEFAULT true,
 minimum bigint NOT NULL DEFAULT 5000 CHECK(minimum>0),
 maximum bigint NOT NULL DEFAULT 10000000 CHECK(maximum>=minimum),
 revision bigint NOT NULL DEFAULT 1
);
INSERT INTO topup_settings(id) VALUES(1);
CREATE TABLE topup_presets (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 amount bigint NOT NULL CHECK(amount>0 AND amount<=1000000000),
 enabled boolean NOT NULL DEFAULT true,
 position bigint NOT NULL DEFAULT 0
);
INSERT INTO topup_presets(amount,position) VALUES(5000,10),(10000,20),(20000,30);

CREATE TABLE topup_orders (
 payment_id uuid PRIMARY KEY REFERENCES payments,
 user_id uuid NOT NULL REFERENCES users,
 chat_id bigint NOT NULL CHECK(chat_id>0),
 request_key text NOT NULL,
 mode text NOT NULL CHECK(mode IN ('demo','live')),
 merchant_id uuid NOT NULL,
 rate_tokens numeric NOT NULL CHECK(rate_tokens>0),
 rate_rubles numeric NOT NULL CHECK(rate_rubles>0),
 state text NOT NULL DEFAULT 'new' CHECK(state IN (
  'new','creating','unknown','pending','paid','cancelled','expired','error','review','refunded'
 )),
 expires_at timestamptz NOT NULL DEFAULT now()+interval '15 minutes',
 next_check_at timestamptz NOT NULL DEFAULT now(),
 returned_minor bigint NOT NULL DEFAULT 0 CHECK(returned_minor>=0),
 returned_tokens bigint NOT NULL DEFAULT 0 CHECK(returned_tokens>=0),
 notice_at timestamptz NOT NULL DEFAULT now(),
 notice_state text NOT NULL DEFAULT 'none' CHECK(notice_state IN ('none','pending','sending','sent','unknown')),
 last_error text,
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(user_id,request_key)
);
CREATE TABLE topup_adjustments (
 payment_id uuid NOT NULL REFERENCES topup_orders,
 returned_minor bigint NOT NULL,
 tokens bigint NOT NULL CHECK(tokens>=0),
 debited bigint NOT NULL CHECK(debited>=0),
 debt bigint NOT NULL CHECK(debt>=0),
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(payment_id,returned_minor)
);
CREATE TRIGGER topup_adjustments_immutable BEFORE UPDATE OR DELETE ON topup_adjustments
 FOR EACH ROW EXECUTE FUNCTION immutable_row();
CREATE TABLE wallet_debts (
 user_id uuid NOT NULL,
 mode text NOT NULL,
 amount bigint NOT NULL DEFAULT 0 CHECK(amount>=0),
 PRIMARY KEY(user_id,mode),
 FOREIGN KEY(user_id,mode) REFERENCES wallets
);
CREATE INDEX topup_pending_checks ON topup_orders(next_check_at);
ALTER TABLE ledger DROP CONSTRAINT ledger_kind_check;
ALTER TABLE ledger ADD CONSTRAINT ledger_kind_check CHECK(kind IN (
 'demo_grant','pilot_grant','payment','reserve','capture','release','refund_hold','refund_release','refund',
 'task_reserve','task_capture','task_release','topup','topup_reversal','topup_debt_repay'));
ALTER TABLE ledger DROP CONSTRAINT ledger_movement_shape;
ALTER TABLE ledger ADD CONSTRAINT ledger_movement_shape CHECK(
 task_quote_id IS NOT NULL
 OR (kind='reserve' AND da<0 AND dr=-da AND job_id IS NOT NULL)
 OR (kind='capture' AND da=0 AND dr<0 AND job_id IS NOT NULL)
 OR (kind='release' AND da>0 AND dr=-da AND job_id IS NOT NULL)
 OR (kind IN ('demo_grant','payment') AND da>0 AND dr=0)
 OR (kind='pilot_grant' AND mode='live' AND da BETWEEN 1 AND 3000 AND dr=0 AND job_id IS NULL AND payment_id IS NULL)
 OR (kind='refund_hold' AND da<0 AND dr=-da AND payment_id IS NOT NULL)
 OR (kind='refund_release' AND da>0 AND dr=-da AND payment_id IS NOT NULL)
 OR (kind='refund' AND da=0 AND dr<0 AND payment_id IS NOT NULL)
 OR (kind='topup' AND da>0 AND dr=0 AND payment_id IS NOT NULL AND job_id IS NULL)
 OR (kind IN ('topup_reversal','topup_debt_repay') AND da<0 AND dr=0 AND payment_id IS NOT NULL AND job_id IS NULL)
);
CREATE UNIQUE INDEX one_topup_credit ON ledger(payment_id) WHERE kind='topup';

CREATE OR REPLACE FUNCTION apply_movement() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.job_id IS NOT NULL AND NOT EXISTS(
  SELECT 1 FROM jobs WHERE id=NEW.job_id AND user_id=NEW.user_id AND mode=NEW.mode
   AND price=greatest(abs(NEW.da),abs(NEW.dr))
 ) THEN RAISE EXCEPTION 'job movement mismatch'; END IF;
 IF NEW.kind IN ('topup','topup_reversal','topup_debt_repay') THEN
  IF NOT EXISTS (
   SELECT 1 FROM payments p JOIN topup_orders t ON t.payment_id=p.id
   WHERE p.id=NEW.payment_id AND p.user_id=NEW.user_id AND t.mode=NEW.mode
    AND t.user_id=NEW.user_id AND abs(NEW.da)<=p.credits
    AND (NEW.kind<>'topup' OR NEW.da=p.credits)
  ) THEN RAISE EXCEPTION 'topup movement mismatch'; END IF;
 ELSIF NEW.payment_id IS NOT NULL AND NOT EXISTS(
  SELECT 1 FROM payments WHERE id=NEW.payment_id AND user_id=NEW.user_id
   AND credits=greatest(abs(NEW.da),abs(NEW.dr))
 ) THEN RAISE EXCEPTION 'payment movement mismatch'; END IF;
 UPDATE wallets SET available=available+NEW.da,reserved=reserved+NEW.dr
  WHERE user_id=NEW.user_id AND mode=NEW.mode;
 IF NOT FOUND THEN RAISE EXCEPTION 'wallet missing'; END IF;
 RETURN NEW;
END $$;
CREATE FUNCTION preserve_topup_terms() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF (NEW.payment_id,NEW.user_id,NEW.chat_id,NEW.mode,NEW.merchant_id,NEW.rate_tokens,NEW.rate_rubles,NEW.request_key)
  IS DISTINCT FROM
  (OLD.payment_id,OLD.user_id,OLD.chat_id,OLD.mode,OLD.merchant_id,OLD.rate_tokens,OLD.rate_rubles,OLD.request_key)
 THEN RAISE EXCEPTION 'topup terms immutable'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER topup_terms_immutable BEFORE UPDATE ON topup_orders
 FOR EACH ROW EXECUTE FUNCTION preserve_topup_terms();


CREATE OR REPLACE FUNCTION preserve_payment_provider() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.provider<>OLD.provider OR (OLD.remote_id IS NOT NULL AND NEW.remote_id IS DISTINCT FROM OLD.remote_id)
 THEN RAISE EXCEPTION 'payment provider immutable'; END IF;
 IF EXISTS(SELECT 1 FROM topup_orders WHERE payment_id=OLD.id)
  AND (NEW.user_id,NEW.amount,NEW.credits,NEW.currency,NEW.tariff)
   IS DISTINCT FROM (OLD.user_id,OLD.amount,OLD.credits,OLD.currency,OLD.tariff)
 THEN RAISE EXCEPTION 'topup payment terms immutable'; END IF;
 RETURN NEW;
END $$;
