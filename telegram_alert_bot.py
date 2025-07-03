from __future__ import annotations
import os
import datetime as dt
import time
import requests
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from typing import Dict, Tuple, Optional
from zoneinfo import ZoneInfo

brt = ZoneInfo("America/Sao_Paulo")

# ------------------------ Planilha ------------------------ #
import json
    cred_dict = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
    creds = Credentials.from_service_account_info(cred_dict, scopes=SCOPE)
    gc = gspread.authorize(creds)
    sheet = gc.open(SPREADSHEET_NAME).worksheet(SHEET_NAME)
    data = sheet.get_all_records()
    ativos = {
        row["Ticker"].strip(): (float(row["FairValue"]), float(row["MOS"]))
        for row in data
    }
    return ativos

# ------------------------ Environment ------------------------ #
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

if not TELEGRAM_TOKEN or not CHAT_ID:
    raise RuntimeError("TELEGRAM_TOKEN e CHAT_ID devem estar definidos nos secrets!")

# ------------------------ Utils ------------------------ #
def log(msg: str) -> None:
    ts = dt.datetime.now(brt).strftime("%Y-%m-%d %H:%M:%S")
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
    dt_now = dt.datetime.now(brt).strftime("%d/%m/%Y %H:%M")
    ativos = carregar_ativos()
    triggered: list[str] = []
    log("Iniciando checagem de ativos...")

    for tk, (fv, mos) in ativos.items():
        try:
            price = get_price(tk)
            trigger = fv * (1 - mos)
            gap_pct = (trigger - price) / trigger * 100

            log(f"{tk}: R$ {price:.2f} | Gatilho R$ {trigger:.2f} | Gap {gap_pct:+.1f}%")

            if price <= trigger:
                msg = (
                    f"🕎️ {dt_now} — ALERTA DE COMPRA\n"
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
            time.sleep(0.5)

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
