import pytest
from django.test import Client


def test_home_renders() -> None:
    resp = Client().get("/")
    assert resp.status_code == 200
    assert b"SIMKEU" in resp.content


@pytest.mark.django_db
def test_healthz_ok() -> None:
    resp = Client().get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.django_db
def test_readyz_ok() -> None:
    resp = Client().get("/readyz")
    assert resp.status_code == 200
    assert resp.json()["checks"]["db"] == "ok"
