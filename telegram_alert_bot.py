from __future__ import annotations
import os
import datetime as dt
import time
import requests
from typing import Dict, Tuple, Optional

# ------------------------ Config ------------------------ #
ASSETS: Dict[str, Tuple[float, float]] = {
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
    "ALZR11": (12.00, 0.15),
    "HGLG11": (186.00, 0.15),
    "IRDM11": (91.50, 0.15),
    "HGCR11": (118.00, 0.15),
    "KNCR11": (133.00, 0.15),
    "XPML11": (145.0, 0.15),
}

# ------------------------ Environment ------------------------ #
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

if not TELEGRAM_TOKEN or not CHAT_ID:
    raise RuntimeError("TELEGRAM_TOKEN e CHAT_ID devem estar definidos nos secrets!")

# ------------------------ Utils ------------------------ #
def log(msg: str) -> None:
    ts = from pytz import timezone
brt = timezone("America/Sao_Paulo")
dt_now = dt.datetime.now(brt).strftime("%d/%m/%Y %H:%M")
    print(f"[{ts}] {msg}")

def send_alert(text: str) -> None:
    try:
        resp = requests.post(API_URL, data={"chat_id": CHAT_ID, "text": text})
        if resp.status_code != 200:
            log(f"Erro Telegram ({resp.status_code}): {resp.text}")
    except Exception as exc:
        log(f"Exceção Telegram: {exc}")

# ------------------------ Preços ------------------------ #
def get_price_brapi(ticker: str) -> Optional[float]:
    try:
        resp = requests.get(f"https://brapi.dev/api/quote/{ticker}", timeout=8)
        if resp.status_code == 200:
            js = resp.json()
            res = js.get("results", [])
            if res and res[0].get("regularMarketPrice"):
                return float(res[0]["regularMarketPrice"])
    except Exception as exc:
        log(f"Brapi erro {ticker}: {exc}")
    return None

def get_price_yahoo(ticker: str) -> Optional[float]:
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
        log(f"Yahoo erro {ticker}: {exc}")
    return None

def get_price(ticker: str) -> float:
    price = get_price_brapi(ticker) or get_price_yahoo(ticker)
    if price is None:
        raise ValueError(f"Preço indisponível para {ticker}")
    return price

# ------------------------ Lógica principal ------------------------ #
def check_assets() -> str:
    dt_now = dt.datetime.now().strftime("%d/%m/%Y %H:%M")
    triggered: list[str] = []
    log("Iniciando checagem de ativos...")

    for tk, (fv, mos) in ASSETS.items():
        try:
            price = get_price(tk)
            trigger = fv * (1 - mos)
            gap_pct = (trigger - price) / trigger * 100

            log(f"{tk}: R$ {price:.2f} | Gatilho R$ {trigger:.2f} | Gap {gap_pct:+.1f}%")

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
            err_msg = f"Erro ao verificar {tk}: {exc}"
            log(err_msg)
            send_alert(f"⚠️ {err_msg}")
            time.sleep(0.5)  # Evita bombardeio de requisições

    summary = ", ".join(triggered) if triggered else "Sem alertas de compra."
    log(f"Checagem concluída. Resultado: {summary}")
    return summary

# ------------------------ Execução direta ------------------------ #
if __name__ == "__main__":
    log("Início do script (execução stand-alone).")
    try:
        check_assets()
    except Exception as exc:
        msg = f"Erro inesperado durante execução: {exc}"
        log(msg)
        send_alert(f"❌ {msg}")
