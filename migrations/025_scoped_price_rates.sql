CREATE TABLE task_price_conversions (
    provider text NOT NULL CHECK (provider <> ''),
    source_unit text NOT NULL CHECK (source_unit <> ''),
    source_amount numeric NOT NULL CHECK (source_amount > 0 AND source_amount <= 1000000000000),
    target_amount numeric NOT NULL CHECK (target_amount > 0 AND target_amount <= 1000000000000),
    revision bigint NOT NULL DEFAULT nextval('task_price_rule_revision'),
    PRIMARY KEY (provider,source_unit)
);

INSERT INTO task_price_conversions(provider,source_unit,source_amount,target_amount,revision)
SELECT CASE source_unit WHEN 'anymodel_balance_token' THEN 'anymodel' ELSE 'clodex' END,
       source_unit,1,multiplier,revision
FROM task_price_rates WHERE source_unit IN ('anymodel_balance_token','clodex_balance_token','USD');

-- Historical manual tariffs can still use their old conversion unit.
ALTER TABLE task_manual_tariffs DROP CONSTRAINT task_manual_tariffs_source_unit_fkey;

CREATE TABLE task_ruble_equivalent (
    id integer PRIMARY KEY CHECK (id=1),
    bot_amount numeric NOT NULL CHECK (bot_amount > 0 AND bot_amount <= 1000000000000),
    rubles numeric NOT NULL CHECK (rubles > 0 AND rubles <= 1000000000000)
);
