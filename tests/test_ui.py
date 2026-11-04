from pathlib import Path

from streamlit.testing.v1 import AppTest


def start_app(monkeypatch, tmp_path):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.setenv("AGENT_MODE", "demo")
    monkeypatch.setenv("DATA_DIR", str(root / "fixtures/public"))
    monkeypatch.setenv("POLICY_PDF", str(root / "data/políticas_da_loja.pdf"))
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "store.sqlite3"))
    return AppTest.from_file(str(root / "app.py"), default_timeout=15).run()


def test_chat_ui_and_follow_up(monkeypatch, tmp_path):
    app = start_app(monkeypatch, tmp_path)
    assert not app.exception
    app.chat_input[0].set_value("Quanto custa o Takamine GD20?").run()
    assert not app.exception
    assert "2.199,00" in app.chat_message[-1].markdown[0].value
    app.chat_input[0].set_value("E ele no PIX?").run()
    assert not app.exception
    assert "2.089,05" in app.chat_message[-1].markdown[0].value


def test_identity_change_clears_conversation(monkeypatch, tmp_path):
    app = start_app(monkeypatch, tmp_path)
    app.chat_input[0].set_value("Qual o status do pedido 1?").run()
    assert "confirme" in app.chat_message[-1].markdown[0].value
    app.sidebar.text_input[0].set_value("customer03@example.invalid")
    app.sidebar.text_input[1].set_value("00000000003")
    app.sidebar.button[0].click().run()
    assert not app.exception
    assert len(app.chat_message) == 0
    app.chat_input[0].set_value("Qual o status do pedido 1?").run()
    assert "entregue" in app.chat_message[-1].markdown[0].value
    app.sidebar.button[0].click().run()  # Log out.
    assert not app.exception and len(app.chat_message) == 0
    app.chat_input[0].set_value("Qual o status do pedido 1?").run()
    assert "confirme" in app.chat_message[-1].markdown[0].value
