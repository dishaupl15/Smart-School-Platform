import sys
from unittest.mock import Mock

from app import cli
from app.models.enums import RoleName
from app.models.role import Role, UserRole
from app.models.school import School
from app.models.user import User


def test_bootstrap_admin_creates_school_and_admin_together(
    db_session, monkeypatch, capsys
):
    db_session.add(Role(name=RoleName.ADMIN))
    db_session.commit()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "app.cli",
            "--name",
            "School Administrator",
            "--email",
            "admin@example.test",
            "--school-code",
            "north",
            "--school-name",
            "North School",
        ],
    )
    monkeypatch.setattr(cli, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(
        cli,
        "getpass",
        Mock(side_effect=["a-secure-password", "a-secure-password"]),
    )

    cli.bootstrap_admin_command()

    school = db_session.query(School).one()
    administrator = db_session.query(User).one()
    admin_role = db_session.query(Role).filter_by(name=RoleName.ADMIN).one()
    assert school.school_code == "NORTH"
    assert administrator.school_id == school.id
    assert administrator.password_hash != "a-secure-password"
    assert (
        db_session.query(UserRole)
        .filter_by(user_id=administrator.id, role_id=admin_role.id)
        .one()
    )
    assert f"Created administrator {administrator.id}." in capsys.readouterr().out
