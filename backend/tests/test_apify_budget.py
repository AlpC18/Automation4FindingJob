from backend.app.modules.scrape import apify_budget


def test_quota_summary_counts_distinct_valid_accounts_only(monkeypatch):
    monkeypatch.setattr(apify_budget, "_tokens", lambda _source: ["one", "duplicate", "invalid"])

    def fake_status(token, slot):
        if token == "invalid":
            return {"slot": slot, "valid": False, "account_id": None, "used_usd": None, "remaining_usd": None, "budget_usd": 0, "masked": "••••xxxx", "error": "invalid"}
        account_id = "account-1"
        return {"slot": slot, "valid": True, "account_id": account_id, "used_usd": 0.25, "remaining_usd": 4.75, "budget_usd": 5, "masked": "••••xxxx", "error": None}

    monkeypatch.setattr(apify_budget, "_fetch_status", fake_status)
    result = apify_budget.get_apify_quota_summary()

    assert result["configured_keys"] == 3
    assert result["valid_keys"] == 2
    assert result["invalid_keys"] == 1
    assert result["distinct_accounts"] == 1
    assert result["budget_usd"] == 5
    assert result["used_usd"] == 0.25
    assert "account_id" not in str(result)


def test_account_selection_skips_unverified_and_exhausted_tokens(monkeypatch):
    tokens = ["invalid", "spent", "available"]
    monkeypatch.setattr(apify_budget, "_tokens", lambda _source: tokens)

    def fake_status(token, slot):
        values = {
            "invalid": {"valid": False, "account_id": None, "remaining_usd": None},
            "spent": {"valid": True, "account_id": "acct-spent", "remaining_usd": 0},
            "available": {"valid": True, "account_id": "acct-available", "remaining_usd": 0.3},
        }
        return {"slot": slot, **values[token]}

    monkeypatch.setattr(apify_budget, "_fetch_status", fake_status)
    assert apify_budget.select_apify_account("linkedin", 1.0) == ("available", 0.3)


def test_account_selection_uses_first_valid_account_until_its_cap(monkeypatch):
    monkeypatch.setattr(apify_budget, "_tokens", lambda _source: ["first", "second"])
    monkeypatch.setattr(apify_budget, "_fetch_status", lambda token, slot: {
        "slot": slot,
        "valid": True,
        "account_id": f"account-{token}",
        "remaining_usd": 0.75 if token == "first" else 4.5,
    })

    assert apify_budget.select_apify_account("linkedin", 1.0) == ("first", 0.75)
