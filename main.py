import logging

import phase0_get_event_ids
import phase1_get_entity_ids
import phase2_filter_by_created_date
import phase3_find_igps
import phase4_update_igps

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

PHASES = [
    ("Phase 0 — Scroll events, collect event IDs",    phase0_get_event_ids.run),
    ("Phase 1 — Batch fetch events, extract entity IDs", phase1_get_entity_ids.run),
    ("Phase 2 — Filter entities by created date",     phase2_filter_by_created_date.run),
    ("Phase 3 — Find initial GRM process state",      phase3_find_igps.run),
    # ("Phase 4 — Update initialgrmprocessstate",       phase4_update_igps.run),
]

if __name__ == "__main__":
    for label, phase_fn in PHASES:
        logger.info("=" * 60)
        logger.info("Starting: %s", label)
        logger.info("=" * 60)
        phase_fn()
        logger.info("Finished: %s", label)
    logger.info("All phases complete.")
