from __future__ import annotations

import isa_snapshot_store as store


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        return self._payload


def test_publish_refuses_non_isa():
    ok, message = store.publish_snapshot(
        supabase_url="https://example.supabase.co",
        service_role_key="secret",
        metrics={"ticker": "EC"},
    )
    assert not ok
    assert "ISA" in message


def test_publish_requires_complete_valuation():
    ok, message = store.publish_snapshot(
        supabase_url="https://example.supabase.co",
        service_role_key="secret",
        metrics={"ticker": "ISA", "val_ev": 100},
    )
    assert not ok
    assert "EV" in message or "valor por acción" in message


def test_publish_upserts_isa_snapshot(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return FakeResponse(204)

    monkeypatch.setattr(store.requests, "post", fake_post)
    ok, _ = store.publish_snapshot(
        supabase_url="https://example.supabase.co/",
        service_role_key="service-secret",
        metrics={"ticker": "ISA.CL", "empresa": "ISA", "vps_modelo": 123, "val_ev": 456},
        decision_text="Mantener",
        memo="Memo",
        kpis=[{"indicador": "VPS"}],
    )
    assert ok
    assert captured["url"].endswith("/rest/v1/isa_valuation_snapshots?on_conflict=ticker")
    assert captured["kwargs"]["json"]["ticker"] == "ISA"
    assert captured["kwargs"]["json"]["payload"]["metrics"]["vps_modelo"] == 123
    assert captured["kwargs"]["headers"]["Authorization"] == "Bearer service-secret"


def test_fetch_snapshot_uses_rpc_and_token(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return FakeResponse(200, {"ticker": "ISA", "payload": {"metrics": {"vps_modelo": 123}}})

    monkeypatch.setattr(store.requests, "post", fake_post)
    result = store.fetch_latest_snapshot(
        supabase_url="https://example.supabase.co",
        anon_key="public-key",
        presentation_token="private-token",
    )
    assert result["ticker"] == "ISA"
    assert captured["url"].endswith("/rest/v1/rpc/get_isa_latest_snapshot")
    assert captured["kwargs"]["json"] == {"p_token": "private-token"}
    assert captured["kwargs"]["headers"]["apikey"] == "public-key"
