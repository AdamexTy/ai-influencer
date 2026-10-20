import feedback


class _Execute:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


class _Videos:
    def list(self, **kwargs):
        return _Execute({"items": [{"id": "abc", "statistics": {"viewCount": "10", "likeCount": "2", "commentCount": "1"}}]})


class _Channels:
    def list(self, **kwargs):
        return _Execute({"items": [{"statistics": {"subscriberCount": "5", "viewCount": "100"}}]})


class _YT:
    def videos(self):
        return _Videos()

    def channels(self):
        return _Channels()


def test_update_metrics_falls_back_when_analytics_unavailable(monkeypatch):
    mem = {"channel": {}, "videos": [{"id": "abc", "title": "x"}]}
    monkeypatch.setattr(feedback, "get_service", lambda: _YT())

    def _boom():
        raise RuntimeError("missing scope")

    monkeypatch.setattr(feedback, "_analytics_service", _boom)

    feedback.update_metrics(mem)

    video = mem["videos"][0]
    assert video["views"] == 10
    assert video["likes"] == 2
    assert video["comments"] == 1
    assert video["metrics_history"]
    assert mem["channel"]["analytics_enabled"] is False
