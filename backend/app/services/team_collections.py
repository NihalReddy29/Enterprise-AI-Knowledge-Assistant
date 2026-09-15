"""Helpers for per-team isolated Qdrant/vector collections."""

import logging

from app.models.team import Team
from app.services.embeddings import get_embedding_service
from app.services.vector_store import get_vector_store

logger = logging.getLogger(__name__)


def ensure_team_collection(team: Team) -> None:
    """Create the team's dedicated vector collection if it does not exist."""
    store = get_vector_store()
    embeddings = get_embedding_service()
    store.ensure_collection(embeddings.dimension, collection_name=team.qdrant_collection_name)
    logger.info("Ensured vector collection %s for team %d", team.qdrant_collection_name, team.id)


def delete_team_collection(team: Team) -> None:
    """Remove the team's vector collection."""
    store = get_vector_store()
    try:
        store.delete_collection(team.qdrant_collection_name)
        logger.info("Deleted vector collection %s for team %d", team.qdrant_collection_name, team.id)
    except NotImplementedError:
        logger.warning(
            "Vector store does not support collection deletion; team %d vectors may remain",
            team.id,
        )
    except Exception:
        logger.exception("Failed to delete vector collection %s", team.qdrant_collection_name)
