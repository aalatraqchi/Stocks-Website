import os
import secrets
from datetime import datetime
from pathlib import Path

from cachelib.file import FileSystemCache
from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from db import Database
from helpers import apology, demo_mode, login_required, lookup, usd

BASE_DIR = Path(__file__).resolve().parent

# Load settings from a local .env file, if there is one
load_dotenv(BASE_DIR / ".env")

# Configure application
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use the filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "cachelib"
app.config["SESSION_CACHELIB"] = FileSystemCache(
    cache_dir=os.environ.get("SESSION_DIR", str(BASE_DIR / "flask_session")), threshold=500)
Session(app)

# Configure SQLite database and create tables on first run
db = Database(os.environ.get("DATABASE_PATH", BASE_DIR / "finance.db"))
db.init_schema(BASE_DIR / "schema.sql")


def parse_shares(value):
    """Return value as a positive whole number of shares, or None."""
    if value is None or not value.strip().isdigit():
        return None
    shares = int(value)
    return shares if shares > 0 else None


def holdings(user_id):
    """Return {symbol: shares} for every stock the user currently owns."""
    rows = db.execute("SELECT symbol, SUM(shares) AS shares FROM transactions WHERE user_id = ? "
                      "GROUP BY symbol HAVING SUM(shares) > 0 ORDER BY symbol", user_id)
    return {row["symbol"]: row["shares"] for row in rows}


def record_transaction(user, stock, shares):
    """Log a buy (positive shares) or sell (negative shares)."""
    db.execute("INSERT INTO transactions (user_id, user, name, symbol, shares, price, datetime) "
               "VALUES (?, ?, ?, ?, ?, ?, ?)",
               user["id"], user["username"], stock["name"], stock["symbol"], shares, stock["price"],
               datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


@app.context_processor
def inject_market_mode():
    """Let every template know whether prices are live or simulated."""
    return {"demo_mode": demo_mode()}


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"]
    total = cash
    stocks = {}

    # Get current values of owned stocks
    for symbol, shares in holdings(session["user_id"]).items():
        stock = lookup(symbol)
        if not stock:
            stocks[symbol] = ("Quote unavailable", shares, "N/A", "N/A")
            continue
        total_price = shares * stock["price"]
        total += total_price
        stocks[symbol] = (stock["name"], shares, usd(stock["price"]), usd(total_price))

    return render_template("index.html", stocks=stocks, cash=usd(cash), total=usd(total))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol", "").strip()
        shares = parse_shares(request.form.get("shares"))

        if not symbol:
            return apology("must provide stock symbol", 400)

        stock = lookup(symbol)
        if not stock:
            return apology("must provide valid stock symbol", 400)
        elif not shares:
            return apology("must provide valid number of shares", 400)

        user = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])[0]
        updated_cash = user["cash"] - shares * stock["price"]

        if updated_cash < 0:
            return apology("insufficient funds", 403)

        # Update cash and transactions
        db.execute("UPDATE users SET cash = ? WHERE id = ?", updated_cash, session["user_id"])
        record_transaction(user, stock, shares)

        flash(f"Bought {shares} share{'s' if shares != 1 else ''} of {stock['symbol']}!")
        return redirect("/")
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    history = db.execute("SELECT * FROM transactions WHERE user_id = ? ORDER BY datetime DESC, rowid DESC",
                         session["user_id"])
    return render_template("history.html", history=history)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id, but keep messages flashed before redirecting here
    flashes = session.get("_flashes")
    session.clear()
    if flashes:
        session["_flashes"] = flashes

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        symbol = request.form.get("symbol", "").strip()

        if not symbol:
            return apology("must provide stock symbol", 400)

        stock = lookup(symbol)
        if not stock:
            return apology("must provide valid stock symbol", 400)
        else:
            return render_template("quoted.html", name=stock["name"], price=usd(stock["price"]), symbol=stock["symbol"])
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        username = request.form.get("username", "").strip()

        # Ensure username was submitted
        if not username:
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", username)

        # Ensure username doesn't already exist, and passwords match
        if len(rows) != 0:
            return apology("username already exists!", 400)
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords do not match!", 400)

        # Register user
        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)",
                   username, generate_password_hash(request.form.get("password")))

        # Redirect user to login page
        flash("Registered! Log in to start trading.")
        return redirect("/login")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    owned = holdings(session["user_id"])

    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = parse_shares(request.form.get("shares"))

        if not symbol:
            return apology("must pick stock symbol", 400)
        elif symbol not in owned:
            return apology("you do not own any shares of " + symbol, 400)
        elif not shares:
            return apology("must provide valid number of shares", 400)
        elif shares > owned[symbol]:
            return apology("you do not own that many shares of " + symbol, 400)

        stock = lookup(symbol)
        if not stock:
            return apology("quote unavailable, try again later", 503)

        user = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])[0]
        updated_cash = user["cash"] + shares * stock["price"]

        # Update cash and transactions
        db.execute("UPDATE users SET cash = ? WHERE id = ?", updated_cash, session["user_id"])
        record_transaction(user, stock, -shares)

        flash(f"Sold {shares} share{'s' if shares != 1 else ''} of {stock['symbol']}!")
        return redirect("/")
    else:
        return render_template("sell.html", owned=owned)


@app.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    """Allow logged in user to change their password"""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        if not request.form.get("username"):
            return apology("must provide username", 403)
        elif not request.form.get("password"):
            return apology("must provide current password", 403)
        elif not request.form.get("new_pass"):
            return apology("must provide new password", 403)

        # Look up the logged-in user
        rows = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])

        # Ensure user correctly implements new password
        if len(rows) != 1 or rows[0]["username"] != request.form.get("username"):
            return apology("invalid username", 403)
        elif not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("incorrect current password", 403)
        elif request.form.get("password") == request.form.get("new_pass"):
            return apology("new password must be different from old password", 403)
        elif request.form.get("new_pass") != request.form.get("confirmation"):
            return apology("passwords do not match", 403)

        # Change user password
        db.execute("UPDATE users SET hash = ? WHERE id = ?", generate_password_hash(
            request.form.get("new_pass")), session["user_id"])

        # Redirect user to login page
        flash("Password changed. Please log in again.")
        return redirect("/login")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("change_password.html")


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
