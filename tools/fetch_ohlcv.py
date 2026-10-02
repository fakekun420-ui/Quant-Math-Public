"""Descarga velas REALES de mainnet y las deja en disco, una por simbolo.

Por que a disco y no en memoria: hasta hoy el backtest leia velas de una
variable en RAM, asi que no quedaba rastro de con que se habia medido. Un
backtest sin datos guardados no se puede repetir ni auditar, y esta fase
mide justamente si el motor dice la verdad.

Uso de red, NO de claves: `data_venue="mainnet"` explicito, porque el
cliente por defecto cae a testnet (medido el 2026-10-01) y sus velas tienen
4x el rango del real.
"""
import sys, os, time, json, warnings
warnings.filterwarnings("ignore")
import pandas as pd

DEST = "/sdcard/projects/Quant-Math-Public/data/ohlcv"
SIMBOLOS = ["BTC/USDT:USDT", "ETH/USDT:USDT", "XRP/USDT:USDT", "SOL/USDT:USDT"]
TF = sys.argv[1] if len(sys.argv) > 1 else "15m"
LIMITE_PAGINAS = int(sys.argv[2]) if len(sys.argv) > 2 else 45

from data_acquisition.data_sources.exchanges import ExchangeAPI
api = ExchangeAPI("bybit", data_venue="mainnet")
cli = api.data_client
if getattr(cli, "sandbox", False):
    raise SystemExit("ABORTADO: el cliente de datos quedo en SANDBOX")

os.makedirs(DEST, exist_ok=True)
resumen = {}
for sym in SIMBOLOS:
    todas, fin = [], None
    for _ in range(LIMITE_PAGINAS):
        # MEDIDO el 2026-10-02, dos trampas del cliente de ccxt:
        #  * `limit` va como KWARG, no en `params`. Con
        #    `params={"limit": 1000}` salen 200 velas, porque ccxt aplica su
        #    default DESPUES. Con `limit=1000` salen 1.000.
        #  * `end` NO es un kwarg (TypeError) y tiene que ir en `params`,
        #    pero SE COMBINA con el `limit` de kwarg sin pisarlo.
        # O sea: `limit` por kwarg y `end` por `params`, en la misma llamada.
        kwargs = {"limit": 1000}
        params = {}
        if fin:
            params["end"] = fin
        try:
            lote = cli.fetch_ohlcv(sym, TF, params=params,
                                   **kwargs)
            lote = lote if lote is not None else []
        except Exception as exc:
            print(f"  {sym}: pagina fallida: {type(exc).__name__}: {exc}")
            break
        if not lote:
            break
        todas.extend(lote)
        nuevo = min(r[0] for r in lote)
        if fin and nuevo >= fin:
            break
        fin = nuevo - 1
        time.sleep(0.12)          # rate limit
        if len(lote) < 1000:
            break
    if not todas:
        print(f"  {sym}: sin velas")
        continue
    df = pd.DataFrame(todas, columns=["ts","open","high","low","close","volume"])
    df = df.drop_duplicates(subset="ts").sort_values("ts").reset_index(drop=True)
    df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    ruta = os.path.join(DEST, f"{sym.split('/')[0]}_{TF}.csv")
    # CSV y no parquet: no hay pyarrow en este entorno, y el CSV ademas se
    # puede abrir a ojo para auditar que los datos son los que dicen ser.
    df.to_csv(ruta, index=False)
    d = pd.to_datetime(df["ts"], unit="ms", utc=True)
    span = (d.iloc[-1] - d.iloc[0]).days
    resumen[sym] = {"velas": len(df), "dias": span,
                    "desde": str(d.iloc[0]), "hasta": str(d.iloc[-1]),
                    "bytes": os.path.getsize(ruta)}
    print(f"  {sym:16s} {len(df):6d} velas  {span:4d} dias  "
          f"{d.iloc[0].date()} -> {d.iloc[-1].date()}  "
          f"{os.path.getsize(ruta)//1024} KB")
json.dump(resumen, open(os.path.join(DEST, f"_manifiesto_{TF}.json"), "w"),
          indent=2, ensure_ascii=False)
print("total:", sum(r["velas"] for r in resumen.values()), "velas")
