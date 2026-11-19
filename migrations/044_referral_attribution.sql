-- Independent attribution records; no financial or rewards behavior.
CREATE TABLE referral_codes (
    user_id uuid PRIMARY KEY REFERENCES users(id),
    code text NOT NULL UNIQUE CHECK (code ~ '^[A-Za-z0-9_-]{16}$'),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE referral_attributions (
    user_id uuid PRIMARY KEY REFERENCES users(id),
    referrer_id uuid NOT NULL REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (user_id <> referrer_id)
);
CREATE FUNCTION reject_referral_rewrite() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'referral attribution is immutable';
END $$;
CREATE TRIGGER referral_codes_immutable BEFORE UPDATE OR DELETE ON referral_codes
    FOR EACH ROW EXECUTE FUNCTION reject_referral_rewrite();
CREATE TRIGGER referral_attributions_immutable BEFORE UPDATE OR DELETE ON referral_attributions
    FOR EACH ROW EXECUTE FUNCTION reject_referral_rewrite();
