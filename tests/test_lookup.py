import requests

import helpers


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status

    def raise_for_status(self):
        if self.status >= 400:
            raise requests.HTTPError(self.status)

    def json(self):
        return self.payload


def fake_finnhub(quote, profile, calls=None):
    def get(url, params=None, headers=None, timeout=None):
        if calls is not None:
            calls.append((url, headers))
        return FakeResponse(quote if url.endswith("/quote") else profile)
    return get


def test_demo_mode_without_key(monkeypatch):
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    assert helpers.demo_mode()
    stock = helpers.lookup("aapl")
    assert stock["symbol"] == "AAPL" and stock["price"] > 0
    assert helpers.lookup("NOTREAL") is None
    assert helpers.lookup("") is None


def test_finnhub_lookup(monkeypatch):
    calls = []
    monkeypatch.setenv("FINNHUB_API_KEY", "test-key")
    monkeypatch.setattr(helpers, "_name_cache", {})
    monkeypatch.setattr(helpers.requests, "get",
                        fake_finnhub({"c": 123.45}, {"name": "Example Corp"}, calls))
    assert helpers.lookup("exmp") == {"name": "Example Corp", "price": 123.45, "symbol": "EXMP"}
    # The key is sent in a header, never in the URL
    assert calls and all(headers == {"X-Finnhub-Token": "test-key"} for _, headers in calls)
    assert all("test-key" not in url for url, _ in calls)


def test_finnhub_unknown_symbol(monkeypatch):
    monkeypatch.setenv("FINNHUB_API_KEY", "test-key")
    monkeypatch.setattr(helpers.requests, "get", fake_finnhub({"c": 0, "t": 0}, {}))
    assert helpers.lookup("ZZZZ") is None


def test_finnhub_error(monkeypatch):
    monkeypatch.setenv("FINNHUB_API_KEY", "test-key")

    def boom(*args, **kwargs):
        raise requests.ConnectionError("offline")
    monkeypatch.setattr(helpers.requests, "get", boom)
    assert helpers.lookup("AAPL") is None
