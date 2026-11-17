from django.db import connection
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render


def home(request: HttpRequest) -> HttpResponse:
    return render(request, "core/home.html")


def healthz(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok"})


def readyz(request: HttpRequest) -> JsonResponse:
    checks: dict[str, str] = {}
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        checks["db"] = "ok"
    except Exception:
        checks["db"] = "unavailable"
    status = 200 if all(v == "ok" for v in checks.values()) else 503
    payload = {"status": "ok" if status == 200 else "unavailable", "checks": checks}
    return JsonResponse(payload, status=status)