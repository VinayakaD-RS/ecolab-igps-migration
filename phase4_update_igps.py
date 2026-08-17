import logging

import env_constants
import query_manager
from entity_manager import EntityManager
from utility import setup_logging, write_json, read_json

setup_logging("data/phase4/phase4.log")
logger = logging.getLogger(__name__)

UPDATE_QUERY = "query/phase4-update-igps.json"
ATTR_NAME = "initialgrmprocessstate"


def run():
    igps_map = read_json(env_constants.PHASE3_OUTPUT)
    logger.info("Loaded %d entity-to-IGPS mappings from Phase 3.", len(igps_map))

    manager = EntityManager(env_constants.ENV_NAME, env_constants.TENANT_NAME)
    template = query_manager.load_query_template(UPDATE_QUERY)

    succeeded = []
    failed = []

    for idx, (entity_id, gps_value) in enumerate(igps_map.items(), start=1):
        query = query_manager.replace_tokens_for_update(template, entity_id, ATTR_NAME, gps_value)
        try:
            response = manager.update_entity(query)
            if manager.is_success(response):
                succeeded.append(entity_id)
            else:
                failed.append({"entity_id": entity_id, "reason": "non-success response", "response": response})
                logger.error("Update failed for entity %s: %s", entity_id, response)
        except Exception as e:
            failed.append({"entity_id": entity_id, "reason": str(e)})
            logger.error("Exception updating entity %s: %s", entity_id, e)

        if idx % 100 == 0:
            logger.info("Progress: %d/%d processed (%d succeeded, %d failed)", idx, len(igps_map), len(succeeded), len(failed))

    write_json(env_constants.PHASE4_OUTPUT, {"succeeded": succeeded, "failed": failed})
    logger.info(
        "Phase 4 complete. %d succeeded, %d failed. Results written to %s",
        len(succeeded), len(failed), env_constants.PHASE4_OUTPUT,
    )


if __name__ == "__main__":
    run()