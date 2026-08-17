import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import env_constants
import query_manager
from entity_manager import EntityManager
from utility import setup_logging, write_json, read_json

setup_logging("data/phase3/phase3.log")
logger = logging.getLogger(__name__)

HISTORY_QUERY = "query/phase3-entity-history.json"


def _get_igps_for_entity(manager, template, entity_id):
    query = query_manager.replace_entity_id(template, entity_id)
    entities = manager.get_entity_history(query)
    if not entities:
        return entity_id, None
    try:
        gps = entities[0]["data"]["attributes"]["grmprocessstate"]["values"][0]["value"]
        return entity_id, gps
    except (KeyError, IndexError):
        return entity_id, None


def run():
    entity_ids = read_json(env_constants.PHASE2_OUTPUT)
    logger.info("Loaded %d entity IDs from Phase 2.", len(entity_ids))

    manager = EntityManager(env_constants.ENV_NAME, env_constants.TENANT_NAME)
    template = query_manager.load_query_template(HISTORY_QUERY)

    igps_map = {}
    warnings = []
    completed = 0

    with ThreadPoolExecutor(max_workers=env_constants.MAX_WORKERS) as executor:
        futures = {
            executor.submit(_get_igps_for_entity, manager, template, eid): eid
            for eid in entity_ids
        }
        for future in as_completed(futures):
            entity_id = futures[future]
            try:
                eid, gps = future.result()
                if gps is None:
                    warnings.append(eid)
                    logger.warning("No grmprocessstate found in history for entity: %s", eid)
                else:
                    igps_map[eid] = gps
            except Exception as e:
                warnings.append(entity_id)
                logger.error("Exception fetching history for entity %s: %s", entity_id, e)

            completed += 1
            if completed % 100 == 0:
                logger.info("Progress: %d/%d processed", completed, len(entity_ids))

    write_json(env_constants.PHASE3_OUTPUT, igps_map)
    write_json(env_constants.PHASE3_WARNINGS, warnings)
    logger.info(
        "Phase 3 complete. %d entities mapped, %d warnings. Written to %s and %s",
        len(igps_map), len(warnings), env_constants.PHASE3_OUTPUT, env_constants.PHASE3_WARNINGS,
    )


if __name__ == "__main__":
    run()