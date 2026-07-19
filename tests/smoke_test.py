from __future__ import annotations

import os
import re


def csrf(html: str) -> str:
    m = re.search(r'name="_csrf" value="([^"]+)"', html)
    assert m, "No CSRF token found in:\n" + html[:600]
    return m.group(1)


def test_register_add_medication_and_view_review_packet(tmp_path):
    """Full registration, medication creation, and Medicare review packet flow."""
    os.environ["NORTHSTAR_DB_PATH"] = str(tmp_path / "test.sqlite3")
    os.environ["NORTHSTAR_UPLOAD_DIR"] = str(tmp_path / "uploads")

    from app.main import app
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        # Landing page has both sign-in and create-profile forms with CSRF
        r = client.get("/")
        assert r.status_code == 200
        token = csrf(r.text)

        # Register via the /register POST endpoint
        r = client.post(
            "/register",
            data={
                "_csrf": token,
                "full_name": "Mary Test",
                "date_of_birth": "1950-01-01",
                "phone": "555-111-2222",
                "email": "mary-test@example.com",
                "password": "longpassword1",
            },
            follow_redirects=False,
        )
        assert r.status_code == 303

        # Add a medication
        r = client.get("/records/medications/new")
        assert r.status_code == 200
        token = csrf(r.text)
        r = client.post(
            "/records/medications/new",
            data={"_csrf": token, "medication_name": "Metformin", "dosage": "500 mg", "frequency": "Twice daily"},
            follow_redirects=False,
        )
        assert r.status_code == 303

        # Verify it shows up
        r = client.get("/records/medications")
        assert r.status_code == 200
        assert "Metformin" in r.text

        # Medicare review page loads
        r = client.get("/medicare-review")
        assert r.status_code == 200
        assert "Medicare" in r.text
