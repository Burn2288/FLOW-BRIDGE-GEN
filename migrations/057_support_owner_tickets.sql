CREATE TABLE support_tickets (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id uuid NOT NULL REFERENCES users(id),
    request_id uuid NOT NULL,
    status text NOT NULL DEFAULT 'open' CHECK (status='open'),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (owner_id, request_id)
);

CREATE TABLE support_messages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id uuid NOT NULL REFERENCES support_tickets(id),
    request_id uuid NOT NULL,
    body text NOT NULL CHECK (char_length(body) BETWEEN 1 AND 2000 AND octet_length(body)<=8000),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (ticket_id, request_id)
);

CREATE INDEX support_tickets_owner_history ON support_tickets(owner_id,created_at DESC,id DESC);
CREATE INDEX support_messages_history ON support_messages(ticket_id,created_at,id);

CREATE TRIGGER support_tickets_immutable BEFORE UPDATE OR DELETE ON support_tickets
    FOR EACH ROW EXECUTE FUNCTION immutable_row();
CREATE TRIGGER support_messages_immutable BEFORE UPDATE OR DELETE ON support_messages
    FOR EACH ROW EXECUTE FUNCTION immutable_row();
