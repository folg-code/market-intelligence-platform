import math

import pytest

from moj_projekt.domain.embedding import IdentityEmbedding


def test_valid_embedding_round_trips_its_fields() -> None:
    embedding = IdentityEmbedding(
        embedding_model="text-embedding-3-small",
        embedding_version="1",
        vector=(0.1, 0.2, 0.3),
    )

    assert embedding.embedding_model == "text-embedding-3-small"
    assert embedding.embedding_version == "1"
    assert embedding.vector == (0.1, 0.2, 0.3)


@pytest.mark.parametrize("embedding_model", ["", "   "])
def test_empty_embedding_model_is_rejected(embedding_model: str) -> None:
    with pytest.raises(ValueError):
        IdentityEmbedding(
            embedding_model=embedding_model, embedding_version="1", vector=(0.1,)
        )


@pytest.mark.parametrize("embedding_version", ["", "   "])
def test_empty_embedding_version_is_rejected(embedding_version: str) -> None:
    with pytest.raises(ValueError):
        IdentityEmbedding(
            embedding_model="model", embedding_version=embedding_version, vector=(0.1,)
        )


def test_empty_vector_is_rejected() -> None:
    with pytest.raises(ValueError):
        IdentityEmbedding(embedding_model="model", embedding_version="1", vector=())


def test_non_finite_vector_component_is_rejected() -> None:
    with pytest.raises(ValueError):
        IdentityEmbedding(
            embedding_model="model", embedding_version="1", vector=(0.1, math.nan)
        )
    with pytest.raises(ValueError):
        IdentityEmbedding(
            embedding_model="model", embedding_version="1", vector=(0.1, math.inf)
        )


def test_identity_embedding_is_immutable() -> None:
    embedding = IdentityEmbedding(
        embedding_model="model", embedding_version="1", vector=(0.1,)
    )

    with pytest.raises(AttributeError):
        embedding.embedding_version = "2"  # type: ignore[misc]
