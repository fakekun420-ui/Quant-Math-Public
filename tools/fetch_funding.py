"""Descarga la serie REAL de funding de Bybit y la deja en disco.

POR QUE A DISCO
---------------
Igual que las velas: una medicion que no queda escrita no se puede repetir ni
auditar, y este numero decide si una operacion es rentable o no. Con 3.800
periodos por simbolo, el funding resulta tener DOS regimenes (el de 2023-2024
y el de 2025-2026 difieren entre 3 y 10 veces), y usar el promedio de los dos
no representa a ninguno.

LAS TRES TRAMPAS DEL ENDPOINT, MEDIDAS EL 2026-10-02
-----------------------------------------------------
1. El metodo privado no existe: `privateGetV5FundingRateHistory` no esta en
   este build de ccxt, yAttributeError no dice nada util.
2. El endpoint publico v3 responde 404: la ruta
   `derivatives/v3/public/funding/history-funding-rate` ya no esta en el
   servidor.
3. El que funciona es `publicGetV5MarketFundingHistory`, y es PUBLICO, o sea
   que medir el funding no necesita clave de API.

Y la cuarta, que es la que hace perder el tiempo: PAGINA CON `endTime` Y NO
CON `end`. Con `end` devuelve siempre la misma pagina, el paginador cree que
retrocede y sale con 200 periodos en vez de 3.800. Es el mismo bucle infinito
que se colgara una vez con el paginador de velas, donde 4.394 filas de un
simbolo se releyeron 40 veces.
"""

import json
import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")

DESDE = 1681948800000  # 2023-04-15, cubre de sobra el periodo backtesteado
DEST = "/sdcard/projects/Quant-Math-Public/data/funding"
SIMBOLOS = {"BTC": "BTCUSDT", "ETH": "ETHUSDT",
            "XRP": "XRPUSDT", "SOL": "SOLUSDT"}

from data_acquisition.data_sources.exchanges import ExchangeAPI


def main() -> int:
    cliente = ExchangeAPI("bybit", data_venue="mainnet").data_client
    if getattr(cliente, "sandbox", False):
        raise SystemExit("ABORTADO: el cliente quedo en SANDBOX")
    os.makedirs(DEST, exist_ok=True)
    resumen = {}
    for nombre, par in SIMBOLOS.items():
        filas, fin = [], None
        while True:
            params = {"category": "linear", "symbol": par, "limit": 200}
            if fin:
                params["endTime"] = fin      # NO `end`: ver la nota del modulo
            try:
                r = cliente.publicGetV5MarketFundingHistory(params)
            except Exception as exc:
                print(f"  {nombre}: {type(exc).__name__}: {str(exc)[:90]}")
                break
            lote = r.get("result", {}).get("list", [])
            if not lote:
                break
            filas.extend(lote)
            minimo = min(int(x["fundingRateTimestamp"]) for x in lote)
            if fin and minimo >= fin:
                break
            if minimo <= DESDE:
                break
            fin = minimo - 1
            time.sleep(0.12)
            if len(lote) < 200:
                break
        if not filas:
            print(f"  {nombre}: sin datos")
            continue
        import pandas as pd
        df = pd.DataFrame(filas)
        df["ts"] = pd.to_datetime(df["fundingRateTimestamp"].astype("int64"),
                                  unit="ms", utc=True)
        df["rate"] = df["fundingRate"].astype(float)
        df = df[["ts", "rate"]].drop_duplicates("ts").sort_values("ts")
        ruta = os.path.join(DEST, f"{nombre}_funding.csv")
        df.to_csv(ruta, index=False)
        resumen[nombre] = {"n": len(df), "desde": str(df["ts"].iloc[0]),
                           "hasta": str(df["ts"].iloc[-1])}
        print(f"  {nombre:4s} {len(df):6d} periodos  "
              f"{str(df['ts'].iloc[0])[:10]} -> {str(df['ts'].iloc[-1])[:10]}")
    json.dump(resumen, open(os.path.join(DEST, "_manifiesto.json"), "w"), indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
