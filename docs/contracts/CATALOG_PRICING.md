# C-006/C-007/C-015 — Catalog, capabilities, price quotations
Status: DESIGN_DRAFT.

## Provider to user catalog
Provider registration does not imply a model is visible. Provider → capabilities → models → versions → price rules → publish state. Each model has: stable model ID, display name, provider ID, adapter identifier, provider model key, media kind, supported operations, required/optional input schema, constraints (prompt length, image count, resolution, duration, languages, voices, file formats), output schema, availability, capabilities, model_version, external docs reference, health and effective dates.
States DRAFT, VALIDATED, STAGED, ACTIVE, PAUSED, DEPRECATED, DISABLED. Only ACTIVE and compatible models shown; unavailability shown gracefully when appropriate. Never delete a model while jobs reference its version.

## Pricing separation
provider_cost_quote (estimated or observed, source, unit and currency) vs user_sell_quote (server-authoritative). Sale formula may include markup, minimum price, tier discounts, fixed fee, exchange conversion and VAT/tax handling (not chosen yet). Store integer minor units or Decimal with explicit currency precision, never binary float; define deterministic rounding as an approved pricing policy.
Inputs: model_version, capability, normalized parameters, quantity/seconds/tokens/output pixels, account segment/tier, currency. Quote: quote_id, actor_id, model_version, normalized_params_hash, amount_minor, currency, pricing_rule_version, provider_cost_estimate_minor, expiry, disclaimer and max_possible_amount if variable. Quote tied to user and immutable once accepted.
For variable final price require explicit maximum/hold and final calculation policy; if undefined disable sale of that model. Historical job prices and referral rewards pin their own snapshot.

## Dynamic catalog
Admin can add/disable providers and models, configure schema-backed forms, capabilities, allowlisted credentials, provider cost and selling price, pagination, visibility and rollout, all with audit. Changes have draft → dry-run schema validation → contract probe → stage → preview → publish; rollback to previous version. Catalog is served by API to Telegram and Mini App simultaneously, cache invalidation/version ETag. A new integration protocol requires a new reviewed adapter code package; arbitrary user-supplied HTTP endpoints/body templates must never be executed with privileged keys.

## Tests
Boundary parameters and unit conversions, zero/negative quote rejection, rounding, concurrent price changes, stale quote, hidden models, inactive provider, provider base URL SSRF, duplicate model external keys, pagination, capability/client parity, rollback and old job reproducibility.
