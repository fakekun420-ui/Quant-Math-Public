"""
Time Series Resampling Module
Provides time series aggregation and resampling utilities
"""

import pandas as pd
import numpy as np
from typing import Optional, Union
import logging

logger = logging.getLogger(__name__)


class TimeSeriesResampler:
    """
    Time series resampling and aggregation utilities
    """

    @staticmethod
    def resample(
        df: pd.DataFrame,
        timestamp_col: str = 'timestamp',
        rule: str = '1h',
        agg_funcs: Optional[dict] = None
    ) -> pd.DataFrame:
        """
        Resample time series data

        Args:
            df: Input DataFrame with timestamp column
            timestamp_col: Name of timestamp column
            rule: Resampling rule ('1h', '30min', '5min', '1d', etc.)
            agg_funcs: Aggregation functions dictionary

        Returns:
            Resampled DataFrame
        """
        if agg_funcs is None:
            agg_funcs = {
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }

        df_resampled = df.set_index(timestamp_col)

        try:
            df_resampled = df_resampled.resample(rule).agg(agg_funcs)
        except Exception as e:
            logger.error(f"Resampling failed: {e}")
            raise

        logger.info(f"Resampled {rule} to {len(df_resampled)} rows")

        return df_resampled

    @staticmethod
    def aggregate_by_timeframe(
        df: pd.DataFrame,
        timestamp_col: str = 'timestamp',
        periods: int = 60,
        agg_funcs: Optional[dict] = None
    ) -> pd.DataFrame:
        """
        Aggregate data into fixed period intervals

        Args:
            df: Input DataFrame
            timestamp_col: Timestamp column name
            periods: Number of periods to aggregate
            agg_funcs: Aggregation functions

        Returns:
            Aggregated DataFrame
        """
        df['time_bucket'] = (
            pd.to_datetime(df[timestamp_col]).dt.floor(f'{periods}min')
        )

        if agg_funcs is None:
            agg_funcs = {
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }

        df_agg = df.groupby('time_bucket').agg(agg_funcs).reset_index()
        df_agg = df_agg.rename(columns={'time_bucket': timestamp_col})

        logger.info(f"Aggregated {len(df)} rows into {len(df_agg)} periods of {periods} min")

        return df_agg

    @staticmethod
    def calculate_returns(
        df: pd.DataFrame,
        price_col: str = 'close',
        method: str = 'percentage'
    ) -> pd.Series:
        """
        Calculate returns from price data

        Args:
            df: Input DataFrame with price column
            price_col: Price column name
            method: 'percentage', 'log', or 'difference'

        Returns:
            Series of returns
        """
        if method == 'percentage':
            returns = df[price_col].pct_change()
        elif method == 'log':
            returns = np.log(df[price_col] / df[price_col].shift(1))
        elif method == 'difference':
            returns = df[price_col].diff()
        else:
            raise ValueError(f"Unknown method: {method}")

        logger.info(f"Calculated {method} returns")
        return returns

    @staticmethod
    def calculate_volatility(
        df: pd.DataFrame,
        price_col: str = 'close',
        window: int = 20,
        method: str = 'rolling_std'
    ) -> pd.Series:
        """
        Calculate volatility

        Args:
            df: Input DataFrame with price column
            price_col: Price column name
            window: Rolling window size
            method: 'rolling_std', 'rolling_range', or 'atr'

        Returns:
            Series of volatility values
        """
        if method == 'rolling_std':
            volatility = df[price_col].rolling(window=window).std()
        elif method == 'rolling_range':
            volatility = df[['high', 'low']].rolling(window=window).apply(
                lambda x: (x['high'] - x['low']) / x['close'].iloc[-1],
                raw=True
            )
        elif method == 'atr':
            high_low = df['high'] - df['low']
            high_close = np.abs(df['high'] - df['close'].shift(1))
            low_close = np.abs(df['low'] - df['close'].shift(1))
            tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            volatility = tr.rolling(window=window).mean()
        else:
            raise ValueError(f"Unknown method: {method}")

        logger.info(f"Calculated {method} volatility with window {window}")
        return volatility

    @staticmethod
    def shift_data(
        df: pd.DataFrame,
        cols: Optional[list] = None,
        periods: int = 1,
        fill_value: float = np.nan
    ) -> pd.DataFrame:
        """
        Shift data by specified periods

        Args:
            df: Input DataFrame
            cols: Columns to shift (all if None)
            periods: Number of periods to shift
            fill_value: Value to fill NaN with

        Returns:
            Shifted DataFrame
        """
        if cols is None:
            cols = df.select_dtypes(include=[np.number]).columns.tolist()

        df_shifted = df.copy()

        for col in cols:
            if col in df_shifted.columns:
                df_shifted[col] = df_shifted[col].shift(periods)
                df_shifted[col] = df_shifted[col].fillna(fill_value)

        logger.info(f"Shifted {len(cols)} columns by {periods} periods")

        return df_shifted

    @staticmethod
    def create_time_features(df: pd.DataFrame, timestamp_col: str = 'timestamp') -> pd.DataFrame:
        """
        Create time-based features

        Args:
            df: Input DataFrame
            timestamp_col: Timestamp column name

        Returns:
            DataFrame with additional time features
        """
        df_time = df.copy()
        df_time['timestamp'] = pd.to_datetime(df_time[timestamp_col])

        # Extract time features
        df_time['year'] = df_time['timestamp'].dt.year
        df_time['month'] = df_time['timestamp'].dt.month
        df_time['day'] = df_time['timestamp'].dt.day
        df_time['hour'] = df_time['timestamp'].dt.hour
        df_time['dayofweek'] = df_time['timestamp'].dt.dayofweek
        df_time['dayofyear'] = df_time['timestamp'].dt.dayofyear
        df_time['weekofyear'] = df_time['timestamp'].dt.isocalendar().week.astype(int)

        # Cyclical encoding
        df_time['hour_sin'] = np.sin(2 * np.pi * df_time['hour'] / 24)
        df_time['hour_cos'] = np.cos(2 * np.pi * df_time['hour'] / 24)
        df_time['dayofweek_sin'] = np.sin(2 * np.pi * df_time['dayofweek'] / 7)
        df_time['dayofweek_cos'] = np.cos(2 * np.pi * df_time['dayofweek'] / 7)

        logger.info(f"Created time features")
        return df_time

    @staticmethod
    def resample_to_frequency(
        df: pd.DataFrame,
        target_freq: str = '1h',
        how: str = 'last',
        timestamp_col: str = None
    ) -> pd.DataFrame:
        """
        Resample to specific frequency

        Args:
            df: Input DataFrame
            target_freq: Target frequency ('1h', '4h', '30min', etc.)
            how: Aggregation method ('last', 'first', 'mean', 'sum')
            timestamp_col: Timestamp column (auto-detected if None)

        Returns:
            Resampled DataFrame
        """
        # Auto-detect the timestamp column if not provided
        if timestamp_col is None or timestamp_col not in df.columns:
            candidates = ['timestamp', 'date', 'time', 'datetime', 'open_time']
            timestamp_col = next(
                (c for c in df.columns if c.lower() in candidates), None)
            if timestamp_col is None:
                raise ValueError(
                    f"No timestamp column found in {list(df.columns)}")

        agg_map = {
            'last': 'last',
            'first': 'first',
            'mean': 'mean',
            'sum': 'sum',
            'ohlc': lambda x: pd.Series({
                'open': x['open'].iloc[0],
                'high': x['high'].max(),
                'low': x['low'].min(),
                'close': x['close'].iloc[-1],
                'volume': x['volume'].sum()
            })
        }

        df.set_index(timestamp_col, inplace=True)
        df_resampled = df.resample(target_freq).agg(agg_map[how])

        logger.info(f"Resampled to {target_freq} using {how}")
        return df_resampled
