"""crear_base.py nunca detiene el arranque."""

import crear_base


def test_no_hace_nada_sin_postgresql(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///db.sqlite3")
    assert crear_base.main() == 0

    monkeypatch.setenv("DATABASE_URL", "")
    assert crear_base.main() == 0


def test_si_postgresql_no_responde_avisa_y_sigue(monkeypatch, capsys):
    # Puerto 1: nadie escucha, la conexión falla enseguida.
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg2://u:c@127.0.0.1:1/db_progreso?connect_timeout=2"
    )

    assert crear_base.main() == 0
    assert "AVISO: no se pudo crear la base db_progreso" in capsys.readouterr().err
