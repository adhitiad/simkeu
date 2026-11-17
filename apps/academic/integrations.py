from __future__ import annotations

import httpx
from django.conf import settings


class SiakadClient:
    def __init__(self) -> None:
        self.base_url = settings.SIAKAD_BASE_URL
        self.api_key = settings.SIAKAD_API_KEY

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=10.0,
        )

    def get_student(self, student_number: str) -> dict[str, object]:
        # Anti-corruption: map external payload to minimal read model here.
        with self._client() as client:
            resp = client.get(f"/students/{student_number}")
            resp.raise_for_status()
            data = resp.json()
        return {
            "student_number": data.get("nim"),
            "study_program": data.get("prodi"),
            "status": data.get("status"),
        }


class SimpegClient:
    def __init__(self) -> None:
        self.base_url = settings.SIMPEG_BASE_URL
        self.api_key = settings.SIMPEG_API_KEY

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=10.0,
        )

    def get_employee(self, employee_id: str) -> dict[str, object]:
        with self._client() as client:
            resp = client.get(f"/employees/{employee_id}")
            resp.raise_for_status()
            data = resp.json()
        return {
            "employee_id": data.get("id"),
            "name": data.get("nama"),
            "unit": data.get("unit"),
        }