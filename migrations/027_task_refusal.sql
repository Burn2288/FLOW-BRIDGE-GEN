ALTER TABLE task_dispatch DROP CONSTRAINT task_dispatch_state_check;
ALTER TABLE task_dispatch ADD CONSTRAINT task_dispatch_state_check
    CHECK (state IN ('pending','dispatching','completed','delegated','interrupted','uncertain','rejected'));
