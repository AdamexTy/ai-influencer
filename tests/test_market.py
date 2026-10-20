import market


def test_collect_survives_source_failure(monkeypatch):
    monkeypatch.setattr(market, "youtube_trending", lambda: [{"title": "x"}])
    monkeypatch.setattr(market, "hacker_news", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(market, "wikipedia_top", lambda: ["A", "B"])

    data = market.collect()

    assert data["youtube_trending"]
    assert data["hacker_news"] == []
    assert data["wikipedia_top"] == ["A", "B"]
    assert data["_meta"]["hacker_news"]["ok"] is False
