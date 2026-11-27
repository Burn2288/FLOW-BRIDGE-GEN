CREATE TABLE support_operator_replies (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id uuid NOT NULL REFERENCES support_tickets(id),
    actor_id uuid NOT NULL REFERENCES users(id),
    request_id uuid NOT NULL,
    body text NOT NULL CHECK(char_length(body) BETWEEN 1 AND 2000 AND octet_length(body)<=8000),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(ticket_id,request_id)
);
CREATE TRIGGER support_operator_replies_immutable BEFORE UPDATE OR DELETE ON support_operator_replies
    FOR EACH ROW EXECUTE FUNCTION immutable_row();
