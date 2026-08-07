# Value at Risk Module
import numpy as np

class ValueAtRisk:
    """Value at Risk calculator."""

    @staticmethod
    def calculate(portfolio_value: float, volatility: float, confidence_level: float = 0.95) -> float:
        """
        Calculate Value at Risk using normal distribution.

        Parameters:
        -----------
        portfolio_value : float
            Portfolio value
        volatility : float
            Daily volatility (standard deviation of returns)
        confidence_level : float
            Confidence level (default 0.95)

        Returns:
        --------
        float
            Value at Risk
        """
        z_score = np.percentile(np.abs(np.random.normal(0, 1, 100000)), (1 - confidence_level) * 100)
        var = portfolio_value * z_score * volatility
        return var

    @staticmethod
    def expected_shortfall(portfolio_value: float, volatility: float, confidence_level: float = 0.95) -> float:
        """
        Calculate Expected Shortfall (Expected Loss).

        Parameters:
        -----------
        portfolio_value : float
            Portfolio value
        volatility : float
            Daily volatility (standard deviation of returns)
        confidence_level : float
            Confidence level (default 0.95)

        Returns:
        --------
        float
            Expected Shortfall
        """
        z_score = -np.percentile(np.random.normal(0, 1, 100000), (1 - confidence_level) * 100)
        es = portfolio_value * z_score * volatility
        return es

class ExpectedShortfall:
    """Expected Shortfall calculator."""

    @staticmethod
    def calculate(portfolio_value: float, volatility: float, confidence_level: float = 0.95) -> float:
        """Calculate Expected Shortfall using normal distribution."""
        var = ValueAtRisk(portfolio_value, volatility, confidence_level)
        return var * 0.5
