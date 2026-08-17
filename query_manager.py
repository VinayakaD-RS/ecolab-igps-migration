import json


def load_query_template(path):
    with open(path, "r") as f:
        return f.read()


def replace_scroll_id(query, scroll_id):
    return query.replace("@@SCROLL_ID@@", scroll_id or "")


def replace_entity_ids(query, entity_ids):
    return query.replace('"@@ENTITY_IDS@@"', json.dumps(entity_ids))


def replace_tokens_for_entity_ids_get(query, entity_ids, created_date_cutoff):
    query = replace_entity_ids(query, entity_ids)
    query = query.replace("@@CREATED_DATE_CUTOFF@@", created_date_cutoff)
    return query


def replace_entity_id(query, entity_id):
    return query.replace("@@ENTITY_ID@@", entity_id)


def replace_tokens_for_update(query, entity_id, attr_name, attr_value):
    query = query.replace("@@ENTITY_ID@@", entity_id)
    query = query.replace("@@ATTRIBUTE_NAME@@", attr_name)
    query = query.replace("@@ATTRIBUTE_VALUE@@", attr_value)
    return query