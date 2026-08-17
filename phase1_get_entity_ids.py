import logging

import env_constants
import query_manager
from event_manager import EventManager
from utility import setup_logging, write_json, read_json, get_in_batch

setup_logging("data/phase1/phase1.log")
logger = logging.getLogger(__name__)

EVENTS_GET_QUERY = "query/phase1-events-get-by-ids.json"


def _extract_entity_ids(events):
    ids = []
    for event in events:
        try:
            entity_id = event["data"]["attributes"]["entityId"]["values"][0]["value"]
            ids.append(entity_id)
        except (KeyError, IndexError):
            logger.warning("Could not extract entityId from event %s", event.get("id"))
    return ids


def run():
    event_ids = read_json(env_constants.PHASE0_OUTPUT)
    logger.info("Loaded %d event IDs from Phase 0.", len(event_ids))

    manager = EventManager(env_constants.ENV_NAME, env_constants.TENANT_NAME)
    template = query_manager.load_query_template(EVENTS_GET_QUERY)

    all_entity_ids = set()
    total_batches = (len(event_ids) + env_constants.entity_batch_size - 1) // env_constants.entity_batch_size

    for batch_num, batch in enumerate(get_in_batch(event_ids, env_constants.entity_batch_size), start=1):
        query = query_manager.replace_entity_ids(template, batch)
        _, events, _ = manager.get_events(query)
        batch_entity_ids = _extract_entity_ids(events)
        all_entity_ids.update(batch_entity_ids)
        logger.info(
            "Batch %d/%d: fetched %d events, %d unique entity IDs so far",
            batch_num, total_batches, len(events), len(all_entity_ids),
        )

    entity_ids = list(all_entity_ids)
    write_json(env_constants.PHASE1_OUTPUT, entity_ids)
    logger.info("Phase 1 complete. %d unique entity IDs written to %s", len(entity_ids), env_constants.PHASE1_OUTPUT)


if __name__ == "__main__":
    run()