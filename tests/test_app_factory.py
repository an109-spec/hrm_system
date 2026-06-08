from app import create_app


def test_create_app_registers_expected_blueprints(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "testing")

    app = create_app()

    expected_blueprints = {
        "admin",
        "attendance",
        "auth",
        "contract",
        "history",
        "hr",
        "leave",
        "manager",
        "notification",
        "payroll",
        "personnel",
        "resignation",
    }
    assert expected_blueprints.issubset(set(app.blueprints.keys()))