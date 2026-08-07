if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.INFO)

    # Example usage
    exchange = ExchangeAPI(
        exchange_id='bybit',
        sandbox=False
    )

    # Get available exchanges
    print("Available exchanges:", get_available_exchanges())

    # Fetch OHLCV data
    ohlcv = exchange.fetch_ohlcv('BTC/USDT', timeframe='1h', limit=100)
    df = exchange.ohlcv_to_dataframe(ohlcv)
    print(df.head())

    exchange.close()
