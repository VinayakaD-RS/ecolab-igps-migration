# IGPS Migration — Backfill `initialgrmprocessstate` for Ecolab

## Problem

When a source record enters the GRM (Golden Record Management) process on the Riversand Data Platform, it is
assigned a **GRM state** (`new`, `updated`, `done`, `in review`) and a **GRM process state**
(`Auto Create`, `Auto Merge`, `Manual Merge`, `In Review`).

A feature was introduced to capture the **initial** GRM process state — the first process state recorded for
an entity — in a dedicated attribute called `initialgrmprocessstate`. This attribute is set once when the
entity's GRM state first transitions away from `new` or `updated`, and never overwritten by subsequent changes.

**The gap:** For Ecolab (`ecolabuat`), a subset of `baseCustomerAccount` entities were originally created with
their first GRM state set to `updated` (rather than `new`). The backfill feature was only triggered for
transitions from `new → <value>`, so these entities — whose first transition was `updated → <value>` — never
had `initialgrmprocessstate` populated.

This script identifies those affected entities and backfills the correct value.

---

## How it works

The migration runs in five isolated phases. Each phase writes its output to a JSON file that the next phase
reads as input. This means any phase can be re-run independently if it fails mid-way.

```
Phase 0  →  data/phase0/event_ids.json
Phase 1  →  data/phase1/entity_ids.json
Phase 2  →  data/phase2/filtered_ids.json
Phase 3  →  data/phase3/igps_map.json  +  warnings.json
Phase 4  →  data/phase4/results.json
```

### Phase 0 — Collect matching event IDs
Scrolls the **event service** (`api/eventservice`) for `entitymanageevent` records where:
- `previous-grmstate` has no value (i.e. this was the very first GRM state transition)
- `grmstate` = `update` (the first state assigned was `updated`)
- `entityType` = `baseCustomerAccount`

Uses scroll pagination to collect all matching event IDs and persists them.

### Phase 1 — Extract affected entity IDs
Batch-fetches the full event records (up to 2 000 per request) using the event IDs from Phase 0.
Extracts the `entityId` attribute from each event and deduplicates — this is the list of
`baseCustomerAccount` entities that are potentially affected.

### Phase 2 — Filter by created date
Batch-fetches entity metadata (up to 2 000 per request) from the **entity service** (`api/entityappservice`).
Retains only entities whose `createdDate` is on or after `CREATED_DATE_CUTOFF` (default: 6 months lookback).
Entities created before the cutoff are excluded from the migration.

### Phase 3 — Find the initial GRM process state
For each filtered entity, calls `api/entityappservice/getentityhistory` to retrieve its history.
The history is sorted ascending by `modifiedDate` and filtered to entries where `grmprocessstate` has a value.
The **first** such entry is the initial GRM process state. Results are written as a map
`{ "entity_id": "grmprocessstate_value" }`.

Entities with no matching history entry are skipped and recorded in `data/phase3/warnings.json` for review.

### Phase 4 — Backfill `initialgrmprocessstate`
For each entity in the Phase 3 map, posts an entity update to set `initialgrmprocessstate` to the discovered
value. Outcomes are written to `data/phase4/results.json` as `{ "succeeded": [...], "failed": [...] }`.

> **Note:** Phase 4 is commented out in `main.py` by default. Uncomment it only after verifying the
> Phase 3 output looks correct.

---

## Setup

### Requirements
```
pip install requests
```

### Configuration — `env_constants.py`

All environment-specific values are set in `env_constants.py`. Nothing else needs to be changed to target a
different environment or tenant.

| Variable | Description | Example |
|---|---|---|
| `ENV_NAME` | Pod / environment name | `"rdpprna26"` |
| `TENANT_NAME` | Tenant identifier | `"ecolabuat"` |
| `use_proxy` | `True` → route via PIM API proxy (use from a dev machine); `False` → connect directly to the pod (use when running inside the cluster) | `True` |
| `BEARER_TOKEN` | Azure AD bearer token. Expires after ~8 hours — regenerate and paste a fresh token here if you get HTTP 401 responses. | `"eyJ..."` |
| `CREATED_DATE_CUTOFF` | ISO 8601 timestamp. Entities created **before** this date are excluded in Phase 2. Update this when running the migration for a different lookback window. | `"2026-02-17T00:00:00.000-0500"` |
| `entity_batch_size` | Number of IDs sent per batch request in Phases 1 and 2. Maximum supported by the platform is 2 000. | `2000` |
| `MAX_WORKERS` | Thread concurrency for Phase 3 (parallel history lookups). | `10` |

---

## Execution

### Run all phases end-to-end
```bash
python main.py
```

### Run a single phase
Each phase script is independently executable:
```bash
python phase0_get_event_ids.py
python phase1_get_entity_ids.py
python phase2_filter_by_created_date.py
python phase3_find_igps.py
python phase4_update_igps.py
```

### Enable Phase 4 (the write step)
Phase 4 is disabled by default in `main.py`. Review `data/phase3/igps_map.json` first, then uncomment:
```python
# in main.py
("Phase 4 — Update initialgrmprocessstate", phase4_update_igps.run),
```

---

## Output files

| File | Contents |
|---|---|
| `data/phase0/event_ids.json` | List of event IDs matching the GRM state criteria |
| `data/phase0/phase0.log` | Phase 0 execution log |
| `data/phase1/entity_ids.json` | Deduplicated list of affected `baseCustomerAccount` entity IDs |
| `data/phase1/phase1.log` | Phase 1 execution log |
| `data/phase2/filtered_ids.json` | Entity IDs that passed the created-date filter |
| `data/phase2/phase2.log` | Phase 2 execution log |
| `data/phase3/igps_map.json` | Map of `entity_id → initial grmprocessstate value` |
| `data/phase3/warnings.json` | Entity IDs with no `grmprocessstate` found in history (skipped) |
| `data/phase3/phase3.log` | Phase 3 execution log |
| `data/phase4/results.json` | `{ "succeeded": [...], "failed": [...] }` per-entity update results |
| `data/phase4/phase4.log` | Phase 4 execution log |

---

## Project structure

```
igps-migration/
├── main.py                          # Entry point — runs all phases in sequence
├── env_constants.py                 # All environment configuration
├── event_manager.py                 # Event service API client (api/eventservice)
├── entity_manager.py                # Entity service API client (api/entityappservice)
├── query_manager.py                 # JSON template loading and token replacement
├── rest_client.py                   # HTTP client with pooling and retries
├── utility.py                       # File I/O and batch utilities
│
├── phase0_get_event_ids.py          # Scroll events → event IDs
├── phase1_get_entity_ids.py         # Fetch events by ID → entity IDs
├── phase2_filter_by_created_date.py # Filter by createdDate
├── phase3_find_igps.py              # History lookup → igps map
├── phase4_update_igps.py            # Write initialgrmprocessstate
│
└── query/
    ├── phase0-events-prepare-scroll.json   # Initial scroll query (isIdOnly)
    ├── phase0-events-scroll.json           # Scroll continuation query
    ├── phase1-events-get-by-ids.json       # Fetch full events by IDs
    ├── phase2-entity-get.json              # Entity get with createdDate filter
    ├── phase3-entity-history.json          # Entity history for single entity
    ├── phase4-update-igps.json             # initialgrmprocessstate update
    └── scroll-queries/
        └── clearscroll_template.json       # Releases server-side scroll context
```
