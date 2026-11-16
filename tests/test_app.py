from app import db
from conftest import login, register


def cash(username="alice"):
    return db.execute("SELECT cash FROM users WHERE username = ?", username)[0]["cash"]


def test_pages_require_login(client):
    for path in ["/", "/buy", "/sell", "/quote", "/history", "/change_password"]:
        response = client.get(path)
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")


def test_register_and_login(client):
    response = register(client)
    assert response.status_code == 302
    response = login(client)
    assert response.status_code == 302
    page = client.get("/").get_data(as_text=True)
    assert "$10,000.00" in page


def test_register_rejects_duplicate_and_mismatch(client):
    register(client)
    assert register(client).status_code == 400
    response = client.post("/register", data={
        "username": "bob", "password": "a", "confirmation": "b"})
    assert response.status_code == 400


def test_login_rejects_wrong_password(client):
    register(client)
    assert login(client, password="nope").status_code == 403


def test_quote(user):
    page = user.post("/quote", data={"symbol": "aapl"}).get_data(as_text=True)
    assert "Apple Inc (AAPL)" in page
    assert user.post("/quote", data={"symbol": "NOTREAL"}).status_code == 400
    assert user.post("/quote", data={"symbol": ""}).status_code == 400


def test_buy_updates_cash_and_portfolio(user):
    response = user.post("/buy", data={"symbol": "MSFT", "shares": "3"})
    assert response.status_code == 302
    assert cash() < 10000
    page = user.get("/").get_data(as_text=True)
    assert "MSFT" in page and "Microsoft Corp" in page


def test_buy_validation(user):
    assert user.post("/buy", data={"symbol": "MSFT", "shares": "0"}).status_code == 400
    assert user.post("/buy", data={"symbol": "MSFT", "shares": "-2"}).status_code == 400
    assert user.post("/buy", data={"symbol": "MSFT", "shares": "1.5"}).status_code == 400
    assert user.post("/buy", data={"symbol": "NOTREAL", "shares": "1"}).status_code == 400
    assert user.post("/buy", data={"symbol": "NFLX", "shares": "1000"}).status_code == 403
    assert cash() == 10000


def test_sell_uses_total_shares_across_purchases(user):
    user.post("/buy", data={"symbol": "KO", "shares": "2"})
    user.post("/buy", data={"symbol": "KO", "shares": "3"})
    # 5 shares owned across two purchases, so selling 4 must work
    assert user.post("/sell", data={"symbol": "KO", "shares": "4"}).status_code == 302
    assert user.post("/sell", data={"symbol": "KO", "shares": "2"}).status_code == 400
    assert user.post("/sell", data={"symbol": "KO", "shares": "1"}).status_code == 302
    # Fully sold positions disappear from the sell menu
    assert 'value="KO"' not in user.get("/sell").get_data(as_text=True)


def test_sell_validation(user):
    user.post("/buy", data={"symbol": "KO", "shares": "1"})
    assert user.post("/sell", data={"symbol": "AAPL", "shares": "1"}).status_code == 400
    assert user.post("/sell", data={"symbol": "KO", "shares": "abc"}).status_code == 400
    assert user.post("/sell", data={"symbol": "KO"}).status_code == 400
    assert user.post("/sell", data={"shares": "1"}).status_code == 400


def test_history_lists_buys_and_sells(user):
    user.post("/buy", data={"symbol": "V", "shares": "2"})
    user.post("/sell", data={"symbol": "V", "shares": "1"})
    page = user.get("/history").get_data(as_text=True)
    assert "bg-success" in page and "bg-danger" in page


def test_change_password(user):
    response = user.post("/change_password", data={
        "username": "alice", "password": "secret123", "new_pass": "newpass1", "confirmation": "newpass1"})
    assert response.status_code == 302
    assert login(user, password="secret123").status_code == 403
    assert login(user, password="newpass1").status_code == 302


def test_change_password_only_for_logged_in_user(client):
    register(client, "bob", "bobpass")
    register(client)
    login(client)
    # Knowing another user's password must not let you change it from your account
    response = client.post("/change_password", data={
        "username": "bob", "password": "bobpass", "new_pass": "changed", "confirmation": "changed"})
    assert response.status_code == 403
    assert login(client, "bob", "bobpass").status_code == 302
