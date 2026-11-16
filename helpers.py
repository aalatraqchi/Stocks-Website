import math
import os
import time
from functools import wraps

import requests
from flask import redirect, render_template, session

FINNHUB_URL = "https://finnhub.io/api/v1"

# Company names rarely change, so cache them to save API calls.
_name_cache = {}

# Simulated market used when no FINNHUB_API_KEY is configured.
DEMO_STOCKS = {
    "AAPL": ("Apple Inc", 228.50),
    "AMD": ("Advanced Micro Devices Inc", 152.30),
    "AMZN": ("Amazon.com Inc", 201.75),
    "DIS": ("Walt Disney Co", 112.40),
    "GOOGL": ("Alphabet Inc", 176.20),
    "INTC": ("Intel Corp", 23.10),
    "JPM": ("JPMorgan Chase & Co", 241.60),
    "KO": ("Coca-Cola Co", 68.90),
    "META": ("Meta Platforms Inc", 585.10),
    "MSFT": ("Microsoft Corp", 418.30),
    "NFLX": ("Netflix Inc", 842.00),
    "NKE": ("Nike Inc", 76.40),
    "NVDA": ("NVIDIA Corp", 141.80),
    "TSLA": ("Tesla Inc", 321.20),
    "V": ("Visa Inc", 309.50),
}


def apology(message, code=400):
    """Render an error page with an HTTP status code."""
    return render_template("apology.html", code=code, message=message), code


def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/latest/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def demo_mode():
    """True when no market data API key is configured."""
    return not os.environ.get("FINNHUB_API_KEY")


def lookup(symbol):
    """Look up a quote for symbol.

    Returns a dict with name, price, and symbol, or None if the symbol is
    invalid or the quote service can't be reached.
    """
    if not symbol or not symbol.strip():
        return None
    symbol = symbol.strip().upper()

    if demo_mode():
        return _demo_lookup(symbol)
    return _finnhub_lookup(symbol, os.environ["FINNHUB_API_KEY"])


def _demo_lookup(symbol):
    """Return a simulated quote that drifts slowly over time."""
    if symbol not in DEMO_STOCKS:
        return None
    name, base_price = DEMO_STOCKS[symbol]
    phase = sum(ord(c) for c in symbol)
    drift = 0.03 * math.sin(time.time() / 900 + phase)
    return {"name": name, "price": round(base_price * (1 + drift), 2), "symbol": symbol}


def _finnhub_lookup(symbol, api_key):
    """Fetch a live quote from Finnhub (https://finnhub.io/docs/api)."""
    headers = {"X-Finnhub-Token": api_key}
    try:
        response = requests.get(f"{FINNHUB_URL}/quote", params={"symbol": symbol},
                                headers=headers, timeout=10)
        response.raise_for_status()
        price = float(response.json()["c"])
    except (requests.RequestException, KeyError, TypeError, ValueError):
        return None

    # Finnhub answers unknown symbols with a price of 0
    if price <= 0:
        return None

    return {"name": _company_name(symbol, headers), "price": price, "symbol": symbol}


def _company_name(symbol, headers):
    """Fetch a company's name, falling back to the symbol itself."""
    if symbol not in _name_cache:
        try:
            response = requests.get(f"{FINNHUB_URL}/stock/profile2", params={"symbol": symbol},
                                    headers=headers, timeout=10)
            response.raise_for_status()
            name = response.json().get("name")
        except (requests.RequestException, ValueError, AttributeError):
            return symbol
        _name_cache[symbol] = name or symbol
    return _name_cache[symbol]


def usd(value):
    """Format value as USD."""
    return f"${value:,.2f}"
