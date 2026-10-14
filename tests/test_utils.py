import sys

import pytest

from xsense.utils import get_credentials


def test_get_credentials_uses_cli_arguments(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["prog", "--username", "user@example.com", "--password", "secret"],
    )

    assert get_credentials() == ("user@example.com", "secret")


def test_get_credentials_raises_when_env_file_has_no_credentials(
    monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["prog"])
    (tmp_path / ".env").write_text("OTHER=value\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Username and password not provided"):
        get_credentials()
