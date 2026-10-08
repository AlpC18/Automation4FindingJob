from backend.app.api.profile import (
    fetch_candidate_profile,
    list_candidate_profiles,
    create_candidate_profile,
    activate_candidate_profile,
)


def test_fetch_candidate_profile_returns_dict():
    """Verify that fetch_candidate_profile returns a non-empty dictionary."""
    profile = fetch_candidate_profile()
    assert isinstance(profile, dict)
    assert "name" in profile
    assert "target_roles" in profile
    assert "skills" in profile


def test_list_candidate_profiles():
    """Verify listing multi-candidate profiles."""
    profiles = list_candidate_profiles()
    if not profiles:
        create_candidate_profile(name="Default Profile", target_role="Developer")
        profiles = list_candidate_profiles()
    assert isinstance(profiles, list)
    assert len(profiles) >= 1
    first = profiles[0]
    assert "id" in first
    assert "name" in first
    assert "is_active" in first


def test_create_and_activate_profile():
    """Test creating a new candidate profile and activating it."""
    import uuid
    unique_name = f"Test Profile {uuid.uuid4().hex[:6]}"
    
    new_profile = create_candidate_profile(
        name=unique_name,
        target_role="Software Engineer",
        full_name="Test Candidate",
        initial_data={
            "email": "test@example.com",
            "location": "Pristina, Kosovo",
        }
    )
    assert new_profile["name"] == unique_name
    assert new_profile["id"].startswith("prof-")

    # Activate it
    activated = activate_candidate_profile(new_profile["id"])
    assert activated["id"] == new_profile["id"]
    assert activated["is_active"] is True or activated["is_active"] == 1
