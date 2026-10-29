import io
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_curvas_dados_platea():
    res = client.get("/api/replan/platea/curvas-dados")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert "kpis" in data
    assert "seriesMensal" in data
    assert "etapas" in data
    assert "s_curves_comparison" in data
    assert "niveis1" in data

def test_curvas_realizado_platea():
    res = client.get("/api/replan/platea/curvas-realizado")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert "kpis" in data
    assert "seriesMensal" in data
    assert "etapas" in data

def test_curvas_templates_downloads():
    # Custo projetado template
    r1 = client.get("/api/replan/platea/curvas-templates/custo-projetado")
    assert r1.status_code == 200
    assert len(r1.content) > 1000

    # Incorrido template
    r2 = client.get("/api/replan/platea/curvas-templates/incorrido")
    assert r2.status_code == 200
    assert len(r2.content) > 1000

    # Conciliacao template
    r3 = client.get("/api/replan/platea/curvas-templates/conciliacao")
    assert r3.status_code == 200
    assert len(r3.content) > 1000

def test_curvas_vinculos_and_versoes():
    # Vínculo manual
    v_res = client.post("/api/replan/platea/curvas-vinculos", json={
        "codigo_origem": "99.99.999",
        "codigo_destino": "01.01.001",
        "remover": False
    })
    assert v_res.status_code == 200
    assert v_res.json()["vinculos"].get("99.99.999") == "01.01.001"

    # Remove vínculo
    v_del = client.post("/api/replan/platea/curvas-vinculos", json={
        "codigo_origem": "99.99.999",
        "remover": True
    })
    assert v_del.status_code == 200
    assert "99.99.999" not in v_del.json()["vinculos"]

    # Salva versão
    ver_res = client.post("/api/replan/platea/curvas-versoes", json={"nome": "Teste Snapshot"})
    assert ver_res.status_code == 200
    ver_id = ver_res.json()["versao"]["id"]

    # Lista versões
    list_res = client.get("/api/replan/platea/curvas-versoes")
    assert list_res.status_code == 200
    assert any(v["id"] == ver_id for v in list_res.json()["versoes"])

    # Deleta versão
    del_res = client.delete(f"/api/replan/platea/curvas-versoes/{ver_id}")
    assert del_res.status_code == 200

    # Cleanup test files from disk
    import os
    for fname in ["vinculos.json", "versoes.json"]:
        fpath = os.path.join("backend", "data", "projects", "platea", fname)
        if os.path.exists(fpath):
            try:
                os.remove(fpath)
            except OSError:
                pass
