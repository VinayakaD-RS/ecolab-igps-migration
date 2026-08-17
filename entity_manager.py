import env_constants
import query_manager
from rest_client import RestClient

ENTITY_APP_SERVICE_URL = "http://rdp-rest:8085/@@TENANT@@/api/entityappservice"
ENTITY_APP_SERVICE_URL_PROXY = "http://pimapiproxy.syndigo.com:8000/@@ENVNAME@@/@@TENANT@@/api/entityappservice"


class EntityManager:
    def __init__(self, env_name, tenant):
        self.base_url = self._build_url(env_name, tenant)
        self.client = RestClient(
            self.base_url,
            headers={
                "Authorization": f"Bearer {env_constants.BEARER_TOKEN}",
                "x-rdp-userId": "system",
                "Content-Type": "application/json",
            },
        )

    def _build_url(self, env_name, tenant):
        template = ENTITY_APP_SERVICE_URL_PROXY if env_constants.use_proxy else ENTITY_APP_SERVICE_URL
        return template.replace("@@ENVNAME@@", env_name).replace("@@TENANT@@", tenant)

    def get_entities_from_store(self, query):
        response = self.client.post("/get", data=query)
        resp = response.get("response", {})
        return (
            resp.get("totalRecords", 0),
            resp.get("entities", []),
            resp.get("scrollId"),
        )

    def get_entity_history(self, query):
        response = self.client.post("/getentityhistory", data=query)
        return response.get("response", {}).get("entities", [])

    def update_entity(self, query):
        return self.client.post("/update", data=query)

    def clear_scroll(self, scroll_id):
        template = query_manager.load_query_template("query/scroll-queries/clearscroll_template.json")
        query = template.replace("@@SCROLL_ID@@", scroll_id)
        self.client.post("/clearscroll", data=query)

    @staticmethod
    def is_success(response):
        return response.get("response", {}).get("status") == "success"