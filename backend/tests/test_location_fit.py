"""A posting limited to places the candidate is not in is flagged; open and matching ones are not."""

import pytest

from backend.app.modules.rank.red_flag_detector import detect_red_flags, location_excludes

KOSOVO = {"location": "Prishtina, Kosovo", "years_of_experience": 1}


@pytest.mark.parametrize("posting_location", [
    "", "Unspecified", "Remote", "Worldwide", "Anywhere", "Europe, USA, UK, Canada", "EMEA",
    "Northern America, LATAM, Europe, APAC", "Prishtina", "Kosovo", "Remote (Europe)",
])
def test_open_or_matching_locations_are_not_flagged(posting_location):
    assert location_excludes(posting_location, KOSOVO["location"]) is False


@pytest.mark.parametrize("posting_location", ["United States", "USA", "India", "London, UK or Zurich", "LATAM", "Paris", "Remote, USA", "Remote (US only)"])
def test_locations_that_leave_the_candidate_out_are_flagged(posting_location):
    assert location_excludes(posting_location, KOSOVO["location"]) is True


def test_extra_places_the_candidate_can_work_in_count_including_their_cities():
    assert location_excludes("Munich, Bavaria, Germany", KOSOVO["location"], ["Germany"]) is False
    assert location_excludes("Berlin", KOSOVO["location"], ["Germany"]) is False
    assert location_excludes("Berlin", KOSOVO["location"]) is True


def test_nothing_is_flagged_when_the_profile_has_no_location():
    assert location_excludes("United States", "") is False
    assert not any("Konum" in flag for flag in detect_red_flags({"location": "USA"}, {}))


def test_the_flag_names_the_posting_location_and_a_restriction_in_the_text_counts():
    by_field = detect_red_flags({"title": "Dev", "location": "United States", "remote_type": "Remote"}, KOSOVO)
    by_text = detect_red_flags(
        {"title": "Remote Dev", "location": "Worldwide", "remote_type": "Remote", "description": "You must be based in Thailand."}, KOSOVO,
    )
    open_text = detect_red_flags(
        {"title": "Remote Dev", "location": "Remote", "remote_type": "Remote", "description": "You must be located in Europe."}, KOSOVO,
    )

    assert len(by_field) == 1 and "United States" in by_field[0]
    assert len(by_text) == 1 and "thailand" in by_text[0].lower()
    assert open_text == []
