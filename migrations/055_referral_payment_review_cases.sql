CREATE TABLE referral_payment_review_cases (
    payment_id uuid NOT NULL REFERENCES payments(id),
    capture_id uuid NOT NULL REFERENCES referral_rewards(capture_id),
    reward_ledger_id uuid NOT NULL REFERENCES ledger(id),
    affected_funding bigint NOT NULL CHECK (affected_funding>0),
    payment_state text NOT NULL,
    reason text NOT NULL CHECK (reason IN ('payment_review','payment_refunded','partial_payment_return')),
    state text NOT NULL DEFAULT 'required' CHECK (state='required'),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(payment_id,capture_id)
);
CREATE TRIGGER referral_payment_review_immutable BEFORE UPDATE OR DELETE ON referral_payment_review_cases
    FOR EACH ROW EXECUTE FUNCTION immutable_row();
