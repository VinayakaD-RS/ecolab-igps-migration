# RDP Entity Operations — Boilerplate Guide

This document describes how to build a Python project that interacts with the Riversand Data Platform (RDP) REST API.
It covers entity GET, events GET, and entity UPDATE operations, including how the REST client, URL patterns,
authentication, query templates, and constants are wired together.

---

## Project Layout

```
project/
├── env_constants.py        # All configurable settings (env, tenant, token, batch sizes)
├── rest_client.py          # Reusable HTTP client with pooling + retries
├── query_manager.py        # Load JSON query templates; replace @@TOKEN@@ placeholders
├── entity_manager.py       # High-level entity operations (get, update, delete, orphan checks)
├── utility.py              # File I/O, batch generators, folder helpers
├── query/                  # JSON query templates (one file per operation type)
│   ├── clearscroll_template.json   # Always needed when using scroll pagination
│   └── <script-specific>.json     # Add query files as your script requires
└── data/                   # Output directory (created at runtime, structure depends on script)
```

---

## Environment Constants (`env_constants.py`)

All environment-specific values live here. A script reads these at startup; nothing is hard-coded elsewhere.

```python
ENV_NAME        = "rdpprna26"      # Pod / environment name
TENANT_NAME     = "ecolabuat"      # Tenant identifier
use_proxy       = True             # True → PIM proxy URL; False → direct pod URL
BEARER_TOKEN    = "eyJ..."         # Azure AD bearer token (rotate frequently)

# Entity type
ENTITY_TYPE     = "customerSite"

# Batch / concurrency
entity_batch_size   = 2000
platform_batch_size = 2000
search_terms        = 10000
MAX_WORKERS         = 10
FILE_WORKERS        = 4

# Workflow flags
FETCH_ENTITIES_FIRST = True
```

**To target a different environment:** change `ENV_NAME`, `TENANT_NAME`, `BEARER_TOKEN`, and optionally flip `use_proxy`. Output paths and any other script-specific constants should be added as needed per script.

---

## URL Patterns

There are two ways to reach `entityappservice`:

### Via PIM API Proxy (default, `use_proxy = True`)

```
http://pimapiproxy.syndigo.com:8000/@@ENVNAME@@/@@TENANT@@/api/entityappservice
```

- External proxy that routes to the correct pod.
- Use this when running from a developer machine or outside the pod network.
- Tokens `@@ENVNAME@@` and `@@TENANT@@` are replaced at runtime by `EntityManager._build_url()`.

### Direct to Pod (`use_proxy = False`)

```
http://rdp-rest:8085/@@TENANT@@/api/entityappservice
```

- Connects directly to the `rdp-rest` service inside the pod's network.
- Use this when the script runs inside the Kubernetes cluster or on the pod itself.
- Only the `@@TENANT@@` token is replaced; `@@ENVNAME@@` is not part of the direct URL.

**In `entity_manager.py`:**

```python
ENTITY_APP_SERVICE_URL       = "http://rdp-rest:8085/@@TENANT@@/api/entityappservice"
ENTITY_APP_SERVICE_URL_PROXY = "http://pimapiproxy.syndigo.com:8000/@@ENVNAME@@/@@TENANT@@/api/entityappservice"

self.base_url = self._build_url(
    ENTITY_APP_SERVICE_URL_PROXY if env_constants.use_proxy else ENTITY_APP_SERVICE_URL,
    env_name, tenant
)
```

---

## Authentication — Bearer Token

All requests require an Azure AD bearer token passed as an `Authorization` header.

```python
headers = {
    "Authorization": f"Bearer {BEARER_TOKEN}",
    "x-rdp-userId": "system",
    "Content-Type": "application/json"   # only for POST with a body
}
```

- `BEARER_TOKEN` is defined in `env_constants.py`.
- Tokens expire (typically 8 hours). When a request returns HTTP 401, generate a new token and update `BEARER_TOKEN`.
- `x-rdp-userId` identifies the caller to RDP audit logs; `"system"` is the conventional value for automation scripts.

The `EntityManager._get_client()` method builds a `RestClient` instance with these headers pre-attached, so
individual API call sites never need to set headers manually.

---

## REST Client (`rest_client.py`)

`RestClient` is a thin wrapper around `requests` that adds:

| Feature | Detail |
|---|---|
| Connection pooling | Class-level `_session_pool` keyed by `base_url`; sessions are reused across calls |
| Auto-retry | 3 retries, 0.5s backoff factor, on HTTP 429/500/502/503/504 |
| Pool size | 20 connections, 50 max size via `HTTPAdapter` |
| Response handling | Returns `dict` for `application/json` responses, raw `str` otherwise |
| Error surfacing | Calls `response.raise_for_status()` and re-raises `HTTPError` |

```python
from rest_client import RestClient

client = RestClient(base_url, headers={"Authorization": f"Bearer {token}"})

# GET
data = client.get("/some/endpoint", params={"key": "value"})

# POST with JSON string body
data = client.post("/get", data=json_string)

# POST with dict body (auto-serialized)
data = client.post("/update", json={"entity": {...}})

# DELETE
data = client.delete("/delete/some-id")
```

Instantiating `RestClient` with the same `base_url` twice returns the same underlying session from the pool —
you do not need to keep a singleton reference yourself.

---

## Query Manager (`query_manager.py`)

Query templates are JSON files stored under `query/`. They contain `@@TOKEN@@` placeholders that are replaced
at runtime with actual values. This keeps query structure visible and version-controlled while keeping logic
in Python.

### Loading a template

```python
import query_manager

template_str = query_manager.load_query_template("query/migrated-entities-query.json")
```

`load_query_template` reads the file as a raw string (not parsed JSON) so that token replacement via
`str.replace()` is safe.

### Token replacement functions

| Function | Tokens replaced |
|---|---|
| `replace_tokens_for_entity_get(q, entity_type, scroll_id)` | `@@ENTITY_TYPE@@`, `@@SCROLL_ID@@` |
| `replace_tokens_for_events(q, entity_ids, scroll_id)` | `"@@ENTITY_IDS@@"`, `@@SCROLL_ID@@` |
| `replace_tokens_to_get_parent(q, rel_to_ids, parent_type, orphan_type, rel_name)` | `"@@REL_TO_IDS@@"`, `@@PARENT_ENTITY_TYPE@@`, `@@ORPHAN_TYPE@@`, `@@ORPHAN_REL_NAME@@` |
| `replace_tokens_for_entity_update(q, entity_id, attr_name, attr_value)` | `@@ENTITY_ID@@`, `@@ATTRIBUTE_NAME@@`, `@@ATTRIBUTE_VALUE@@` |

`entity_ids` and `rel_to_ids` are Python lists — they are injected as JSON arrays by replacing the quoted
placeholder `"@@ENTITY_IDS@@"` (note the surrounding quotes in the template) with `json.dumps(list)`.

---

## Query Templates (`query/`)

### Entity GET — initial scroll (`migrated-entities-query.json`)

```json
{
  "params": {
    "prepareScroll": true,
    "query": {
      "filters": {
        "typesCriterion": ["@@ENTITY_TYPE@@"]
      }
    },
    "sort": {
      "properties": [{"modifiedDate": "_ASC", "sortType": "_DATETIME"}]
    },
    "options": {"isIdOnly": true}
  }
}
```

- `prepareScroll: true` tells RDP to return a `scrollId` for pagination.
- `isIdOnly: true` returns only entity IDs, reducing payload size.

### Entity GET — continue scroll (`migrated-entities-scroll-query.json`)

```json
{
  "params": {
    "scrollId": "@@SCROLL_ID@@",
    "query": {
      "filters": {
        "typesCriterion": ["@@ENTITY_TYPE@@"]
      }
    },
    "sort": {
      "properties": [{"modifiedDate": "_ASC", "sortType": "_DATETIME"}]
    },
    "options": {"isIdOnly": true}
  }
}
```

Pass the `scrollId` from the previous response to get the next page.

### Clear Scroll (`clearscroll_template.json`)

```json
{
  "params": {
    "scrollId": "@@SCROLL_ID@@"
  }
}
```

Always call `/clearscroll` after you are done paginating to release server-side resources.

### Parent relationship lookup (`get_parent_template.json`)

```json
{
  "params": {
    "query": {
      "filters": {
        "typesCriterion": ["baseCustomerAccount"],
        "relationshipsCriterion": [{
          "@@ORPHAN_REL_NAME@@": {
            "relTo": {
              "ids": "@@REL_TO_IDS@@",
              "type": "@@ORPHAN_TYPE@@"
            }
          }
        }]
      }
    },
    "fields": {
      "relationships": ["@@ORPHAN_REL_NAME@@"]
    }
  }
}
```

---

## Entity Manager (`entity_manager.py`)

`EntityManager` is the main interface for all RDP operations. Initialize it with an env name and tenant:

```python
from entity_manager import EntityManager
import env_constants

manager = EntityManager(env_constants.ENV_NAME, env_constants.TENANT_NAME)
```

### Entity GET (with scroll pagination)

RDP's entityappservice uses a scroll API for large result sets. The pattern is:

1. POST to `/get` with `prepareScroll: true` → get first page + `scrollId`
2. POST to `/get` with the `scrollId` → get next page
3. Repeat until `scrollId` is `""`, `None`, or `"invalid"`
4. POST to `/clearscroll` with the final `scrollId`

```python
import query_manager

# Step 1 — initial fetch
template = query_manager.load_query_template("query/migrated-entities-query.json")
query = query_manager.replace_tokens_for_entity_get(template, "customerSite", None)

ids, scroll_id = manager.get_entity_ids_from_store(query)

# Step 2 — paginate
while scroll_id and scroll_id not in ("", "invalid"):
    scroll_template = query_manager.load_query_template("query/migrated-entities-scroll-query.json")
    scroll_query = query_manager.replace_tokens_for_entity_get(scroll_template, "customerSite", scroll_id)
    ids, scroll_id = manager.get_entity_ids_from_store(scroll_query)
```

For bulk ID collection with async file writes, call the higher-level helper:

```python
manager.get_and_persist_entity_ids(query)
# Writes paginated batches to data/<entity-type>-ids/entities_0.json, entities_1.json, ...
```

### Full Entity GET (with metadata)

When you need full entity objects instead of just IDs:

```python
total_records, entities = manager.get_entities_from_store(query)
# entities is a list of dicts from response["response"]["entities"]
```

### Events GET

Events follow the same scroll pattern but use `replace_tokens_for_events`:

```python
event_template = query_manager.load_query_template("query/your-events-query.json")
query = query_manager.replace_tokens_for_events(event_template, entity_ids_list, None)
total, entities = manager.get_entities_from_store(query)
```

The events query template should include `"@@ENTITY_IDS@@"` (with surrounding quotes) where the ID array goes:

```json
{
  "params": {
    "query": {
      "filters": {
        "typesCriterion": ["entitygovernactivity"],
        "ids": "@@ENTITY_IDS@@"
      }
    }
  }
}
```

### Entity UPDATE

```python
update_template = query_manager.load_query_template("query/your-update-query.json")
query = manager.get_update_query(update_template, entity_id, "attributeName", "newValue")
response = manager.update_entity(query)

if manager.is_success(response):
    print("Updated successfully")
```

Update template example:

```json
{
  "entity": {
    "id": "@@ENTITY_ID@@",
    "type": "customerSite",
    "data": {
      "attributes": {
        "@@ATTRIBUTE_NAME@@": {
          "values": [{"value": "@@ATTRIBUTE_VALUE@@", "source": "internal", "locale": "en-US"}]
        }
      }
    }
  }
}
```

### Entity DELETE

```python
response = manager.delete_entity(entity_id, entity_type)
```

Internally posts `{"entity": {"id": ..., "type": ...}}` to `/delete`.

---

## Utility Module (`utility.py`)

### Batch processing

```python
from utility import get_in_batch

for batch in get_in_batch(large_list, batch_size=2000):
    process(batch)
```

### Writing output to the `data/` folder

```python
from utility import persist_entities_in_file, persist_data_in_file, persist_in_file

# Write a list of IDs as entities_0.json, entities_1.json ...
persist_entities_in_file("data/customerSite-ids", count=0, entity_ids=["id1", "id2"])

# Write arbitrary data to a named file
persist_data_in_file("data/Orphan-customerSite", "batch_0.json", orphan_list)

# Write a single dict
persist_in_file("data/summary.json", {"total": 500, "orphans": 42})
```

### Reading back

```python
from utility import read_list_from_file, read_files_from_folder

ids = read_list_from_file("data/some-file.txt")          # comma-separated
for filename, content in read_files_from_folder("data/customerSite-ids"):
    ids = json.loads(content)
```

---

## Minimal Boilerplate Script

This is the minimum skeleton to fetch all entities of a type and write their IDs to disk:

```python
import json
import env_constants
import query_manager
from entity_manager import EntityManager
from utility import persist_entities_in_file

manager = EntityManager(env_constants.ENV_NAME, env_constants.TENANT_NAME)

template = query_manager.load_query_template("query/migrated-entities-query.json")
query = query_manager.replace_tokens_for_entity_get(template, env_constants.ORPHAN_TYPE, None)

ids, scroll_id = manager.get_entity_ids_from_store(query)
batch = 0
persist_entities_in_file(env_constants.CUSTOMER_SITE_IDS_PATH, batch, ids)

while scroll_id and scroll_id not in ("", "invalid"):
    scroll_template = query_manager.load_query_template("query/migrated-entities-scroll-query.json")
    scroll_query = query_manager.replace_tokens_for_entity_get(
        scroll_template, env_constants.ORPHAN_TYPE, scroll_id
    )
    ids, scroll_id = manager.get_entity_ids_from_store(scroll_query)
    if ids:
        batch += 1
        persist_entities_in_file(env_constants.CUSTOMER_SITE_IDS_PATH, batch, ids)

print(f"Done. {batch + 1} batch files written to {env_constants.CUSTOMER_SITE_IDS_PATH}/")
```

---

## API Response Structure

All `/get`, `/update`, and `/delete` responses from entityappservice share the same envelope:

```json
{
  "response": {
    "status": "success",
    "totalRecords": 12345,
    "scrollId": "abc123...",
    "entities": [
      {"id": "ent001", "type": "customerSite", "data": {...}},
      ...
    ]
  }
}
```

| Field | Where used |
|---|---|
| `response.status` | `manager.is_success(response)` checks for `"success"` |
| `response.totalRecords` | Used to decide whether to split batches (> 2000 triggers recursive split) |
| `response.scrollId` | Passed to the next scroll query; empty/`"invalid"` means last page |
| `response.entities` | Extracted by `_parse_entities()` or `_parse_entity_ids()` |

---

## Concurrency

`entity_manager.py` uses `ThreadPoolExecutor` for async file writes so API calls are not blocked by disk I/O:

```python
_file_write_executor = ThreadPoolExecutor(max_workers=4)

future = _file_write_executor.submit(persist_entities_in_file, path, count, ids)
```

The caller collects futures and calls `future.result()` before exiting to ensure all writes complete.

For parallel batch processing, caller scripts use their own `ThreadPoolExecutor` with `MAX_WORKERS` from
`env_constants`.

---

## Common Pitfalls

| Problem | Fix |
|---|---|
| HTTP 401 | Bearer token expired — generate a new one and update `BEARER_TOKEN` in `env_constants.py` |
| `scrollId` keeps returning `"invalid"` | Token expired mid-scroll; restart with a fresh token |
| `totalRecords > 2000` on parent lookup | EntityManager auto-splits the batch recursively (max depth 10) |
| File writes incomplete on crash | Always iterate `future.result()` in a `finally` block |
| Wrong URL | Verify `use_proxy` matches your network context (machine vs inside pod) |
