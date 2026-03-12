from cachetools import TTLCache
import uuid

# Store max 100 dashboards
# Expire after 30 minutes
dashboard_cache = TTLCache(maxsize=100, ttl=1800)


def create_dashboard(data):
    dashboard_id = str(uuid.uuid4())
    dashboard_cache[dashboard_id] = data
    return dashboard_id


def get_dashboard(dashboard_id):
    return dashboard_cache.get(dashboard_id)


def delete_dashboard(dashboard_id):
    if dashboard_id in dashboard_cache:
        del dashboard_cache[dashboard_id]