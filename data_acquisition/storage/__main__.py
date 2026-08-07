if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.INFO)

    # Example usage
    store = DataStore(
        dbname='quant_math',
        user='postgres',
        password='password',
        host='localhost'
    )

    # Create sample data
    data = [
        {'timestamp': '2024-01-01', 'price': 100.0, 'volume': 1000},
        {'timestamp': '2024-01-02', 'price': 102.0, 'volume': 1200},
        {'timestamp': '2024-01-03', 'price': 101.0, 'volume': 900}
    ]

    # Save data
    row_count = store.save('ohlcv', data)
    print(f"Saved {row_count} rows")

    # Check data quality
    quality = store.check_data_quality('ohlcv')
    print(f"Data quality: {quality}")

    store.close()
