# C-013/C-014 — Universal Provider Integration Contract

> **Новая сверка с фактическим кодом (PR #17, SHA d691d54e…; 2026-11-15):** Реализованы `aggregate.py:ProviderRegistry`, `task_launch.py:ExecutionAdapter`, `provider_execution.py` и тест третьего fixture-агрегатора. Новый manifesto/onboarding workflow должен расширить существующие контракты, а не создавать параллельный реестр или глобальный switch по каждому бренду. Состояние этого кода — SOURCE_PRESENT_UNMERGED + CI_PASS, не принятая main. [Полная инвентаризация](../audit/VANKHU21_IMPLEMENTATION_BASELINE.md).
Status: DESIGN_DRAFT. Critical architectural requirement: register AI aggregators with divergent sync/async/request formats without rewriting platform core.

## Supported integration categories
TEXT_TO_IMAGE, IMAGE_TO_IMAGE, TEXT_TO_VIDEO, IMAGE_TO_VIDEO, TEXT_TO_SPEECH, SPEECH_TO_TEXT (future), TEXT_TO_MUSIC, MUSIC_EXTEND (future), and future capability IDs. A provider is not a model; models expose individual capabilities and schemas.
Core interface: ProviderAdapterV1 with validate_config(), discover_models() [optional], normalize_capabilities(), estimate_cost(), start(request), poll(handle) [optional], handle_webhook(event) [optional], cancel(handle) [optional], health(). Each method returns typed payloads or normalized typed errors; no provider-specific exception crosses into core.
Provider manifest: adapter_id, adapter_contract_version, provider_id, name, verified_base_hosts, auth_strategy, transport (REST/SDK), execution_mode (SYNC/ASYNC/WEBHOOK), supported_capabilities, limits, timeouts, idempotency_policy, callback_signature_policy, cost_units, secrets_refs, model_mapping schema, output handling and documentation sources.
Normalized StartResult = COMPLETED(typed artifacts and metadata) | ACCEPTED(provider_job_id, poll_after) | UNCERTAIN(reason, request correlation) | REJECTED(error). PollResult = PROCESSING/COMPLETED/FAILED/UNCERTAIN. Artifact = type, content_kind (bytes/url/base64/provider-asset-id), media type, size/checksum when known, safe metadata. Validate and persist before declaring job successful.

## Adding a new aggregator — administrator workflow
1. Admin chooses an installed, signed, reviewed adapter from catalog (or requests integration code review); enters display name and scoped credentials into secret store / secret reference, never arbitrary Python code.
2. Admin configures allowlisted base URL/region, verifies TLS and SSRF rules; chooses supported auth protocol (API key/Bearer/signed headers/OAuth via audited adapter).
3. Dry-run: syntax and schema validation, redacted network health/identity probe, capability discovery or manual model metadata entry. Do not expend real credits without explicit approval.
4. Import model definitions with metadata and input/output schema, categorize by Studio, assign prices, limits, feature flags and test accounts; stage invisible to regular users.
5. Contract sandbox suite: known expected response, async poll, errors, timeouts, malformed/oversized output, cancellation and cost/retry constraints. Then one explicitly authorized live cheap probe if available.
6. Preview model cards and form in bot/Mini App staging, with same Catalog API.
7. Approve activation with RBAC + audit event + version pin; publish catalog update without restarting customer interfaces when adapter runtime is already installed.
8. Monitor health/error/credit discrepancies; pause model/provider independently; rollback manifest/rules without destroying existing job version references.

## Hard limit of universality
Configuration alone can onboard new providers ONLY if their protocol is supported by an installed adapter family. A fundamentally novel transport, authentication, streaming, asynchronous state, signature or pricing protocol requires writing a small new adapter implementing the contract, review, tests and deployment. Never promise that an unknown API can safely be integrated by pasting an arbitrary endpoint and secret; no unrestricted script execution inside admin panel.

## Adapter security
Secret references read by runtime secret resolver, never served to Mini App or Telegram; allowlisted outbound hostnames, DNS rebinding defense, redirects checked at every hop, request/response redaction, byte/time/request budgets, per-provider circuit breaker, rate limits, no arbitrary file access. Provider webhook verifies signature and binds provider job to existing owned job; external data never directly updates ledger. Version adapter binary and manifest, keep old adapters while in-flight jobs exist.

## Retry and uncertain outcomes
Retry only known-safe requests by documented idempotency semantics. Never fall back to another paid provider on unknown initial result. Poll GET/status or reconcile instead. Distinguish no-charge transport failures from unknown provider execution.

## Acceptance
Two dissimilar adapters (e.g. sync image and async video) pass common fixtures, same client UI and billing workflow, 4 product category manifests validate, misconfigured provider cannot take platform down, disabled model disappears, rollback works, credentials never appear in logs. Live credentials are not required for unit/contract tests; real provider E2E separately evidence-graded.
