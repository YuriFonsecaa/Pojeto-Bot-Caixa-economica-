from __future__ import annotations

import re
import sqlite3
import time
import threading
from dataclasses import dataclass
from typing import Iterable

import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

# ================= CONFIG =================
URL_BUSCA = "https://venda-imoveis.caixa.gov.br/sistema/busca-imovel.asp"
INTERVALO_MINUTOS = 1

FILTRO_LOCAL = []
FILTRO_PRECO = None

TELEGRAM_BOT_TOKEN = "8798439191:AAH12kz-6KcqqiexVtHN8Mv5lNpD2Nm8lS0"
TELEGRAM_CHAT_ID = "7729132456"
# ==========================================


@dataclass
class Imovel:
    titulo: str
    localidade: str
    preco: float | None
    url: str


def extrair_preco(texto: str) -> float | None:
    achou = re.search(r"r\$\s*([\d\.]+,\d{2})", texto.lower())
    if not achou:
        return None
    bruto = achou.group(1).replace(".", "").replace(",", ".")
    try:
        return float(bruto)
    except:
        return None


def buscar_imoveis() -> list[Imovel]:
    return [
        Imovel(
            titulo="Casa em Olinda - 2 quartos",
            localidade="olinda",
            preco=200000,
            url="https://exemplo.com/imovel1"
        ),
        Imovel(
            titulo="Apartamento em Recife - 3 quartos",
            localidade="recife",
            preco=300000,
            url="https://exemplo.com/imovel2"
        )
    ]


def filtrar(imoveis: Iterable[Imovel]) -> list[Imovel]:
    locais = [x.lower() for x in FILTRO_LOCAL if x]

    resultado = []

    for item in imoveis:
        local_ok = True
        preco_ok = True

        if locais:
            local_ok = any(
                l in (item.localidade + " " + item.titulo).lower()
                for l in locais
            )

        if FILTRO_PRECO:
            preco_ok = item.preco is not None and item.preco <= FILTRO_PRECO

        if local_ok or preco_ok:
            resultado.append(item)

    return resultado


def iniciar_banco():
    conn = sqlite3.connect("historico.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS alertados (
            url TEXT PRIMARY KEY
        )
    """)
    conn.commit()
    return conn


def ja_alertado(conn, url):
    cur = conn.execute("SELECT 1 FROM alertados WHERE url = ?", (url,))
    return cur.fetchone() is not None


def salvar_alertado(conn, url):
    conn.execute("INSERT OR IGNORE INTO alertados(url) VALUES(?)", (url,))
    conn.commit()


def enviar_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg})


def formatar(item: Imovel):
    return f"🏠 {item.titulo}\n💰 {item.preco}\n🔗 {item.url}"


def loop():
    conn = iniciar_banco()

    while True:
        try:
            encontrados = buscar_imoveis()
            filtrados = filtrar(encontrados)
            novos = [x for x in filtrados if not ja_alertado(conn, x.url)]

            for item in novos:
             enviar_telegram(formatar(item))
            salvar_alertado(conn, item.url)
            print(f"[OK] encontrados={len(encontrados)} | filtrados={len(filtrados)} | novos={len(novos)}")

        except Exception as e:
            print("[ERRO]", e)

        time.sleep(INTERVALO_MINUTOS * 60)


async def receber(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global FILTRO_LOCAL, FILTRO_PRECO

    texto = update.message.text.lower()

    if "cidade" in texto:
        FILTRO_LOCAL = [texto.split("cidade")[1].strip().split()[0]]

    if "preco" in texto:
        valor = re.findall(r"\d+", texto)
        if valor:
            FILTRO_PRECO = int(valor[0])

    await update.message.reply_text(f"Cidade: {FILTRO_LOCAL} | Preço: {FILTRO_PRECO}")


def bot():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT, receber))
    print("[BOT] rodando...")
    app.run_polling()


if __name__ == "__main__":
    t = threading.Thread(target=loop, daemon=True)
    t.start()

    bot()