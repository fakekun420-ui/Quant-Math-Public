"""
Value at Risk (VaR) and Expected Shortfall (ES) Module

Pure numpy implementation to avoid scipy dependency.
"""

import numpy as np
from typing import Optional


class ValueAtRisk:
    """
    Value at Risk calculator.

    VaR is the maximum expected loss over a given time horizon
    at a given confidence level.
    """

    def __init__(self, default_method: str = "parametric", default_confidence: float = 0.95):
        """
        Initialize VaR calculator.

        Args:
            default_method: Default VaR method ('parametric', 'historical', 'cornish_fisher')
            default_confidence: Default confidence level
        """
        self.default_method = default_method
        self.default_confidence = default_confidence

    def calculate(
        self,
        mean_return: float = 0.0,
        std_return: float = 0.0,
        confidence: Optional[float] = None,
        method: Optional[str] = None,
        skewness: float = 0.0,
        kurtosis: float = 3.0,
        portfolio_value: float = 1.0
    ) -> float:
        """
        Calculate Value at Risk.

        Supports two call styles:
            Instance: ValueAtRisk(0.95).calculate(mean, std) -> float
            Class:    ValueAtRisk.calculate(portfolio_value, std, confidence) -> float
        """
        # Class-style call: ValueAtRisk.calculate(portfolio_value, std, confidence)
        if not isinstance(self, ValueAtRisk):
            portfolio_value = self
            std_return = mean_return if std_return == 0.0 else std_return
            conf = confidence if confidence is not None else 0.95
            alpha = 1 - conf
            z_score = ValueAtRisk._norm_ppf(alpha)
            var = -(0 + z_score * std_return) * portfolio_value
            return max(0.0, var)

        confidence = confidence or self.default_confidence
        method = method or self.default_method

        alpha = 1 - confidence

        if method == "parametric":
            return self._parametric_var(mean_return, std_return, alpha, portfolio_value)
        elif method == "cornish_fisher":
            return self._cornish_fisher_var(mean_return, std_return, alpha, skewness, kurtosis, portfolio_value)
        elif method == "historical":
            # Would need historical returns
            return self._parametric_var(mean_return, std_return, alpha, portfolio_value)
        else:
            raise ValueError(f"Unknown VaR method: {method}")

    def _parametric_var(self, mean: float, std: float, alpha: float, portfolio_value: float) -> float:
        """Parametric VaR assuming normal distribution."""
        # Normal inverse CDF approximation (using the rational approximation)
        z_score = self._norm_ppf(alpha)
        var = -(mean + z_score * std) * portfolio_value
        return max(0.0, var)

    def _cornish_fisher_var(self, mean: float, std: float, alpha: float,
                            skewness: float, kurtosis: float, portfolio_value: float) -> float:
        """Cornish-Fisher VaR approximation."""
        z = self._norm_ppf(alpha)
        # Cornish-Fisher expansion
        z_cf = (z +
                (z**2 - 1) * skewness / 6 +
                (z**3 - 3*z) * (kurtosis - 3) / 24 -
                (2*z**3 - 5*z) * skewness**2 / 36)
        var = -(mean + z_cf * std) * portfolio_value
        return max(0.0, var)

    @staticmethod
    def _norm_ppf(p: float) -> float:
        """
        Approximation of the inverse standard normal CDF (quantile function).

        Uses the rational approximation from Peter John Acklam.
        """
        # Coefficients in rational approximation
        a = [-3.969683028665376e+01, 2.209460984245205e+02,
             -2.759285104469687e+02, 1.383577518672690e+02,
             -3.066479806614716e+01, 2.506628277459239e+00]
        b = [-5.447609879822406e+01, 1.615858368580409e+02,
             -1.556989798598866e+02, 6.680131188771972e+01,
             -1.328068155288572e+01]
        c = [-7.784894002430293e-03, -3.223964580411365e-01,
             -2.400758277161838e+00, -2.549732539343734e+00,
             4.374664141464968e+00, 2.938163982698783e+00]
        d = [7.784695709041462e-03, 3.224671290700398e-01,
             2.445134137142996e+00, 3.754408661907416e+00]

        p_low = 0.02425
        p_high = 1 - p_low

        if p < 0:
            return -np.inf
        if p > 1:
            return np.inf
        if p == 0:
            return -np.inf
        if p == 1:
            return np.inf

        if p < p_low:
            q = np.sqrt(-2 * np.log(p))
            return (((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5]) / \
                   ((((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1)
        elif p <= p_high:
            q = p - 0.5
            r = q * q
            return (((((a[0]*r + a[1])*r + a[2])*r + a[3])*r + a[4])*r + a[5]) * q / \
                   (((((b[0]*r + b[1])*r + b[2])*r + b[3])*r + b[4])*r + 1)
        else:
            q = np.sqrt(-2 * np.log(1 - p))
            return -(((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5]) / \
                    ((((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1)

    def calculate_from_returns(
        self,
        returns: np.ndarray,
        confidence: Optional[float] = None,
        method: Optional[str] = None,
        portfolio_value: float = 1.0
    ) -> float:
        """
        Calculate VaR from return series.

        Args:
            returns: Array of returns
            confidence: Confidence level
            method: VaR method
            portfolio_value: Portfolio value

        Returns:
            VaR as positive number
        """
        if len(returns) == 0:
            return 0.0

        mean = np.mean(returns)
        std = np.std(returns, ddof=1)
        skewness = self._calculate_skewness(returns)
        kurtosis = self._calculate_kurtosis(returns)

        return self.calculate(mean, std, confidence, method, skewness, kurtosis, portfolio_value)

    def _calculate_skewness(self, returns: np.ndarray) -> float:
        """Calculate skewness."""
        n = len(returns)
        if n < 3:
            return 0.0
        mean = np.mean(returns)
        std = np.std(returns, ddof=1)
        if std == 0:
            return 0.0
        return np.sum(((returns - mean) / std) ** 3) / n

    def _calculate_kurtosis(self, returns: np.ndarray) -> float:
        """Calculate excess kurtosis."""
        n = len(returns)
        if n < 4:
            return 3.0
        mean = np.mean(returns)
        std = np.std(returns, ddof=1)
        if std == 0:
            return 3.0
        return np.sum(((returns - mean) / std) ** 4) / n


class ExpectedShortfall:
    """
    Expected Shortfall calculator.

    ES is the expected loss given that the loss exceeds VaR.
    Also known as Conditional Value at Risk (CVaR).
    """

    def __init__(self, default_method: str = "parametric", default_confidence: float = 0.95):
        """
        Initialize ES calculator.

        Args:
            default_method: Default ES method
            default_confidence: Default confidence level
        """
        self.default_method = default_method
        self.default_confidence = default_confidence

    def calculate(
        self,
        mean_return: float,
        std_return: float,
        confidence: Optional[float] = None,
        method: Optional[str] = None,
        skewness: float = 0.0,
        kurtosis: float = 3.0,
        portfolio_value: float = 1.0
    ) -> float:
        """
        Calculate Expected Shortfall.

        Args:
            mean_return: Mean return
            std_return: Standard deviation of returns
            confidence: Confidence level (uses default if None)
            method: ES method (uses default if None)
            skewness: Return skewness
            kurtosis: Return kurtosis
            portfolio_value: Portfolio value for absolute ES

        Returns:
            ES as positive number (expected loss beyond VaR)
        """
        confidence = confidence or self.default_confidence
        method = method or self.default_method

        alpha = 1 - confidence

        if method == "parametric":
            return self._parametric_es(mean_return, std_return, alpha, portfolio_value)
        elif method == "cornish_fisher":
            return self._cornish_fisher_es(mean_return, std_return, alpha, skewness, kurtosis, portfolio_value)
        elif method == "historical":
            # Would need historical returns
            return self._parametric_es(mean_return, std_return, alpha, portfolio_value)
        else:
            raise ValueError(f"Unknown ES method: {method}")

    def _parametric_es(self, mean: float, std: float, alpha: float, portfolio_value: float) -> float:
        """Parametric ES assuming normal distribution."""
        # For normal: ES = -[mu + sigma * phi(z_alpha) / alpha]
        # where phi is the standard normal PDF
        z_score = ValueAtRisk._norm_ppf(alpha)
        # Standard normal PDF
        phi_z = np.exp(-0.5 * z_score**2) / np.sqrt(2 * np.pi)
        es = -(mean + std * phi_z / alpha) * portfolio_value
        return max(0.0, es)

    def _cornish_fisher_es(self, mean: float, std: float, alpha: float,
                           skewness: float, kurtosis: float, portfolio_value: float) -> float:
        """Cornish-Fisher ES approximation."""
        # This is a simplified approximation
        # For accurate Cornish-Fisher ES, numerical integration is needed
        var = self._cornish_fisher_var(mean, std, alpha, skewness, kurtosis, portfolio_value)
        # ES typically ~ VaR * 1.1 to 1.3 for normal distribution
        # Using 1.25 as approximation
        return var * 1.25

    def _cornish_fisher_var(self, mean: float, std: float, alpha: float,
                            skewness: float, kurtosis: float, portfolio_value: float) -> float:
        """Cornish-Fisher VaR for ES calculation."""
        z = ValueAtRisk._norm_ppf(alpha)
        z_cf = (z +
                (z**2 - 1) * skewness / 6 +
                (z**3 - 3*z) * (kurtosis - 3) / 24 -
                (2*z**3 - 5*z) * skewness**2 / 36)
        var = -(mean + z_cf * std) * portfolio_value
        return max(0.0, var)

    def calculate_from_returns(
        self,
        returns: np.ndarray,
        confidence: Optional[float] = None,
        method: Optional[str] = None,
        portfolio_value: float = 1.0
    ) -> float:
        """
        Calculate ES from return series.

        Args:
            returns: Array of returns
            confidence: Confidence level
            method: ES method
            portfolio_value: Portfolio value

        Returns:
            ES as positive number
        """
        if len(returns) == 0:
            return 0.0

        mean = np.mean(returns)
        std = np.std(returns, ddof=1)
        skewness = self._calculate_skewness(returns)
        kurtosis = self._calculate_kurtosis(returns)

        return self.calculate(mean, std, confidence, method, skewness, kurtosis, portfolio_value)

    def _calculate_skewness(self, returns: np.ndarray) -> float:
        """Calculate skewness."""
        n = len(returns)
        if n < 3:
            return 0.0
        mean = np.mean(returns)
        std = np.std(returns, ddof=1)
        if std == 0:
            return 0.0
        return np.sum(((returns - mean) / std) ** 3) / n

    def _calculate_kurtosis(self, returns: np.ndarray) -> float:
        """Calculate excess kurtosis."""
        n = len(returns)
        if n < 4:
            return 3.0
        mean = np.mean(returns)
        std = np.std(returns, ddof=1)
        if std == 0:
            return 3.0
        return np.sum(((returns - mean) / std) ** 4) / n


# Convenience functions for backward compatibility
def calculate_var(portfolio_value: float, volatility: float, confidence_level: float = 0.95) -> float:
    """Calculate Value at Risk using normal distribution (legacy API)."""
    var_calc = ValueAtRisk()
    return var_calc.calculate(0.0, volatility, confidence_level, "parametric", 0.0, 3.0, portfolio_value)


def expected_shortfall(portfolio_value: float, volatility: float, confidence_level: float = 0.95) -> float:
    """Calculate Expected Shortfall using normal distribution (legacy API)."""
    es_calc = ExpectedShortfall()
    return es_calc.calculate(0.0, volatility, confidence_level, "parametric", 0.0, 3.0, portfolio_value)