def test_moderation_summary_review(client):
    res = client.post("/message", json={"message": "Test claim about vaccines"})
    assert res.status_code == 200
    data = res.json()

    assert "moderation_summary" in data
    summary = data["moderation_summary"]
    assert summary["recommendation"] == "review"
    assert summary["risk"] >= 0.6

    flags = summary.get("flags") or []
    assert "likely_misinformation" in flags
