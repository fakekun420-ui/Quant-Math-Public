# Mean-Variance Optimization Module
import numpy as np

class MeanVarianceOptimizer:
    """Mean-variance portfolio optimization."""

    def __init__(self, expected_returns: np.ndarray = None, cov_matrix: np.ndarray = None):
        """
        Initialize optimizer.

        Parameters:
        -----------
        expected_returns : np.ndarray, optional
            Expected returns for each asset
        cov_matrix : np.ndarray, optional
            Covariance matrix of returns

        If provided, optimize() and efficient_frontier() can be called
        without repeating the arguments.
        """
        self.expected_returns = expected_returns
        self.cov_matrix = cov_matrix

    def optimize(self, expected_returns: np.ndarray = None, cov_matrix: np.ndarray = None,
                 target_return: float = None, risk_aversion: float = 1.0) -> np.ndarray:
        """
        Optimize portfolio weights for minimum variance.

        Parameters:
        -----------
        expected_returns : np.ndarray, optional
            Expected returns for each asset (defaults to constructor value)
        cov_matrix : np.ndarray, optional
            Covariance matrix of returns (defaults to constructor value)
        target_return : float, optional
            Target portfolio return
        risk_aversion : float
            Risk aversion parameter

        Returns:
        --------
        np.ndarray
            Optimal portfolio weights
        """
        er = expected_returns if expected_returns is not None else self.expected_returns
        cm = cov_matrix if cov_matrix is not None else self.cov_matrix
        n_assets = len(er)

        # Define objective: minimize variance
        def portfolio_variance(weights):
            return weights @ cm @ weights

        constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]
        if target_return is not None:
            constraints.append(
                {'type': 'eq', 'fun': lambda w: er @ w - target_return})

        # Bounds: weights between 0 and 1
        bounds = tuple((0, 1) for _ in range(n_assets))

        # Initial guess: equal weights
        x0 = np.ones(n_assets) / n_assets

        # Simple optimization using scipy if available, otherwise use naive approach
        try:
            from scipy.optimize import minimize
            result = minimize(portfolio_variance, x0, method='SLSQP',
                              bounds=bounds, constraints=constraints)
            return result.x if result.success else x0
        except ImportError:
            # Fallback: simple gradient descent
            weights = x0.copy()
            learning_rate = 0.01
            for _ in range(100):
                gradient = 2 * cm @ weights
                weights -= learning_rate * gradient
                weights = np.clip(weights, 0, 1)
                weights = weights / np.sum(weights)
            return weights

    def efficient_frontier(self, expected_returns: np.ndarray = None,
                           cov_matrix: np.ndarray = None,
                           n_points: int = 50) -> tuple:
        """
        Generate efficient frontier points.

        Parameters:
        -----------
        expected_returns : np.ndarray, optional
            Expected returns for each asset (defaults to constructor value)
        cov_matrix : np.ndarray, optional
            Covariance matrix of returns (defaults to constructor value)
        n_points : int
            Number of points to generate

        Returns:
        --------
        tuple
            (returns, volatilities, weights) for efficient frontier
        """
        er = expected_returns if expected_returns is not None else self.expected_returns
        cm = cov_matrix if cov_matrix is not None else self.cov_matrix
        n_assets = len(er)

        # Optimize for minimum variance at different returns
        min_return = er.min()
        max_return = er.max()

        returns = np.linspace(min_return, max_return, n_points)
        volatilities = []
        weights_list = []

        try:
            from scipy.optimize import minimize
        except ImportError:
            # Fallback using simple optimization
            pass

        for ret in returns:
            # Define constraints
            def constraint_sum_weights(weights):
                return np.sum(weights) - 1

            def constraint_target_return(weights):
                return er @ weights - ret

            # Bounds: weights between 0 and 1
            bounds = tuple((0, 1) for _ in range(n_assets))

            # Initial guess: equal weights
            x0 = np.ones(n_assets) / n_assets

            # Optimize
            try:
                from scipy.optimize import minimize
                result = minimize(
                    lambda w: w @ cm @ w,
                    x0, method='SLSQP', bounds=bounds,
                    constraints=[{'type': 'eq', 'fun': constraint_sum_weights},
                                 {'type': 'eq', 'fun': constraint_target_return}]
                )
                if result.success:
                    weights = result.x
                    volatility = np.sqrt(weights @ cm @ weights)
                else:
                    weights = x0
                    volatility = np.sqrt(x0 @ cm @ x0)
            except ImportError:
                # Fallback simple approach
                weights = x0.copy()
                volatility = np.sqrt(weights @ cm @ weights)

            volatilities.append(volatility)
            weights_list.append(weights)

        return returns, np.array(volatilities), weights_list
