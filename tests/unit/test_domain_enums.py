import pytest

from moj_projekt.domain.enums import (
    AlertType,
    CandidateStatus,
    EpistemicCategory,
    EvidenceRefKind,
    ImpactDirection,
    ImpactHorizon,
    Instrument,
    LifecycleStatus,
    OverrideState,
    RelationType,
    SourceTier,
    ValidityStatus,
)


def test_source_tier_has_the_four_documented_tiers() -> None:
    assert SourceTier.PRIMARY == 1
    assert SourceTier.PROFESSIONAL == 2
    assert SourceTier.SPECIALIST == 3
    assert SourceTier.SOCIAL == 4
    assert {tier.value for tier in SourceTier} == {1, 2, 3, 4}


def test_validity_status_matches_domain_model() -> None:
    assert {status.value for status in ValidityStatus} == {
        "candidate",
        "supported",
        "confirmed",
        "disputed",
        "invalid",
        "rejected",
    }


def test_lifecycle_status_excludes_dimensions_that_are_not_lifecycle() -> None:
    values = {status.value for status in LifecycleStatus}
    assert values == {"emerging", "active", "fading", "dormant", "resolved"}
    # These describe NarrativeDynamics or other axes, not lifecycle - see
    # DOMAIN_MODEL.md section 4.
    assert "accelerating" not in values
    assert "dominant" not in values
    assert "recurring" not in values


def test_impact_direction_matches_domain_model() -> None:
    assert {direction.value for direction in ImpactDirection} == {
        "strongly_bearish",
        "bearish",
        "mixed",
        "neutral",
        "bullish",
        "strongly_bullish",
        "uncertain",
    }


def test_impact_horizon_matches_domain_model() -> None:
    assert {horizon.value for horizon in ImpactHorizon} == {
        "intraday",
        "multi_day",
        "unknown",
    }


def test_override_state_matches_domain_model() -> None:
    assert {state.value for state in OverrideState} == {
        "none",
        "user_preferred",
        "user_locked",
    }


def test_candidate_status_matches_domain_model() -> None:
    assert {status.value for status in CandidateStatus} == {
        "accepted",
        "proposed",
        "rejected",
    }


def test_epistemic_category_matches_domain_model() -> None:
    assert {category.value for category in EpistemicCategory} == {
        "observed_fact",
        "source_claim",
        "model_inference",
        "system_metric",
        "market_evidence",
    }


def test_relation_type_matches_domain_model() -> None:
    assert {relation.value for relation in RelationType} == {
        "related_to",
        "causes",
        "contributes_to",
        "contradicts",
        "parent_of",
        "merged_into",
    }


def test_instrument_is_the_closed_mvp_set() -> None:
    assert {instrument.value for instrument in Instrument} == {"NQ", "BTC", "GOLD"}


def test_evidence_ref_kind_covers_document_event_and_fact() -> None:
    assert {kind.value for kind in EvidenceRefKind} == {"document", "event", "fact"}


def test_alert_type_matches_domain_model_initial_types() -> None:
    assert {alert_type.value for alert_type in AlertType} == {
        "emerging_narrative",
        "confirmed_narrative",
        "narrative_acceleration",
        "high_impact_event_added_to_narrative",
        "conflicting_information",
        "unconfirmed_social_hype",
    }


@pytest.mark.parametrize(
    "enum_type",
    [
        ValidityStatus,
        LifecycleStatus,
        ImpactDirection,
        ImpactHorizon,
        OverrideState,
        CandidateStatus,
        EpistemicCategory,
        RelationType,
        Instrument,
        EvidenceRefKind,
        AlertType,
    ],
)
def test_illegal_value_is_rejected_at_construction(enum_type: type) -> None:
    with pytest.raises(ValueError):
        enum_type("not-a-real-value")


def test_source_tier_illegal_value_is_rejected_at_construction() -> None:
    with pytest.raises(ValueError):
        SourceTier(99)
