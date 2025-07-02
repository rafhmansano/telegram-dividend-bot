from __future__ import annotations

import os
import datetime as dt
import time
from typing import Dict, Tuple, Optional

import requests
from flask import Flask, Response

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
if not TELEGRAM_TOKEN or not CHAT_ID:
    raise RuntimeError("Defina TELEGRAM_TOKEN e CHAT_ID em Secrets!")

import sys

if __name__ == "__main__":
    if "web" in sys.argv:
        from flask import Flask
        app = Flask(__name__)

        @app.route("/")
        def run_job():
            check_assets()
            return "OK", 200

        app.run(host="0.0.0.0", port=81)
  

import os
import datetime as dt
import time
from typing import Dict, Tuple, Optional

import requests
from flask import Flask, Response

# ---------------------- Configuração dos ativos ---------------------- #
ASSETS: Dict[str, Tuple[float, float]] = {
    # ticker: (fair_value, margem_de_seguranca)
    "BBAS3": (20.60, 0.20),
    "BRSR6": (8.00, 0.20),
    "BRAP4": (19.00, 0.20),
    "ITSA4": (10.60, 0.20),
    "BBSE3": (47.06, 0.20),
    "CSMG3": (22.50, 0.20),
    "SAPR11": (23.30, 0.15),
    "LEVE3": (33.50, 0.20),
    "CMIG4": (10.26, 0.20),
    "CPLE6": (7.10, 0.20),
    "TAEE11": (26.50, 0.15),
    "ISAE4": (30.6, 0.20),
    "VIVT3": (18.40, 0.20),
    # "TFLO": (50.53, 0.10),  # ETF USD — removido se usar somente B3
    "ALZR11": (12.00, 0.15),
    "HGLG11": (186.00, 0.15),
    "IRDM11": (91.50, 0.15),
    "HGCR11": (118.00, 0.15),
    "KNCR11": (133.00, 0.15),
    "XPML11": (145.0, 0.15),
}

# ------------------------ Chaves de ambiente ------------------------ #
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
if not TELEGRAM_TOKEN or not CHAT_ID:
    raise RuntimeError("Defina TELEGRAM_TOKEN e CHAT_ID em Secrets!")
API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

# -------------------------- Fetch de preços ------------------------- #

def get_price_brapi(ticker: str) -> Optional[float]:
    """Primeira tentativa: brapi.dev (rápido, dados B3)."""
    try:
        resp = requests.get(f"https://brapi.dev/api/quote/{ticker}", timeout=8)
        if resp.status_code == 200:
            js = resp.json()
            res = js.get("results", [])
            if res and res[0].get("regularMarketPrice"):
                return float(res[0]["regularMarketPrice"])
    except Exception as exc:
        print(f"brapi erro {ticker}: {exc}")
    return None


def get_price_yahoo(ticker: str) -> Optional[float]:
    """Fallback: query1.finance.yahoo.com (exige .SA)."""
    tk = f"{ticker}.SA" if not ticker.endswith(".SA") else ticker
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{tk}"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            result = data.get("chart", {}).get("result")
            if result:
                return float(result[0]["meta"]["regularMarketPrice"])
    except Exception as exc:
        print(f"Yahoo erro {ticker}: {exc}")
    return None


def get_price(ticker: str) -> float:
    price = get_price_brapi(ticker) or get_price_yahoo(ticker)
    if price is None:
        raise ValueError(f"Preço indisponível para {ticker}")
    return price

# --------------------------- Telegram -------------------------------- #

def send_alert(text: str) -> None:
    try:
        resp = requests.post(API_URL, data={"chat_id": CHAT_ID, "text": text})
        if resp.status_code != 200:
            print(f"Telegram erro HTTP {resp.status_code}: {resp.text}")
    except Exception as exc:
        print(f"Telegram exceção: {exc}")

# --------------------------- Core logic ------------------------------ #

def check_assets() -> str:
    dt_now = dt.datetime.now().strftime("%d/%m/%Y %H:%M")
    triggered: list[str] = []
    for tk, (fv, mos) in ASSETS.items():
    try:
        price = get_price(tk)
        trigger = fv * (1 - mos)

        gap_pct = (trigger - price) / trigger * 100      # novo
        print(f"{tk}: R$ {price:.2f} | gatilho R$ {trigger:.2f} "
              f"| gap {gap_pct:+.1f}%")                  # opcional

        if price <= trigger:
            msg = (
                f"🛎️ {dt_now} — ALERTA DE COMPRA\n"
                f"{tk} cotado a R$ {price:.2f} "
                f"(gatilho R$ {trigger:.2f}, "
                f"gap {gap_pct:.1f}%, MOS {mos*100:.0f}%)"
            )
            send_alert(msg)
            triggered.append(tk)

    except Exception as exc:
        print(f"Erro {tk}: {exc}")

        time.sleep(0.4)  # Polidez com as APIs
    return ", ".join(triggered) if triggered else "Sem alertas"

# --------------------------- Flask app ------------------------------- #
app = Flask(__name__)

@app.route("/", methods=["GET"])
def index() -> Response:
    result = check_assets()
    return Response(f"OK – {result}\n", status=200, mimetype="text/plain")

# ---------------------------- CLI run -------------------------------- #
if __name__ == "__main__":
    # Roda uma checagem única se chamar: python telegram_alert_bot.py
    print("Execução stand‑alone…")
    print(check_assets())
