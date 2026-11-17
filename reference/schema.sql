-- PostgreSQL initial design. Application transactions and production migrations required.
BEGIN;
CREATE TABLE users (
 id uuid PRIMARY KEY, blocked boolean NOT NULL DEFAULT false,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE identities (
 id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES users(id),
 platform text NOT NULL CHECK(platform IN ('telegram','max')),
 external_user_id text NOT NULL, terms_version text, terms_accepted_at timestamptz,
 UNIQUE(platform,external_user_id)
);
CREATE TABLE wallets (
 user_id uuid PRIMARY KEY REFERENCES users(id),
 available bigint NOT NULL DEFAULT 0 CHECK(available>=0),
 reserved bigint NOT NULL DEFAULT 0 CHECK(reserved>=0)
);
CREATE TABLE payments (
 id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES users(id),
 platform text NOT NULL, charge_id text,
 currency text NOT NULL, amount bigint NOT NULL CHECK(amount>0),
 credits bigint NOT NULL CHECK(credits>0), tariff_version text NOT NULL,
 status text NOT NULL CHECK(status IN ('pending','succeeded','refunding','refunded','review')),
 created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(platform,charge_id)
);
CREATE TABLE quotes (
 id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES users(id),
 text_content text, parameters jsonb NOT NULL,
 price bigint NOT NULL CHECK(price>0), tariff_version text NOT NULL,
 expires_at timestamptz NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE jobs (
 id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES users(id),
 quote_id uuid NOT NULL UNIQUE REFERENCES quotes(id),
 status text NOT NULL CHECK(status IN ('queued','dispatching','running','succeeded','failed','uncertain','cancelled')),
 settlement text CHECK(settlement IN ('capture','release')),
 price bigint NOT NULL CHECK(price>0), provider text NOT NULL,
 provider_job_id text, provider_request_id text, attempt_id uuid,
 lease_owner text, lease_until timestamptz, next_check_at timestamptz,
 error_code text, created_at timestamptz NOT NULL DEFAULT now(), completed_at timestamptz,
 UNIQUE(provider,provider_job_id)
);
CREATE UNIQUE INDEX one_active_job_per_user ON jobs(user_id)
 WHERE status IN ('queued','dispatching','running','uncertain');
CREATE INDEX jobs_queue ON jobs(created_at) WHERE status='queued';
CREATE TABLE ledger (
 id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES users(id),
 event_key text NOT NULL UNIQUE, kind text NOT NULL,
 delta_available bigint NOT NULL, delta_reserved bigint NOT NULL,
 job_id uuid REFERENCES jobs(id), payment_id uuid REFERENCES payments(id),
 reason text, created_at timestamptz NOT NULL DEFAULT now(),
 CHECK(delta_available<>0 OR delta_reserved<>0)
);
CREATE UNIQUE INDEX one_job_settlement ON ledger(job_id)
 WHERE kind IN ('capture','release');
CREATE TABLE files (
 id uuid PRIMARY KEY, job_id uuid NOT NULL REFERENCES jobs(id),
 storage_key text NOT NULL UNIQUE, mime_type text NOT NULL,
 size_bytes bigint NOT NULL CHECK(size_bytes>0), sha256 text NOT NULL,
 expires_at timestamptz NOT NULL, deleted_at timestamptz
);
CREATE TABLE deliveries (
 id uuid PRIMARY KEY, job_id uuid NOT NULL REFERENCES jobs(id),
 identity_id uuid NOT NULL REFERENCES identities(id), file_id uuid NOT NULL REFERENCES files(id),
 status text NOT NULL CHECK(status IN ('pending','sending','sent','retry','expired')),
 platform_file_id text, platform_message_id text, attempts integer NOT NULL DEFAULT 0,
 next_attempt_at timestamptz, UNIQUE(job_id,identity_id,file_id)
);
CREATE TABLE processed_events (
 platform text NOT NULL, event_id text NOT NULL,
 processed_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(platform,event_id)
);
CREATE TABLE audit_events (
 id uuid PRIMARY KEY, actor_identity_id uuid REFERENCES identities(id),
 action text NOT NULL, target_id text, metadata jsonb NOT NULL DEFAULT '{}',
 created_at timestamptz NOT NULL DEFAULT now()
);
-- Never store raw user text or credentials in audit metadata.
-- Add provider budget reservations, pricing catalog, refund operations and retention jobs
-- through versioned migrations before enabling those production features.
COMMIT;
