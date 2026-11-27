import pytest


@pytest.fixture(autouse=True)
def indicador_proxy_pruebas(tmp_path, monkeypatch):
    from app.seguridad.proxy import servidor

    indicador = tmp_path / "proxy-habilitado.flag"

    indicador.write_text(
        "habilitado",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        servidor,
        "INDICADOR_PROXY",
        indicador,
    )

    return indicador
