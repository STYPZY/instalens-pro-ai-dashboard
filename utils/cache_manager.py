from cachetools import TTLCache
import uuid
import logging

logger = logging.getLogger(__name__)

# Store max 100 dashboards
# Expire after 30 minutes
dashboard_cache = TTLCache(maxsize=100, ttl=1800)


def create_dashboard(data):
    """Create a new dashboard entry with unique ID"""
    dashboard_id = str(uuid.uuid4())
    dashboard_cache[dashboard_id] = data
    logger.info(f"Created dashboard: {dashboard_id}")
    return dashboard_id


def get_dashboard(dashboard_id):
    """Retrieve a dashboard by ID"""
    return dashboard_cache.get(dashboard_id)


def delete_dashboard(dashboard_id):
    """Delete a dashboard entry"""
    if dashboard_id in dashboard_cache:
        del dashboard_cache[dashboard_id]
        logger.info(f"Deleted dashboard: {dashboard_id}")
        return True
    return False


def get_cache_stats():
    """Get cache statistics"""
    return {
        "size": len(dashboard_cache),
        "max_size": dashboard_cache.maxsize,
        "ttl": dashboard_cache.ttl
    }