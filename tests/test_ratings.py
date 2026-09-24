from data.models import AppData


def test_old_ratings_survive_scale_change_and_are_marked_for_review():
    data = AppData.from_dict({
        "pair_ratings": {"AB": 3},
        "rating_color_levels": 3,
        "rating_color_hexes": ["#D32F2F", "#F9A825", "#2E7D32"],
        "rating_color_grades": [1, 3, 5],
    })
    assert data.pair_ratings["AB"] == 3
    assert data.pair_rating_versions["AB"] == data.rating_scale_version


def test_rating_metadata_round_trips():
    data = AppData()
    data.pair_ratings["AB"] = 2.33
    data.pair_rating_versions["AB"] = 2
    data.rating_scale_version = 3
    restored = AppData.from_dict(data.to_dict())
    assert restored.pair_ratings["AB"] == 2.33
    assert restored.pair_rating_versions["AB"] == 2
    assert restored.rating_scale_version == 3
