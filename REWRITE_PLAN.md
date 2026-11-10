# GEX Dashboard Rewrite Plan

## 0. Goals and non-goals

### Goals
- Preserve current user-visible capabilities (GEX/DEX analytics, dashboard views, MCP tools, Discord bot integration, CBOE + optional dxFeed flows) while improving architecture.
- Separate concerns: **capture/ingestion**, **compute**, **storage/state**, **serving/UI/API**.
- Make data contracts explicit and versioned (schemas, provenance, quality/freshness metadata).
- Improve reliability, observability, and testability (deterministic compute, replayable inputs, health checks).
- Enable incremental migration with no big-bang cutover.

### Non-goals (initial rewrite phases)
- Replacing every feature at once or changing market-math conventions without validation.
- Rewriting the Dash UI wholesale in phase 1.
- Introducing heavy infrastructure dependencies; prefer local-first components (SQLite/DuckDB optional, in-process first).

## 1. Guiding principles
1. **Backward compatibility first:** existing entrypoints (`gex-dashboard`, `gex-mcp`, `python run.py`), data directories, and key APIs keep working during migration.
2. **Strangler-fig migration:** add new modules/adapters behind stable interfaces and route existing code through them incrementally.
3. **Pure compute:** analytics functions must be deterministic and side-effect free given typed inputs.
4. **Provenance everywhere:** every derived artifact carries source, timestamps, schema version, and quality flags.
5. **Test before/after each slice:** run existing tests continuously; add tests for every new contract.

## 2. Target architecture (incremental)

### Components
- **`gex/core/`**: domain models, schemas, events, interfaces, validation, quality metadata.
- **`gex/providers/` (adapters)**: source-specific fetch/stream adapters (CBOE, dxFeed/futopt/idxopt, remote capture) normalized to canonical inputs.
- **`gex/compute/`**: pure enrichment/metrics/levels/flow/regime computations and materializers.
- **`gex/state/`**: in-memory read model + snapshot cache fed by events/jobs.
- **`gex/storage/`**: Parquet persistence + optional indexed query store abstractions; manifests/retention hooks.
- **`gex/pipeline/`**: schedulers/jobs/orchestration that wire providers -> compute -> storage/state -> events.
- **`gex/serve/`**: read-only API/read models for Dash, MCP, bot; streaming endpoints decoupled from compute.
- **Compatibility shims**: existing `gex.ingest`, `gex.metrics`, `gex.scheduler`, `gex.store`, `gex.run` continue to expose current behavior by delegating to new components.

### Data contracts (v1)
- `RawChainSnapshot` (source payload metadata + normalized rows)
- `EnrichedSnapshot` (computed greeks/exposures, schema_version)
- `MarketSummary` (net gex/dex, walls, flip, confidence/quality)
- `FlowRecord` / `RegimeEvent`
- Common metadata: `symbol`, `source`, `provider_ts`, `fetched_at`, `as_of`, `schema_version`, `quality` (stale/delayed/partial flags)

## 3. Phased implementation plan

### Phase 0 — Baseline and scaffolding (start now)
**Tasks**
- Create `rewrite` branch and this plan.
- Add `gex/core` package with: schema/version constants, typed dataclasses/protocols for providers and compute inputs/outputs, quality/provenance helpers, lightweight validation utilities.
- Add an internal event abstraction (simple pub/sub or queue interface) for snapshot/summary events.
- Add compatibility layer so existing modules can import/use new contracts without behavior change.
- Add tests for schema defaults, serialization round-trips, provenance/quality tagging, and interface conformance.

**Acceptance**
- Existing tests still pass.
- New core tests pass.
- No change required to current runtime paths.

### Phase 1 — Compute extraction and determinism
**Tasks**
- Wrap/refactor `metrics`/`greeks` hot paths behind pure compute functions in `gex/compute` (same formulas/defaults).
- Introduce materialized summary objects consumed by scheduler/state.
- Add golden/fixture-based tests comparing new compute outputs to current outputs for representative snapshots.

**Acceptance**
- Numerical parity on fixtures (within defined tolerances).
- Scheduler/state can use compute layer via adapter.

### Phase 2 — Provider adapters and normalization
**Tasks**
- Implement CBOE adapter using existing `ingest` logic as backend; normalize to canonical `RawChainSnapshot`.
- Define capability metadata (delayed/realtime, aggressor side availability, Greeks availability).
- Add parsing/normalization tests and malformed-payload handling/quarantine hooks.

**Acceptance**
- Current CBOE ingestion path works through adapter with same persisted results.

### Phase 3 — State/read model decoupling
**Tasks**
- Introduce read-model/state store updated from compute outputs/events.
- Make dashboard/API/MCP readers depend on read model interfaces where feasible.
- Add health/freshness metadata (last pull, lag, source, quality).

**Acceptance**
- UI/API reflect same values; state updates are observable and testable.

### Phase 4 — Storage/query improvements
**Tasks**
- Formalize dataset layout and manifests; add schema_version columns/metadata.
- Add optional indexed query backend (SQLite/DuckDB) for hot reads/history queries behind interface, default off/local-safe.
- Retention/compaction utilities with dry-run mode.

**Acceptance**
- Reads faster or equal for hot paths; historical compatibility maintained.

### Phase 5 — Serving and streaming hardening
**Tasks**
- Stabilize read API contract shared by Dash/MCP/Discord bot.
- Isolate streaming/SSE publishers; add backpressure/limits and health endpoints.
- Preserve existing routes/tools; deprecate internals gradually.

**Acceptance**
- Concurrency behavior improved under load tests; no contract regressions.

### Phase 6 — Cutover, cleanup, and docs
**Tasks**
- Flip defaults to new pipeline where validated.
- Remove dead compatibility code after deprecation window.
- Update docs (architecture, schemas, ops/runbook, migration notes).

## 4. Testing strategy (continuous)

- **Regression:** run `pytest tests/ -q` after every meaningful change (baseline + per phase).
- **Unit tests:** schemas/validation, provider normalization, pure compute functions, state transitions.
- **Parity/golden tests:** fixed snapshot fixtures -> compare legacy vs new outputs (exact or tolerance-based for floats).
- **Replay tests:** recorded snapshot/flow sequences to validate end-to-end pipeline determinism.
- **Contract tests:** MCP/API/bot-facing payload shapes remain compatible.
- **Operational checks:** startup smoke, scheduler job wiring, health/freshness reporting (where added).
- **Bug bar:** no new failing tests; investigate and fix regressions before proceeding. For known environment-only issues, document explicitly.

## 5. Risk management and rollback
- Keep changes additive and behind adapters/shims until parity proven.
- Feature-flag new pipeline paths; default to legacy behavior until validated.
- Small commits per slice on `rewrite` branch with tests.
- Rollback: revert to legacy module path/flag or previous commit; persisted data remains readable via compatibility readers.

## 6. Execution status (rewrite branch)

### Completed
- [x] Inspect repo/branch state and preserve pre-existing local working-tree changes.
- [x] Write rewrite plan.
- [x] Create `rewrite` branch and commit incremental slices.
- [x] **Phase 0 (scaffolding):** `gex/core` schemas/provenance/quality, event bus, interfaces, validation, package scaffolds, and tests.
- [x] **Phase 1 (compute parity):** `gex/compute/greeks` + `gex/compute/metrics` wrappers delegating to legacy implementations, `gex/compute/pipeline` bridge to core contracts/metadata, and parity tests vs legacy outputs.
- [x] **Phase 2 (provider adapter):** `gex/providers/cboe` adapter with capability metadata and normalization to `RawChainSnapshot`/provenance (legacy fetch backend injectable), plus tests.
- [x] **Phase 3 (state/read model, additive):** `gex/state/readmodel` in-memory read model with freshness/quality/error/health tracking and tests; optional side-channel runtime (`gex/pipeline/runtime.py`, `GEX_REWRITE_PIPELINE=1`) updates read model/events from legacy ingestion without altering legacy behavior.
- [x] **Phase 4 (storage metadata, additive):** sidecar manifest utilities (`gex/storage/metadata.py`) writing schema/provenance manifests per symbol; runtime emits manifests when enabled; tests. Existing Parquet formats remain unchanged for compatibility.
- [x] **Phase 5 (serving/health, additive):** `gex/serve/health.py` and `/api/v1/rewrite/health` endpoint exposing rewrite read-model health when enabled; tests. Existing Dash/MCP/API contracts preserved.
- [x] **Phase 6 (incremental cutover/docs):** plan updated with implementation status; new paths are additive/flagged or side-channel, keeping legacy defaults and entrypoints intact.

### Validation
- Added rewrite/phase tests: `tests/test_core_rewrite.py`, `tests/test_compute_parity_phase1.py`, `tests/test_compute_pipeline_phase1.py`, `tests/test_provider_cboe_phase2.py`, `tests/test_state_readmodel_phase3.py`, `tests/test_pipeline_runtime.py`, `tests/test_storage_metadata_phase4.py`, `tests/test_serve_health_phase5.py`.
- Full regression suite run repeatedly during implementation: **all existing + new tests passing** (latest run recorded in commit/session notes: `612 passed, 1 skipped, 1 warning`).

### Remaining follow-ups (post-foundation, non-breaking)
- Wire provider/compute/read-model into scheduler/serving as primary paths behind feature flags after parity soak (currently side-channel/compat wrappers in place).
- Expand adapters for dxFeed/futopt/idxopt/tick capture with unified capability/quality scoring.
- Introduce versioned dataset manifests/readers and optional indexed hot-query backend (SQLite/DuckDB) for historical APIs without changing default storage.
- Migrate streaming to a dedicated async/backpressured publisher and broaden contract tests for MCP/Discord consumers.
- Remove legacy shims only after deprecation window and production parity validation.
