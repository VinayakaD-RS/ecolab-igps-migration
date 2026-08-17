import logging

import env_constants
import query_manager
from entity_manager import EntityManager
from utility import setup_logging, write_json, read_json, get_in_batch

setup_logging("data/phase2/phase2.log")
logger = logging.getLogger(__name__)

ENTITY_GET_QUERY = "query/phase2-entity-get.json"


def run():
    entity_ids = read_json(env_constants.PHASE1_OUTPUT)
    logger.info("Loaded %d entity IDs from Phase 1.", len(entity_ids))

    manager = EntityManager(env_constants.ENV_NAME, env_constants.TENANT_NAME)
    template = query_manager.load_query_template(ENTITY_GET_QUERY)

    filtered_ids = []
    total_batches = (len(entity_ids) + env_constants.entity_batch_size - 1) // env_constants.entity_batch_size

    for batch_num, batch in enumerate(get_in_batch(entity_ids, env_constants.entity_batch_size), start=1):
        query = query_manager.replace_tokens_for_entity_ids_get(
            template, batch, env_constants.CREATED_DATE_CUTOFF
        )
        _, entities, _ = manager.get_entities_from_store(query)
        batch_ids = [e["id"] for e in entities]
        filtered_ids.extend(batch_ids)
        logger.info(
            "Batch %d/%d: sent %d IDs, %d passed date filter, running total %d",
            batch_num, total_batches, len(batch), len(batch_ids), len(filtered_ids),
        )

    write_json(env_constants.PHASE2_OUTPUT, filtered_ids)
    logger.info(
        "Phase 2 complete. %d of %d entities passed the createdDate filter. Written to %s",
        len(filtered_ids), len(entity_ids), env_constants.PHASE2_OUTPUT,
    )


if __name__ == "__main__":
    run()