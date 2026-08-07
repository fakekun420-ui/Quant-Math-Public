if __name__ == '__main__':
    import logging
    import numpy as np
    import pandas as pd
    logging.basicConfig(level=logging.INFO)

    # Create sample data with structural breaks
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=1000)

    # Generate data with two regimes
    regime1 = np.random.normal(100, 1, 500)
    regime2 = np.random.normal(105, 1, 500)
    data = np.concatenate([regime1, regime2])

    df = pd.DataFrame({
        'timestamp': dates,
        'close': data
    })

    print("Original data with structural breaks:")
    print(df.describe())

    # Detect structural breaks
    analysis = StructuralBreakDetector.analyze_breaks(df, col='close', max_breaks=3)

    print("\nStructural Break Analysis:")
    print(f"Stationarity test: {analysis['stationarity']}")
    print(f"Found breaks: {analysis['breaks']}")

    # Resample data
    df_resampled = TimeSeriesResampler.resample(df, rule='1d')
    print(f"\nResampled to daily: {len(df_resampled)} rows")

    # Calculate returns
    returns = TimeSeriesResampler.calculate_returns(df, method='percentage')
    print(f"\nReturns statistics:")
    print(f"  Mean: {returns.mean():.4f}")
    print(f"  Std: {returns.std():.4f}")
