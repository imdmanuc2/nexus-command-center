from backend.db.repositories.recommendation_repository import (
    list_recommendations,
    recommendation_summary,
)


def recommendations():
    records = list_recommendations(limit=100)
    return {
        "status": "ok",
        "source": "nexus-postgresql-platform-recommendations",
        "count": len(records),
        "recommendations": records,
    }


def high_priority():
    records = [
        recommendation
        for recommendation in list_recommendations(limit=250)
        if recommendation["status"] in {"open", "accepted"}
        and recommendation["priority"] in {"critical", "high"}
    ]
    return {
        "status": "ok",
        "source": "nexus-postgresql-platform-recommendations",
        "count": len(records),
        "recommendations": records,
    }


def summary():
    return {
        "status": "ok",
        "source": "nexus-postgresql-platform-recommendations",
        **recommendation_summary(),
    }
