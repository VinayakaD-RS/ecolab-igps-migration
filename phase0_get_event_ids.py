import logging

import env_constants
import query_manager
from event_manager import EventManager
from utility import setup_logging, write_json

setup_logging("data/phase0/phase0.log")
logger = logging.getLogger(__name__)

PREPARE_SCROLL_QUERY = "query/phase0-events-prepare-scroll.json"
SCROLL_QUERY = "query/phase0-events-scroll.json"


def run():
    manager = EventManager(env_constants.ENV_NAME, env_constants.TENANT_NAME)
    event_ids = []

    initial_query = query_manager.load_query_template(PREPARE_SCROLL_QUERY)
    total, events, scroll_id = manager.get_events(initial_query)
    logger.info("Total matching events reported by server: %d", total)
    event_ids.extend(e["id"] for e in events)
    logger.info("Page 1: %d event IDs collected", len(event_ids))

    scroll_template = query_manager.load_query_template(SCROLL_QUERY)
    prev_scroll_id = scroll_id
    page = 2

    while scroll_id and scroll_id not in ("", "invalid"):
        prev_scroll_id = scroll_id
        query = query_manager.replace_scroll_id(scroll_template, scroll_id)
        _, events, scroll_id = manager.get_events(query)
        event_ids.extend(e["id"] for e in events)
        logger.info("Page %d: %d event IDs collected so far", page, len(event_ids))
        page += 1

    if prev_scroll_id:
        try:
            manager.clear_scroll(prev_scroll_id)
            logger.info("Scroll cleared.")
        except Exception as e:
            logger.warning("Failed to clear scroll: %s", e)

    write_json(env_constants.PHASE0_OUTPUT, event_ids)
    logger.info("Phase 0 complete. %d event IDs written to %s", len(event_ids), env_constants.PHASE0_OUTPUT)


if __name__ == "__main__":
    run()