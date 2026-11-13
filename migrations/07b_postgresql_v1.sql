-- Apply as an independent superuser provisioner in a dedicated PostgreSQL 16
-- database, inside one transaction. The five roles must already exist without memberships.
CREATE SCHEMA ask4mo_07b AUTHORIZATION ask4mo_07b_owner;
SET LOCAL ROLE ask4mo_07b_owner;
REVOKE ALL ON SCHEMA ask4mo_07b FROM PUBLIC;

CREATE TABLE ask4mo_07b.control (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    ledger_id uuid NOT NULL DEFAULT gen_random_uuid(),
    policy jsonb CHECK (policy IS NULL OR (jsonb_typeof(policy) = 'object' AND policy->>'ledger_id' = ledger_id::text) IS TRUE),
    killed boolean NOT NULL DEFAULT false,
    generation bigint NOT NULL DEFAULT 0 CHECK (generation >= 0),
    kill_reason text
);
INSERT INTO ask4mo_07b.control DEFAULT VALUES;

CREATE TABLE ask4mo_07b.entry (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    capability uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    fingerprint text NOT NULL UNIQUE CHECK (fingerprint ~ '^[0-9a-f]{64}$'),
    category text NOT NULL CHECK (category IN ('agent', 'evaluation', 'embedding')),
    operation text NOT NULL,
    model text NOT NULL,
    endpoint text NOT NULL CHECK (endpoint IN ('chat', 'embeddings')),
    state text NOT NULL DEFAULT 'reserved' CHECK (state IN ('reserved', 'unknown', 'rejected', 'settled')),
    reserved_micro_usd bigint NOT NULL CHECK (reserved_micro_usd >= 0),
    held_micro_usd numeric NOT NULL CHECK (held_micro_usd >= 0 AND held_micro_usd = trunc(held_micro_usd)),
    committed_micro_usd numeric CHECK (committed_micro_usd >= 0 AND committed_micro_usd = trunc(committed_micro_usd)),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    accepted_at timestamptz,
    settled_at timestamptz,
    reconciled_at timestamptz,
    input_tokens bigint CHECK (input_tokens >= 0),
    output_tokens bigint CHECK (output_tokens >= 0),
    latency_ms bigint CHECK (latency_ms >= 0),
    estimated_micro_usd numeric CHECK (estimated_micro_usd >= 0 AND estimated_micro_usd = trunc(estimated_micro_usd)
        AND estimated_micro_usd::text NOT IN ('NaN', 'Infinity', '-Infinity')),
    reported_micro_usd numeric CHECK (reported_micro_usd >= 0 AND reported_micro_usd = trunc(reported_micro_usd)
        AND reported_micro_usd::text NOT IN ('NaN', 'Infinity', '-Infinity')),
    status_code integer CHECK (status_code BETWEEN 100 AND 599),
    error_category text CHECK (error_category IN (
        'admission_changed', 'reconciliation_required', 'malformed_body', 'usage_missing',
        'contradictory_charge', 'timeout', 'network', 'rate_limited', 'server_error', 'rejected'
    )),
    CHECK (
        (state IN ('reserved', 'unknown') AND held_micro_usd >= reserved_micro_usd AND committed_micro_usd IS NULL)
        OR (state = 'rejected' AND held_micro_usd = 0 AND committed_micro_usd IS NULL)
        OR (state = 'settled' AND (accepted_at IS NOT NULL OR reconciled_at IS NOT NULL) AND held_micro_usd = 0 AND committed_micro_usd IS NOT NULL)
    ),
    CHECK ((state = 'reserved') = (settled_at IS NULL)),
    CHECK (reconciled_at IS NULL OR state = 'settled')
);

-- One slot across all clients and processes. The admission lock also serializes
-- policy checks, aggregate accounting, handoff, stop, settlement and resume.
CREATE UNIQUE INDEX one_active_reservation ON ask4mo_07b.entry ((true)) WHERE state = 'reserved';

CREATE TABLE ask4mo_07b.authorization (
    id uuid PRIMARY KEY,
    kind text NOT NULL CHECK (kind IN ('receipt', 'resume', 'abandoned')),
    actor name NOT NULL,
    generation bigint NOT NULL CHECK (generation >= 0),
    reservation_id bigint REFERENCES ask4mo_07b.entry,
    final_micro_usd numeric CHECK (final_micro_usd >= 0 AND final_micro_usd = trunc(final_micro_usd)
        AND final_micro_usd::text NOT IN ('NaN', 'Infinity', '-Infinity')),
    expires_at timestamptz NOT NULL CHECK (isfinite(expires_at)),
    consumed_at timestamptz,
    CHECK (
        (kind = 'receipt' AND reservation_id IS NOT NULL AND final_micro_usd IS NOT NULL)
        OR (kind = 'abandoned' AND reservation_id IS NOT NULL AND final_micro_usd IS NULL)
        OR (kind = 'resume' AND reservation_id IS NULL AND final_micro_usd IS NULL)
    )
);

CREATE TABLE ask4mo_07b.audit (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    actor name NOT NULL DEFAULT SESSION_USER,
    action text NOT NULL,
    generation bigint NOT NULL,
    reservation_id bigint REFERENCES ask4mo_07b.entry,
    authorization_id uuid REFERENCES ask4mo_07b.authorization,
    details jsonb NOT NULL DEFAULT '{}'
);

-- Private helpers run as the definer of the entry point. Nothing in this schema
-- resolves through an application-controlled search_path or uses dynamic SQL.
CREATE FUNCTION ask4mo_07b.lock_control(p_accounting boolean DEFAULT true) RETURNS ask4mo_07b.control
LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    c ask4mo_07b.control;
BEGIN
    -- A lock alone does not refresh a transaction-wide snapshot of the entry table.
    IF p_accounting AND current_setting('transaction_isolation') <> 'read committed' THEN
        RAISE EXCEPTION USING ERRCODE = 'P0001', MESSAGE = 'unsupported_isolation';
    END IF;
    SELECT * INTO c FROM ask4mo_07b.control WHERE singleton FOR UPDATE;
    RETURN c;
END
$$;

CREATE FUNCTION ask4mo_07b.order_acl_change() RETURNS event_trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    PERFORM ask4mo_07b.lock_control();
    IF EXISTS (SELECT 1 FROM ask4mo_07b.entry WHERE state = 'reserved' AND accepted_at IS NOT NULL) THEN
        RAISE EXCEPTION USING ERRCODE = 'P0001', MESSAGE = 'acl_change_in_flight';
    END IF;
END
$$;

-- Check the login's privileges explicitly, including when called by a definer.
CREATE FUNCTION ask4mo_07b.runtime_privileges_valid() RETURNS boolean
LANGUAGE sql SET search_path = pg_catalog, pg_temp
AS $$
    SELECT runtime.rolname = 'ask4mo_07b_runtime' AND runtime.rolcanlogin AND NOT (
        runtime.rolsuper OR runtime.rolcreatedb OR runtime.rolcreaterole OR runtime.rolinherit
        OR runtime.rolreplication OR runtime.rolbypassrls
    ) AND NOT EXISTS (SELECT 1 FROM pg_auth_members WHERE member = runtime.oid)
    AND owner.rolname = 'ask4mo_07b_owner' AND NOT owner.rolcanlogin AND NOT (
        owner.rolsuper OR owner.rolcreatedb OR owner.rolcreaterole OR owner.rolinherit
        OR owner.rolreplication OR owner.rolbypassrls
    ) AND NOT EXISTS (SELECT 1 FROM pg_auth_members WHERE member = owner.oid)
    AND NOT has_database_privilege(runtime.oid, current_database(), 'CREATE,TEMP')
    AND NOT EXISTS (SELECT 1 FROM pg_namespace WHERE has_schema_privilege(runtime.oid, oid, 'CREATE'))
    AND NOT EXISTS (
        SELECT 1 FROM pg_class AS relation
        WHERE relation.relnamespace = n.oid AND relation.relkind IN ('r', 'p', 'S', 'v', 'm', 'f') AND (
            relation.relowner <> owner.oid
            OR CASE WHEN relation.relkind = 'S'
                THEN has_sequence_privilege(runtime.oid, relation.oid, 'USAGE,SELECT,UPDATE')
                ELSE has_table_privilege(runtime.oid, relation.oid, 'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
                    OR has_any_column_privilege(runtime.oid, relation.oid, 'SELECT,INSERT,UPDATE,REFERENCES')
            END
        )
    )
    AND 5 = (SELECT count(*) FROM pg_proc AS routine WHERE routine.pronamespace = n.oid
             AND routine.proname IN ('binding', 'reserve', 'accept_handoff', 'settle', 'status'))
    AND NOT EXISTS (
        SELECT 1 FROM pg_proc AS routine WHERE routine.pronamespace = n.oid AND (
            routine.proowner <> owner.oid
            OR has_function_privilege(runtime.oid, routine.oid, 'EXECUTE') IS DISTINCT FROM
                (routine.proname IN ('binding', 'reserve', 'accept_handoff', 'settle', 'status'))
            OR (routine.proname IN ('binding', 'reserve', 'accept_handoff', 'settle', 'status') AND (
                NOT routine.prosecdef OR routine.proconfig IS DISTINCT FROM ARRAY['search_path=pg_catalog, pg_temp']
            ))
        )
    )
    AND EXISTS (
        SELECT 1 FROM pg_event_trigger AS guard
        WHERE guard.evtname = 'ask4mo_07b_order_acl_change' AND guard.evtevent = 'ddl_command_start'
            AND guard.evtenabled = 'A' AND guard.evttags @> ARRAY['GRANT', 'REVOKE'] AND cardinality(guard.evttags) = 2
            AND guard.evtfoid = to_regprocedure('ask4mo_07b.order_acl_change()')
    )
    FROM pg_namespace AS n JOIN pg_roles AS owner ON owner.oid = n.nspowner
    JOIN pg_roles AS runtime ON runtime.rolname = SESSION_USER
    WHERE n.nspname = 'ask4mo_07b'
$$;

CREATE FUNCTION ask4mo_07b.binding() RETURNS TABLE (ledger_id uuid, privileges_valid boolean)
LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, pg_temp
AS $$
    SELECT control.ledger_id, ask4mo_07b.runtime_privileges_valid() FROM ask4mo_07b.control WHERE singleton
$$;

CREATE FUNCTION ask4mo_07b.require_open(c ask4mo_07b.control, p_policy jsonb) RETURNS timestamptz
LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    checked_at timestamptz := clock_timestamp();
BEGIN
    IF c.policy IS NULL OR p_policy IS NULL OR c.policy IS DISTINCT FROM p_policy THEN
        RAISE EXCEPTION USING ERRCODE = 'P0001', MESSAGE = 'policy_mismatch';
    END IF;
    IF c.killed THEN
        RAISE EXCEPTION USING ERRCODE = 'P0001', MESSAGE = 'kill_switch';
    END IF;
    IF (c.policy->>'total_stop')::bigint IS NULL OR (c.policy->>'class_stop')::bigint IS NULL
        OR (c.policy->>'total_requests')::bigint IS NULL OR (c.policy->>'class_requests')::bigint IS NULL THEN
        RAISE EXCEPTION USING ERRCODE = 'P0001', MESSAGE = 'approval_invalid';
    END IF;
    IF (checked_at >= (c.policy->>'starts_at')::timestamptz
        AND checked_at < (c.policy->>'expires_at')::timestamptz) IS NOT TRUE THEN
        RAISE EXCEPTION USING ERRCODE = 'P0001', MESSAGE = 'approval_invalid';
    END IF;
    RETURN checked_at;
END
$$;

CREATE FUNCTION ask4mo_07b.latch(c ask4mo_07b.control, p_reason text, p_id bigint, p_amount numeric)
RETURNS void LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    UPDATE ask4mo_07b.control
    SET killed = true, kill_reason = p_reason, generation = c.generation + 1 WHERE singleton;
    INSERT INTO ask4mo_07b.audit (action, generation, reservation_id, details)
    VALUES (p_reason, c.generation + 1, p_id, jsonb_build_object('observed_micro_usd', p_amount));
END
$$;

CREATE FUNCTION ask4mo_07b.reserve(
    p_policy jsonb, p_operation text, p_model text, p_endpoint text, p_fingerprint text, p_worst bigint
) RETURNS TABLE (entry_id bigint, token uuid)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    c ask4mo_07b.control := ask4mo_07b.lock_control();
    operation jsonb := c.policy #> ARRAY['operations', p_operation];
    bucket text := operation->>'category';
    prior_state text;
    requests bigint;
    exposure numeric;
    category_exposure numeric;
BEGIN
    PERFORM ask4mo_07b.require_open(c, p_policy);
    IF (p_worst >= (operation->>'reservation_micro_usd')::bigint AND p_worst >= 0) IS NOT TRUE
        OR p_model IS NULL OR p_endpoint IS NULL
        OR operation->>'model' IS DISTINCT FROM p_model OR operation->>'endpoint' IS DISTINCT FROM p_endpoint THEN
        RAISE EXCEPTION USING ERRCODE = 'P0001', MESSAGE = 'approval_invalid';
    END IF;
    SELECT state INTO prior_state FROM ask4mo_07b.entry WHERE fingerprint = p_fingerprint;
    IF FOUND THEN
        RAISE EXCEPTION USING ERRCODE = 'P0001', MESSAGE = CASE prior_state
            WHEN 'reserved' THEN 'duplicate_in_flight' WHEN 'unknown' THEN 'unknown_outcome_no_retry' ELSE 'retry_limit' END;
    END IF;
    IF EXISTS (SELECT 1 FROM ask4mo_07b.entry WHERE state = 'unknown') THEN
        RAISE EXCEPTION USING ERRCODE = 'P0001', MESSAGE = 'unknown_outcome_no_retry';
    END IF;
    IF EXISTS (SELECT 1 FROM ask4mo_07b.entry WHERE state = 'reserved') THEN
        RAISE EXCEPTION USING ERRCODE = 'P0001', MESSAGE = 'concurrency_limit';
    END IF;
    SELECT count(*), coalesce(sum(coalesce(committed_micro_usd, held_micro_usd)), 0),
        coalesce(sum(coalesce(committed_micro_usd, held_micro_usd)) FILTER (WHERE category = bucket), 0)
    INTO requests, exposure, category_exposure FROM ask4mo_07b.entry;
    IF requests >= (c.policy->>'total_requests')::bigint THEN
        RAISE EXCEPTION USING ERRCODE = 'P0001', MESSAGE = 'total_request_cap';
    END IF;
    IF requests >= (c.policy->>'class_requests')::bigint THEN
        RAISE EXCEPTION USING ERRCODE = 'P0001', MESSAGE = 'request_cap';
    END IF;
    IF exposure + p_worst > (c.policy->>'total_stop')::bigint THEN
        RAISE EXCEPTION USING ERRCODE = 'P0001', MESSAGE = 'total_stop';
    END IF;
    IF exposure + p_worst > (c.policy->>'class_stop')::bigint THEN
        RAISE EXCEPTION USING ERRCODE = 'P0001', MESSAGE = 'stop_threshold';
    END IF;
    IF (category_exposure + p_worst <= (c.policy->'category_stops'->>bucket)::bigint) IS NOT TRUE THEN
        RAISE EXCEPTION USING ERRCODE = 'P0001', MESSAGE = 'category_stop';
    END IF;
    RETURN QUERY INSERT INTO ask4mo_07b.entry AS entry (
        fingerprint, category, operation, model, endpoint, reserved_micro_usd, held_micro_usd
    ) VALUES (p_fingerprint, bucket, p_operation, p_model, p_endpoint, p_worst, p_worst)
    RETURNING entry.id, entry.capability;
END
$$;

CREATE FUNCTION ask4mo_07b.accept_handoff(p_id bigint, p_token uuid, p_policy jsonb) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    c ask4mo_07b.control := ask4mo_07b.lock_control();
    checked_at timestamptz;
BEGIN
    IF ask4mo_07b.runtime_privileges_valid() IS NOT TRUE THEN
        RAISE EXCEPTION USING ERRCODE = 'P0001', MESSAGE = 'ledger_unavailable';
    END IF;
    checked_at := ask4mo_07b.require_open(c, p_policy);
    UPDATE ask4mo_07b.entry SET accepted_at = checked_at
    WHERE id = p_id AND capability = p_token AND state = 'reserved' AND accepted_at IS NULL;
    IF NOT FOUND THEN
        RAISE EXCEPTION USING ERRCODE = 'P0001', MESSAGE = 'handoff_refused';
    END IF;
END
$$;

CREATE FUNCTION ask4mo_07b.settle(
    p_id bigint, p_token uuid, p_outcome text, p_cost numeric, p_input bigint,
    p_output bigint, p_status integer, p_latency bigint, p_error text, p_estimated numeric, p_reported numeric
) RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    c ask4mo_07b.control := ask4mo_07b.lock_control();
    e ask4mo_07b.entry;
    operation jsonb;
    usage_estimate numeric;
    charge_floor numeric;
    recorded_cost numeric;
    result text := p_outcome;
    reason text := p_error;
BEGIN
    SELECT * INTO e FROM ask4mo_07b.entry WHERE id = p_id AND capability = p_token;
    IF c.policy IS NULL OR NOT FOUND OR p_cost IS NULL OR p_cost < 0 OR p_cost <> trunc(p_cost)
        OR p_cost::text IN ('NaN', 'Infinity', '-Infinity')
        OR p_outcome IS NULL OR p_outcome NOT IN ('settled', 'unknown', 'rejected')
        OR (p_outcome = 'settled' AND e.accepted_at IS NULL)
        OR e.state <> 'reserved' THEN
        RAISE EXCEPTION USING ERRCODE = 'P0001', MESSAGE = 'settlement_refused';
    END IF;

    operation := c.policy #> ARRAY['operations', e.operation];
    IF operation IS NULL OR operation->>'prompt_usd_per_token' IS NULL
        OR operation->>'completion_usd_per_token' IS NULL THEN
        RAISE EXCEPTION USING ERRCODE = 'P0001', MESSAGE = 'ledger_inconsistent';
    END IF;
    usage_estimate := ceil(1000000 * (p_input * (operation->>'prompt_usd_per_token')::numeric
        + p_output * (operation->>'completion_usd_per_token')::numeric));
    charge_floor := greatest(0, usage_estimate, p_estimated, p_reported);
    recorded_cost := greatest(p_cost, charge_floor);

    IF p_outcome = 'rejected' THEN
        -- Release only a confirmed pre-handoff refusal. HTTP status alone cannot prove zero charge.
        IF NOT (e.accepted_at IS NULL AND p_status IS NULL AND p_input IS NULL AND p_output IS NULL
                AND recorded_cost = 0 AND coalesce(p_error, '') IN ('admission_changed', 'reconciliation_required')) THEN
            result := 'unknown';
            reason := CASE WHEN recorded_cost > 0 THEN 'contradictory_charge' ELSE coalesce(p_error, 'rejected') END;
        END IF;
    ELSIF p_outcome = 'settled' AND (p_error IS NOT NULL OR p_status IS DISTINCT FROM 200 OR usage_estimate IS NULL
            OR (e.endpoint = 'embeddings' AND p_output <> 0) OR p_cost < charge_floor
            OR (e.reserved_micro_usd > 0 AND recorded_cost = 0)) THEN
        result := 'unknown';
        reason := CASE WHEN p_cost < charge_floor THEN 'contradictory_charge' ELSE coalesce(p_error, 'usage_missing') END;
    END IF;

    UPDATE ask4mo_07b.entry SET state = result, settled_at = clock_timestamp(),
        held_micro_usd = CASE WHEN result = 'unknown' THEN greatest(e.held_micro_usd, recorded_cost) ELSE 0 END,
        committed_micro_usd = CASE WHEN result = 'settled' THEN recorded_cost END,
        input_tokens = p_input, output_tokens = p_output, status_code = p_status, latency_ms = p_latency,
        error_category = reason, estimated_micro_usd = greatest(usage_estimate, p_estimated),
        reported_micro_usd = p_reported WHERE id = p_id;
    IF recorded_cost > e.reserved_micro_usd THEN
        PERFORM ask4mo_07b.latch(c, 'overrun', p_id, recorded_cost);
    ELSIF result = 'unknown' THEN
        PERFORM ask4mo_07b.latch(c, 'unknown', p_id, recorded_cost);
    END IF;
    RETURN result;
END
$$;

CREATE FUNCTION ask4mo_07b.emergency_stop() RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    c ask4mo_07b.control := ask4mo_07b.lock_control(false);
BEGIN
    IF c.policy IS NULL THEN
        RAISE EXCEPTION USING ERRCODE = 'P0001', MESSAGE = 'ledger_inconsistent';
    END IF;
    PERFORM ask4mo_07b.latch(c, 'stop', NULL, NULL);
END
$$;

CREATE FUNCTION ask4mo_07b.consume_authorization(p_kind text, p_approval uuid, p_generation bigint, p_id bigint)
RETURNS numeric LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    amount numeric;
BEGIN
    UPDATE ask4mo_07b.authorization SET consumed_at = clock_timestamp()
    WHERE id = p_approval AND kind = p_kind AND actor = SESSION_USER
        AND generation = p_generation AND reservation_id IS NOT DISTINCT FROM p_id
        AND consumed_at IS NULL AND expires_at > clock_timestamp()
    RETURNING final_micro_usd INTO amount;
    IF NOT FOUND THEN
        RAISE EXCEPTION USING ERRCODE = 'P0001', MESSAGE = 'authorization_invalid';
    END IF;
    RETURN amount;
END
$$;

CREATE FUNCTION ask4mo_07b.mark_abandoned(p_id bigint, p_approval uuid) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    c ask4mo_07b.control := ask4mo_07b.lock_control();
BEGIN
    -- The independent issuer must establish receiver quiescence. No automatic
    -- timeout promotes an in-flight request or releases a monetary hold.
    PERFORM ask4mo_07b.consume_authorization('abandoned', p_approval, c.generation, p_id);
    UPDATE ask4mo_07b.entry SET state = 'unknown', settled_at = clock_timestamp()
    WHERE id = p_id AND state = 'reserved' AND c.killed;
    IF NOT FOUND THEN
        RAISE EXCEPTION USING ERRCODE = 'P0001', MESSAGE = 'hold_not_reconcilable';
    END IF;
    INSERT INTO ask4mo_07b.audit (action, generation, reservation_id, authorization_id)
    VALUES ('abandoned', c.generation, p_id, p_approval);
END
$$;

CREATE FUNCTION ask4mo_07b.reconcile_hold(p_id bigint, p_receipt uuid) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    c ask4mo_07b.control := ask4mo_07b.lock_control();
    amount numeric;
    before_held numeric;
BEGIN
    amount := ask4mo_07b.consume_authorization('receipt', p_receipt, c.generation, p_id);
    SELECT held_micro_usd INTO before_held FROM ask4mo_07b.entry WHERE id = p_id AND state = 'unknown';
    IF NOT FOUND OR c.killed IS NOT TRUE THEN
        RAISE EXCEPTION USING ERRCODE = 'P0001', MESSAGE = 'hold_not_reconcilable';
    END IF;
    UPDATE ask4mo_07b.entry SET state = 'settled', held_micro_usd = 0, committed_micro_usd = amount,
        reconciled_at = clock_timestamp(), settled_at = clock_timestamp() WHERE id = p_id;
    INSERT INTO ask4mo_07b.audit (action, generation, reservation_id, authorization_id, details)
    VALUES ('reconcile', c.generation, p_id, p_receipt,
        jsonb_build_object('before_held', before_held, 'final_micro_usd', amount));
END
$$;

CREATE FUNCTION ask4mo_07b.resume(p_generation bigint, p_approval uuid) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    c ask4mo_07b.control := ask4mo_07b.lock_control();
BEGIN
    IF c.killed IS NOT TRUE OR p_generation IS DISTINCT FROM c.generation THEN
        RAISE EXCEPTION USING ERRCODE = 'P0001', MESSAGE = 'authorization_invalid';
    END IF;
    PERFORM ask4mo_07b.consume_authorization('resume', p_approval, c.generation, NULL);
    IF EXISTS (SELECT 1 FROM ask4mo_07b.entry WHERE state IN ('reserved', 'unknown')) THEN
        RAISE EXCEPTION USING ERRCODE = 'P0001', MESSAGE = 'recovery_reconciliation_required';
    END IF;
    UPDATE ask4mo_07b.control SET killed = false, kill_reason = NULL WHERE singleton;
    INSERT INTO ask4mo_07b.audit (action, generation, authorization_id)
    VALUES ('resume', c.generation, p_approval);
END
$$;

CREATE FUNCTION ask4mo_07b.status() RETURNS jsonb
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, pg_temp
AS $$
    SELECT jsonb_build_object(
        'policy', c.policy, 'killed', c.killed, 'kill_reason', c.kill_reason,
        'generation', c.generation, 'requests', a.requests, 'held', a.held,
        'settled', a.settled, 'open', a.open, 'unknown', a.unknown,
        'input_tokens', a.input_tokens, 'output_tokens', a.output_tokens,
        'known_calls', a.known_calls, 'latency', a.latency, 'errors', a.errors,
        'states', (SELECT coalesce(jsonb_object_agg(state, n), '{}')
            FROM (SELECT state, count(*) AS n FROM ask4mo_07b.entry GROUP BY state) AS states),
        'categories', (SELECT coalesce(jsonb_object_agg(category, held), '{}')
            FROM (SELECT category, sum(coalesce(committed_micro_usd, held_micro_usd)) AS held
                FROM ask4mo_07b.entry GROUP BY category) AS categories)
    )
    FROM ask4mo_07b.control AS c CROSS JOIN (
        SELECT count(*) AS requests, coalesce(sum(coalesce(committed_micro_usd, held_micro_usd)), 0) AS held,
            coalesce(sum(committed_micro_usd), 0) AS settled,
            coalesce(sum(held_micro_usd) FILTER (WHERE state = 'reserved'), 0) AS open,
            coalesce(sum(held_micro_usd) FILTER (WHERE state = 'unknown'), 0) AS unknown,
            sum(input_tokens) AS input_tokens, sum(output_tokens) AS output_tokens,
            count(*) FILTER (WHERE input_tokens IS NOT NULL AND output_tokens IS NOT NULL) AS known_calls,
            round(avg(latency_ms), 1) AS latency, count(error_category) AS errors
        FROM ask4mo_07b.entry
    ) AS a WHERE c.singleton
$$;

REVOKE ALL ON ALL TABLES IN SCHEMA ask4mo_07b FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA ask4mo_07b FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA ask4mo_07b FROM PUBLIC;
GRANT USAGE ON SCHEMA ask4mo_07b TO ask4mo_07b_runtime, ask4mo_07b_stop, ask4mo_07b_reconcile, ask4mo_07b_issuer;
GRANT EXECUTE ON FUNCTION ask4mo_07b.binding(), ask4mo_07b.reserve(jsonb, text, text, text, text, bigint),
    ask4mo_07b.accept_handoff(bigint, uuid, jsonb),
    ask4mo_07b.settle(bigint, uuid, text, numeric, bigint, bigint, integer, bigint, text, numeric, numeric),
    ask4mo_07b.status() TO ask4mo_07b_runtime;
GRANT EXECUTE ON FUNCTION ask4mo_07b.emergency_stop() TO ask4mo_07b_stop;
GRANT EXECUTE ON FUNCTION ask4mo_07b.mark_abandoned(bigint, uuid), ask4mo_07b.reconcile_hold(bigint, uuid),
    ask4mo_07b.resume(bigint, uuid) TO ask4mo_07b_reconcile;
GRANT INSERT (id, kind, actor, generation, reservation_id, final_micro_usd, expires_at)
    ON ask4mo_07b.authorization TO ask4mo_07b_issuer;
RESET ROLE;

CREATE EVENT TRIGGER ask4mo_07b_order_acl_change ON ddl_command_start
    WHEN TAG IN ('GRANT', 'REVOKE') EXECUTE FUNCTION ask4mo_07b.order_acl_change();
ALTER EVENT TRIGGER ask4mo_07b_order_acl_change ENABLE ALWAYS;
