"""
Statistical Models for Probabilistic Forecasting

This module provides time series models for probabilistic predictions including
ARIMA, SARIMA, GARCH, and ARCH models with full probability distributions.
"""

import numpy as np
from typing import Tuple, Optional, Dict, Any
from dataclasses import dataclass
from scipy import stats, signal
from scipy.optimize import minimize


@dataclass
class ARIMAResult:
    """Result of ARIMA model fitting."""
    coefficients: Dict[str, float]
    residuals: np.ndarray
    fitted_values: np.ndarray
    aic: float
    bic: float


class ARIMAModel:
    """
    ARIMA (Autoregressive Integrated Moving Average) Model
    
    Fit ARIMA models with confidence interval estimation for probabilistic forecasting.
    """
    
    def __init__(self, p: int = 1, d: int = 1, q: int = 1):
        """
        Initialize ARIMA model.
        
        Parameters
        ----------
        p : int
            Order of autoregressive terms (AR)
        d : int
            Degree of differencing
        q : int
            Order of moving average terms (MA)
        """
        self.p = p
        self.d = d
        self.q = q
        self.coefficients = None
        self.residuals = None
        self.fitted_values = None
        self.order = (p, d, q)
    
    def fit(self, data: np.ndarray) -> ARIMAResult:
        """
        Fit ARIMA model to data.
        
        Parameters
        ----------
        data : np.ndarray
            Time series data
        
        Returns
        -------
        result : ARIMAResult
            Fitting results
        """
        data = np.asarray(data)
        n = len(data)
        
        # Differencing
        diff_data = data
        for _ in range(self.d):
            diff_data = np.diff(diff_data)
        
        # Estimate AR and MA coefficients using Yule-Walker for AR part
        if self.p > 0:
            # Use autocorrelation for AR coefficients
            acf = np.correlate(diff_data, diff_data, mode='full')[len(diff_data)-1:]
            acf = acf[:self.p]
            
            # Solve Yule-Walker equations
            r = np.zeros(self.p)
            for i in range(self.p):
                r[i] = np.mean(diff_data[:-1-i] * diff_data[i+1:])
            
            try:
                ar_coeff = np.linalg.solve(r[:, np.newaxis] * np.eye(self.p), acf)
                ar_coeff = np.concatenate([[1], -ar_coeff])
            except Exception:
                ar_coeff = np.ones(self.p + 1)
        else:
            ar_coeff = np.array([1.0])
        
        # Estimate MA coefficient using residuals
        if self.q > 0:
            # Fit simple MA using least squares
            from sklearn.linear_model import LinearRegression
            
            X = diff_data[:-self.q]
            y = diff_data[self.q:]
            
            if len(X) > 0:
                lr = LinearRegression()
                lr.fit(X, y)
                ma_coeff = np.concatenate([[-lr.intercept_], lr.coef_])
            else:
                ma_coeff = np.zeros(self.q)
        else:
            ma_coeff = np.array([0.0])
        
        # Compute residuals
        residuals = diff_data - np.convolve(diff_data, ar_coeff[:-1], mode='full')[:len(diff_data)] + \
                    np.convolve(np.zeros_like(diff_data), ma_coeff[1:], mode='full')[:len(diff_data)]
        
        # Compute fitted values
        fitted_diff = np.convolve(diff_data, ar_coeff[:-1], mode='full')[:len(diff_data)]
        fitted_data = fitted_diff - np.convolve(residuals, ma_coeff[1:], mode='full')[:len(diff_data)]
        
        # Invert differencing
        fitted = np.zeros(n)
        fitted[-1] = fitted_data[-1]
        for i in range(n-2, -1, -1):
            fitted[i] = fitted[i+1] + fitted_data[i] if i < len(fitted_data) else fitted[i+1]
        
        # Compute AIC and BIC
        n_params = self.p + self.q
        aic = n * np.log(np.mean(residuals**2)) + 2 * n_params
        bic = n * np.log(np.mean(residuals**2)) + n_params * np.log(n)
        
        self.coefficients = {
            'ar': ar_coeff,
            'ma': ma_coeff,
            'intercept': fitted[0]
        }
        self.residuals = residuals
        self.fitted_values = fitted
        
        return ARIMAResult(
            coefficients=self.coefficients,
            residuals=residuals,
            fitted_values=fitted,
            aic=aic,
            bic=bic
        )
    
    def predict(self, data: np.ndarray, steps: int = 1,
                conf_level: float = 0.95) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Generate probabilistic predictions with confidence intervals.
        
        Parameters
        ----------
        data : np.ndarray
            Historical data for prediction
        steps : int
            Number of steps to predict
        conf_level : float
            Confidence level (0-1)
        
        Returns
        -------
        predictions : np.ndarray
            Point predictions
        lower_ci : np.ndarray
            Lower confidence bounds
        upper_ci : np.ndarray
            Upper confidence bounds
        """
        if self.coefficients is None:
            raise ValueError("Model not fitted yet. Call fit() first.")
        
        data = np.asarray(data)
        n = len(data)
        
        # Get standard deviation of residuals
        residual_std = np.std(self.residuals) if len(self.residuals) > 0 else 1.0
        
        # Calculate critical value
        alpha = 1 - conf_level
        z_critical = stats.norm.ppf(1 - alpha / 2)
        
        # Generate predictions
        ar = self.coefficients['ar']
        ma = self.coefficients['ma']
        
        predictions = np.zeros(steps)
        lower_ci = np.zeros(steps)
        upper_ci = np.zeros(steps)
        
        # For simplicity, use approximate prediction intervals
        prediction_std = np.sqrt(n) * residual_std
        margin = z_critical * prediction_std
        
        for i in range(steps):
            # Simple autoregressive prediction
            if n - i > 0:
                pred = np.sum(data[-i:] * ar[-i-1:-1:-1])
            else:
                pred = np.mean(data)
            
            predictions[i] = pred
            lower_ci[i] = pred - margin
            upper_ci[i] = pred + margin
        
        return predictions, lower_ci, upper_ci
    
    def get_forecast_distribution(self, steps: int = 10) -> Dict[str, Any]:
        """
        Get forecast distribution statistics.
        
        Parameters
        ----------
        steps : int
            Number of steps to forecast
        
        Returns
        -------
        info : dict
            Distribution statistics
        """
        if self.coefficients is None:
            raise ValueError("Model not fitted yet. Call fit() first.")
        
        mean_pred, lower, upper = self.predict(steps=steps, conf_level=0.95)
        
        return {
            'mean': mean_pred,
            'std': (upper - lower) / (2 * stats.norm.ppf(0.975)),
            'confidence_interval': (lower, upper),
            'forecast_range': (np.min(mean_pred), np.max(mean_pred))
        }


class SARIMAModel(ARIMAModel):
    """
    SARIMA (Seasonal ARIMA) Model
    
    Extension of ARIMA with seasonal components.
    """
    
    def __init__(self, p: int = 1, d: int = 1, q: int = 1,
                 seasonal_order: tuple = (0, 0, 0, 0)):
        """
        Initialize SARIMA model.
        
        Parameters
        ----------
        p, d, q : int
            Non-seasonal ARIMA order
        seasonal_order : tuple
            (P, D, Q, s) where s is seasonal period
        """
        super().__init__(p, d, q)
        self.P, self.D, self.Q, self.s = seasonal_order
        self.seasonal_coefficients = None
    
    def fit(self, data: np.ndarray) -> ARIMAResult:
        """Fit SARIMA model to data."""
        data = np.asarray(data)
        
        # Apply seasonal differencing
        seasonal_diff = data.copy()
        for _ in range(self.D):
            seasonal_diff = seasonal_diff[self.s:] - seasonal_diff[:-self.s]
        
        # Fit non-seasonal ARIMA
        super().fit(seasonal_diff)
        
        # Compute seasonal residuals
        if self.Q > 0:
            ma = self.coefficients['ma']
            self.seasonal_residuals = seasonal_diff[self.s:] - \
                np.convolve(seasonal_diff[self.s:], ma[:-1], mode='full')[:len(seasonal_diff[self.s:])]
        else:
            self.seasonal_residuals = self.residuals.copy()
        
        return ARIMAResult(
            coefficients=self.coefficients,
            residuals=self.seasonal_residuals,
            fitted_values=self.fitted_values,
            aic=self.coefficients['ar'][0] * len(data),
            bic=self.coefficients['ar'][0] * len(data)
        )


class ARCHModel:
    """
    ARCH (Autoregressive Conditional Heteroskedasticity) Model
    
    Model volatility clustering with heteroskedastic residuals.
    """
    
    def __init__(self, lags: int = 1):
        """
        Initialize ARCH model.
        
        Parameters
        ----------
        lags : int
            Number of ARCH lags
        """
        self.lags = lags
        self.arch_coefficients = None
        self.residuals = None
        self.volatility = None
    
    def fit(self, data: np.ndarray) -> np.ndarray:
        """
        Fit ARCH model to data.
        
        Parameters
        ----------
        data : np.ndarray
            Time series data
        
        Returns
        -------
        volatility : np.ndarray
            Estimated conditional variance
        """
        data = np.asarray(data)
        n = len(data)
        
        # Compute residuals (assume mean=0 for ARCH)
        residuals = data - np.mean(data)
        self.residuals = residuals
        
        # Initialize volatility
        volatility = np.zeros(n)
        volatility[:self.lags] = np.var(residuals[:self.lags])
        
        # Fit ARCH model
        for i in range(self.lags, n):
            # Compute conditional variance
            arch_terms = residuals[i-self.lags:i]
            volatility[i] = self.arch_coefficients @ arch_terms**2 if self.arch_coefficients is not None else \
                           np.mean(arch_terms**2)
        
        self.volatility = volatility
        
        # Estimate coefficients using OLS
        if self.lags > 0:
            y = residuals[self.lags:]**2
            X = np.column_stack([residuals[i-self.lags:i]**2 for i in range(self.lags, n)])
            
            try:
                from sklearn.linear_model import LinearRegression
                lr = LinearRegression()
                lr.fit(X, y)
                self.arch_coefficients = np.concatenate([lr.intercept_, lr.coef_])
            except Exception:
                self.arch_coefficients = np.ones(self.lags + 1)
        
        return volatility
    
    def predict_volatility(self, n_steps: int = 1) -> np.ndarray:
        """
        Predict future volatility.
        
        Parameters
        ----------
        n_steps : int
            Number of steps to predict
        
        Returns
        -------
        forecast : np.ndarray
            Volatility forecast
        """
        if self.volatility is None:
            raise ValueError("Model not fitted yet. Call fit() first.")
        
        forecast = np.zeros(n_steps)
        
        if self.lags > 0:
            for i in range(n_steps):
                arch_terms = self.residuals[-self.lags:] if len(self.residuals) >= self.lags else self.residuals
                forecast[i] = self.arch_coefficients @ arch_terms**2
        else:
            forecast = np.full(n_steps, np.mean(self.volatility))
        
        return forecast


class GARCHModel(ARCHModel):
    """
    GARCH (Generalized ARCH) Model
    
    Model volatility with both ARCH and GARCH terms.
    """
    
    def __init__(self, lags: int = 1):
        """
        Initialize GARCH model.
        
        Parameters
        ----------
        lags : int
            Number of ARCH and GARCH lags
        """
        super().__init__(lags)
        self.garch_coefficients = None
    
    def fit(self, data: np.ndarray) -> np.ndarray:
        """
        Fit GARCH model to data.
        
        Parameters
        ----------
        data : np.ndarray
            Time series data
        
        Returns
        -------
        volatility : np.ndarray
            Estimated conditional variance
        """
        data = np.asarray(data)
        n = len(data)
        
        # Compute residuals
        residuals = data - np.mean(data)
        self.residuals = residuals
        
        # Initialize volatility
        volatility = np.zeros(n)
        volatility[:self.lags] = np.var(residuals[:self.lags])
        
        # Initialize omega (long-term variance)
        omega = np.mean(residuals**2)
        self.garch_coefficients = np.ones(self.lags + 1)
        
        # Fit GARCH model
        for i in range(self.lags, n):
            # GARCH: sigma_t^2 = omega + alpha * sum(r_{t-i}^2) + beta * sum(sigma_{t-i}^2)
            arch_terms = residuals[i-self.lags:i]**2
            garch_terms = volatility[i-self.lags:i]**2
            
            volatility[i] = omega + self.garch_coefficients[:self.lags] @ arch_terms + \
                          self.garch_coefficients[self.lags:] @ garch_terms
        
        self.volatility = volatility
        
        # Estimate coefficients using OLS
        if self.lags > 0:
            y = residuals[self.lags:]**2
            arch_terms = np.column_stack([residuals[i-self.lags:i]**2 for i in range(self.lags, n)])
            garch_terms = np.column_stack([volatility[i-self.lags:i]**2 for i in range(self.lags, n)])
            X = np.column_stack([arch_terms, garch_terms])
            
            try:
                from sklearn.linear_model import LinearRegression
                lr = LinearRegression()
                lr.fit(X, y)
                self.garch_coefficients = np.concatenate([lr.intercept_, lr.coef_[:self.lags], lr.coef_[self.lags:]])
            except Exception:
                self.garch_coefficients = np.ones(2 * self.lags + 1)
        
        return volatility
    
    def predict_volatility(self, n_steps: int = 1) -> np.ndarray:
        """
        Predict future volatility.
        
        Parameters
        ----------
        n_steps : int
            Number of steps to predict
        
        Returns
        -------
        forecast : np.ndarray
            Volatility forecast
        """
        if self.volatility is None:
            raise ValueError("Model not fitted yet. Call fit() first.")
        
        forecast = np.zeros(n_steps)
        
        if self.lags > 0:
            for i in range(n_steps):
                arch_terms = self.residuals[-self.lags:] if len(self.residuals) >= self.lags else self.residuals
                garch_terms = self.volatility[-self.lags:] if len(self.volatility) >= self.lags else self.volatility
                
                forecast[i] = self.garch_coefficients[0] + \
                             self.garch_coefficients[1:self.lags+1] @ arch_terms**2 + \
                             self.garch_coefficients[self.lags+1:] @ garch_terms**2
        else:
            forecast = np.full(n_steps, np.mean(self.volatility))
        
        return forecast
