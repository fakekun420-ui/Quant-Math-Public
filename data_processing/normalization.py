"""
Data Normalization Module
Provides multiple normalization and scaling methods
"""

import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler, StandardScaler, RobustScaler
from typing import Optional, Union, List
import logging

logger = logging.getLogger(__name__)


class Normalizer:
    """
    Data normalization and scaling utilities
    """

    @staticmethod
    def min_max_scale(
        df: pd.DataFrame,
        feature_range: tuple = (0, 1),
        columns: Optional[List[str]] = None,
        fit: bool = True
    ) -> pd.DataFrame:
        """
        Min-Max normalization

        Args:
            df: Input DataFrame
            feature_range: Desired range (default: 0-1)
            columns: Specific columns to normalize (all if None)
            fit: Whether to fit scaler on data

        Returns:
            Normalized DataFrame
        """
        df_norm = df.copy()

        if columns is None:
            columns = df.select_dtypes(include=[np.number]).columns.tolist()

        scaler = MinMaxScaler(feature_range=feature_range)

        if fit:
            df_norm[columns] = scaler.fit_transform(df[columns])
        else:
            df_norm[columns] = scaler.transform(df[columns])

        # Store scaler for inverse transformation
        df_norm['_scaler'] = scaler

        logger.info(f"Min-Max normalized {len(columns)} columns")
        return df_norm

    @staticmethod
    def z_score_normalize(
        df: pd.DataFrame,
        columns: Optional[List[str]] = None,
        fit: bool = True
    ) -> pd.DataFrame:
        """
        Z-score normalization (standardization)

        Args:
            df: Input DataFrame
            columns: Specific columns to normalize (all if None)
            fit: Whether to fit scaler on data

        Returns:
            Normalized DataFrame
        """
        df_norm = df.copy()

        if columns is None:
            columns = df.select_dtypes(include=[np.number]).columns.tolist()

        scaler = StandardScaler()

        if fit:
            df_norm[columns] = scaler.fit_transform(df[columns])
        else:
            df_norm[columns] = scaler.transform(df[columns])

        # Store scaler for inverse transformation
        df_norm['_scaler'] = scaler

        logger.info(f"Z-score normalized {len(columns)} columns")
        return df_norm

    @staticmethod
    def robust_scale(
        df: pd.DataFrame,
        columns: Optional[List[str]] = None,
        fit: bool = True
    ) -> pd.DataFrame:
        """
        Robust scaling (using median and IQR)

        Args:
            df: Input DataFrame
            columns: Specific columns to normalize (all if None)
            fit: Whether to fit scaler on data

        Returns:
            Normalized DataFrame
        """
        df_norm = df.copy()

        if columns is None:
            columns = df.select_dtypes(include=[np.number]).columns.tolist()

        scaler = RobustScaler()

        if fit:
            df_norm[columns] = scaler.fit_transform(df[columns])
        else:
            df_norm[columns] = scaler.transform(df[columns])

        # Store scaler for inverse transformation
        df_norm['_scaler'] = scaler

        logger.info(f"Robust scaled {len(columns)} columns")
        return df_norm

    @staticmethod
    def standardize(
        df: pd.DataFrame,
        method: str = 'zscore',
        columns: Optional[List[str]] = None
    ) -> tuple:
        """
        Standardize multiple columns

        Args:
            df: Input DataFrame
            method: 'zscore', 'minmax', or 'robust'
            columns: Specific columns to standardize (all if None)

        Returns:
            Tuple of (normalized DataFrame, scaler object)
        """
        if method == 'zscore':
            return Normalizer.z_score_normalize(df, columns=columns), None
        elif method == 'minmax':
            return Normalizer.min_max_scale(df, columns=columns), None
        elif method == 'robust':
            return Normalizer.robust_scale(df, columns=columns), None
        else:
            raise ValueError(f"Unknown method: {method}")

    @staticmethod
    def normalize(
        df: pd.DataFrame,
        method: str = 'zscore',
        columns: Optional[List[str]] = None,
        verbose: bool = True
    ) -> pd.DataFrame:
        """
        Normalize all numerical columns

        Args:
            df: Input DataFrame
            method: Normalization method
            columns: Specific columns (all if None)
            verbose: Print summary

        Returns:
            Normalized DataFrame
        """
        if verbose:
            print(f"\n{'='*60}")
            print(f"NORMALIZATION: {method.upper()}")
            print(f"{'='*60}")

        df_norm = df.copy()

        numerical_cols = df.select_dtypes(include=[np.number]).columns.tolist()

        if columns:
            numerical_cols = [c for c in columns if c in numerical_cols]

        if not numerical_cols:
            logger.warning("No numerical columns found for normalization")
            return df_norm

        if verbose:
            print(f"Normalizing {len(numerical_cols)} columns:")
            for col in numerical_cols:
                print(f"  - {col}")

        if method == 'zscore':
            df_norm = Normalizer.z_score_normalize(df_norm, columns=numerical_cols)
        elif method == 'minmax':
            df_norm = Normalizer.min_max_scale(df_norm, columns=numerical_cols)
        elif method == 'robust':
            df_norm = Normalizer.robust_scale(df_norm, columns=numerical_cols)
        else:
            raise ValueError(f"Unknown normalization method: {method}")

        # Remove temporary scaler attribute
        if '_scaler' in df_norm.columns:
            df_norm = df_norm.drop(columns=['_scaler'])

        # Display statistics
        if verbose:
            print(f"\nNormalized statistics:")
            for col in numerical_cols:
                print(f"  {col}: mean={df_norm[col].mean():.4f}, std={df_norm[col].std():.4f}")

        return df_norm

    @staticmethod
    def inverse_transform(
        df_norm: pd.DataFrame,
        scaler: object,
        columns: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Inverse transform normalized data

        Args:
            df_norm: Normalized DataFrame
            scaler: Fitted scaler object
            columns: Columns to inverse transform (all if None)

        Returns:
            Original-scale DataFrame
        """
        df_orig = df_norm.copy()

        if columns is None:
            numerical_cols = df_norm.select_dtypes(include=[np.number]).columns.tolist()
        else:
            numerical_cols = [c for c in columns if c in df_norm.columns]

        if numerical_cols:
            df_orig[numerical_cols] = scaler.inverse_transform(df_norm[numerical_cols])

        return df_orig
