if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.INFO)

    # Example: Fetch and save market data
    from .data_sources.exchanges import ExchangeAPI
    from .storage.database import DataStore

    exchange = ExchangeAPI(
        exchange_id='bybit',
        sandbox=False
    )

    store = DataStore(
        dbname='quant_math',
        user='postgres',
        password='password',
        host='localhost'
    )

    # Fetch OHLCV data
    ohlcv = exchange.fetch_ohlcv('BTC/USDT', timeframe='1h', limit=1000)
    df = exchange.ohlcv_to_dataframe(ohlcv)

    # Save to database
    data = df.to_dict('records')
    row_count = store.save('ohlcv', data)
    print(f"Saved {row_count} rows to database")

    store.close()
    exchange.close()
