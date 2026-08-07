"""
Data Cleaning Module
Handles missing values, outliers, and structural breaks
"""

import pandas as pd
import numpy as np
from typing import Optional, Union
import logging

logger = logging.getLogger(__name__)


class DataCleaner:
    """
    Data cleaning utilities for time series data
    """

    @staticmethod
    def handle_missing_values(
        df: pd.DataFrame,
        method: str = 'ffill',
        fill_value: Optional[Union[float, int]] = None
    ) -> pd.DataFrame:
        """
        Handle missing values in DataFrame

        Args:
            df: Input DataFrame
            method: 'ffill', 'bfill', 'mean', 'median', 'interpolate', 'fill_value'
            fill_value: Specific value to use (when method='fill_value')

        Returns:
            Cleaned DataFrame
        """
        df_clean = df.copy()

        if df_clean.isnull().sum().sum() == 0:
            logger.info("No missing values found")
            return df_clean

        logger.info(f"Found {df_clean.isnull().sum().sum()} missing values")

        if method == 'ffill':
            df_clean = df_clean.fillna(method='ffill')
            df_clean = df_clean.fillna(method='bfill')
        elif method == 'bfill':
            df_clean = df_clean.fillna(method='bfill')
        elif method == 'mean':
            df_clean = df_clean.fillna(df_clean.mean())
        elif method == 'median':
            df_clean = df_clean.fillna(df_clean.median())
        elif method == 'interpolate':
            df_clean = df_clean.interpolate(method='linear')
        elif method == 'fill_value':
            if fill_value is None:
                fill_value = df_clean.mean().mean()
            df_clean = df_clean.fillna(fill_value)
        else:
            raise ValueError(f"Unknown fill method: {method}")

        # Check for remaining NaNs
        remaining_nans = df_clean.isnull().sum().sum()
        if remaining_nans > 0:
            logger.warning(f"Warning: {remaining_nans} missing values remain after filling")
        else:
            logger.info("All missing values filled successfully")

        return df_clean

    @staticmethod
    def detect_outliers_iqr(
        df: pd.DataFrame,
        column: str,
        multiplier: float = 1.5
    ) -> np.ndarray:
        """
        Detect outliers using IQR method

        Args:
            df: DataFrame
            column: Column to check
            multiplier: IQR multiplier

        Returns:
            Boolean array of outliers
        """
        Q1 = df[column].quantile(0.25)
        Q3 = df[column].quantile(0.75)
        IQR = Q3 - Q1

        lower_bound = Q1 - multiplier * IQR
        upper_bound = Q3 + multiplier * IQR

        outliers = (df[column] < lower_bound) | (df[column] > upper_bound)

        logger.info(f"Detected {outliers.sum()} outliers in {column}")

        return outliers

    @staticmethod
    def cap_outliers(
        df: pd.DataFrame,
        column: str,
        method: str = 'iqr',
        multiplier: float = 1.5
    ) -> pd.DataFrame:
        """
        Cap outliers to specified bounds

        Args:
            df: DataFrame
            column: Column to cap
            method: 'iqr' or 'zscore'
            multiplier: Multiplier for bounds

        Returns:
            DataFrame with capped values
        """
        df_clean = df.copy()

        if method == 'iqr':
            Q1 = df[column].quantile(0.25)
            Q3 = df[column].quantile(0.75)
            IQR = Q3 - Q1
            lower_bound = Q1 - multiplier * IQR
            upper_bound = Q3 + multiplier * IQR
        elif method == 'zscore':
            mean = df[column].mean()
            std = df[column].std()
            lower_bound = mean - multiplier * std
            upper_bound = mean + multiplier * std
        else:
            raise ValueError(f"Unknown method: {method}")

        df_clean[column] = np.where(
            df_clean[column] > upper_bound,
            upper_bound,
            np.where(
                df_clean[column] < lower_bound,
                lower_bound,
                df_clean[column]
            )
        )

        logger.info(f"Capped outliers in {column}")

        return df_clean

    @staticmethod
    def detect_duplicates(df: pd.DataFrame) -> pd.DataFrame:
        """
        Detect and count duplicate rows

        Args:
            df: Input DataFrame

        Returns:
            DataFrame with duplicate info
        """
        duplicates = df.duplicated()
        dup_count = duplicates.sum()

        logger.info(f"Found {dup_count} duplicate rows")

        return pd.DataFrame({
            'is_duplicate': duplicates,
            'count': 1
        }).groupby('is_duplicate').size().reset_index(name='count')

    @staticmethod
    def remove_duplicates(df: pd.DataFrame, subset: Optional[list] = None) -> pd.DataFrame:
        """
        Remove duplicate rows

        Args:
            df: Input DataFrame
            subset: Columns to check for duplicates

        Returns:
            DataFrame without duplicates
        """
        if subset is None:
            subset = df.columns.tolist()

        dup_count_before = len(df)
        df_clean = df.drop_duplicates(subset=subset)
        dup_count_after = len(df_clean)

        removed = dup_count_before - dup_count_after
        logger.info(f"Removed {removed} duplicate rows")

        return df_clean

    @staticmethod
    def check_data_quality(df: pd.DataFrame) -> dict:
        """
        Perform comprehensive data quality check

        Args:
            df: Input DataFrame

        Returns:
            Dictionary with quality metrics
        """
        metrics = {
            'total_rows': len(df),
            'total_columns': len(df.columns),
            'missing_values': df.isnull().sum().sum(),
            'missing_percentage': (df.isnull().sum().sum() / (len(df) * len(df.columns))) * 100,
            'duplicate_rows': df.duplicated().sum()
        }

        for col in df.columns:
            col_stats = {
                'type': df[col].dtype,
                'mean': df[col].mean(),
                'std': df[col].std(),
                'min': df[col].min(),
                'max': df[col].max(),
                'null_count': df[col].isnull().sum(),
                'null_percentage': (df[col].isnull().sum() / len(df)) * 100
            }
            metrics[col] = col_stats

        return metrics

    @staticmethod
    def clean(
        df: pd.DataFrame,
        handle_missing: str = 'ffill',
        handle_outliers: str = 'none',
        remove_duplicates: bool = True,
        verbose: bool = True
    ) -> pd.DataFrame:
        """
        Perform complete data cleaning pipeline

        Args:
            df: Input DataFrame
            handle_missing: Method to handle missing values
            handle_outliers: 'none', 'cap', or 'remove'
            remove_duplicates: Whether to remove duplicates
            verbose: Print cleaning steps

        Returns:
            Cleaned DataFrame
        """
        if verbose:
            print(f"\n{'='*60}")
            print("DATA CLEANING PIPELINE")
            print(f"{'='*60}")

        df_clean = df.copy()

        # Check data quality before
        if verbose:
            quality_before = DataCleaner.check_data_quality(df_clean)
            print(f"Initial quality:")
            print(f"  Total rows: {quality_before['total_rows']}")
            print(f"  Missing values: {quality_before['missing_values']}")
            print(f"  Duplicate rows: {quality_before['duplicate_rows']}")

        # Handle missing values
        if handle_missing != 'none':
            if verbose:
                print(f"\nHandling missing values with '{handle_missing}'...")
            df_clean = DataCleaner.handle_missing_values(df_clean, method=handle_missing)

        # Handle outliers
        if handle_outliers != 'none':
            for col in df_clean.select_dtypes(include=[np.number]).columns:
                if verbose:
                    print(f"  Detecting outliers in {col}...")
                outliers = DataCleaner.detect_outliers_iqr(df_clean, col)
                if handle_outliers == 'cap':
                    df_clean = DataCleaner.cap_outliers(df_clean, col, method='iqr')
                elif handle_outliers == 'remove':
                    df_clean = df_clean[~outliers]

        # Remove duplicates
        if remove_duplicates:
            if verbose:
                print(f"Removing duplicates...")
            df_clean = DataCleaner.remove_duplicates(df_clean)

        # Check data quality after
        if verbose:
            quality_after = DataCleaner.check_data_quality(df_clean)
            print(f"\nFinal quality:")
            print(f"  Total rows: {quality_after['total_rows']}")
            print(f"  Missing values: {quality_after['missing_values']}")
            print(f"  Duplicate rows: {quality_after['duplicate_rows']}")
            print(f"{'='*60}\n")

        return df_clean
