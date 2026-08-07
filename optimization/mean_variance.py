# Mean-Variance Optimization Module
import numpy as np

class MeanVarianceOptimizer:
    """Mean-variance portfolio optimization."""

    @staticmethod
    def optimize(expected_returns: np.ndarray, cov_matrix: np.ndarray,
                 target_return: float = None, risk_aversion: float = 1.0) -> np.ndarray:
        """
        Optimize portfolio weights for minimum variance.

        Parameters:
        -----------
        expected_returns : np.ndarray
            Expected returns for each asset
        cov_matrix : np.ndarray
            Covariance matrix of returns
        target_return : float, optional
            Target portfolio return
        risk_aversion : float
            Risk aversion parameter

        Returns:
        --------
        np.ndarray
            Optimal portfolio weights
        """
        n_assets = len(expected_returns)

        # Define objective: minimize variance
        def portfolio_variance(weights):
            return weights @ cov_matrix @ weights

        # Constraints: sum of weights = 1
        def constraint_sum_weights(weights):
            return np.sum(weights) - 1

        # Bounds: weights between 0 and 1
        bounds = tuple((0, 1) for _ in range(n_assets))

        # Initial guess: equal weights
        x0 = np.ones(n_assets) / n_assets

        # Simple optimization using scipy if available, otherwise use naive approach
        try:
            from scipy.optimize import minimize
            result = minimize(portfolio_variance, x0, method='SLSQP',
                              bounds=bounds, constraints={'type': 'eq', 'fun': constraint_sum_weights})
            return result.x if result.success else x0
        except ImportError:
            # Fallback: simple gradient descent
            weights = x0.copy()
            learning_rate = 0.01
            for _ in range(100):
                gradient = 2 * cov_matrix @ weights
                weights -= learning_rate * gradient
                weights = np.clip(weights, 0, 1)
                weights = weights / np.sum(weights)
            return weights

    @staticmethod
    def efficient_frontier(expected_returns: np.ndarray, cov_matrix: np.ndarray,
                           n_points: int = 50) -> tuple:
        """
        Generate efficient frontier points.

        Parameters:
        -----------
        expected_returns : np.ndarray
            Expected returns for each asset
        cov_matrix : np.ndarray
            Covariance matrix of returns
        n_points : int
            Number of points to generate

        Returns:
        --------
        tuple
            (returns, volatilities, weights) for efficient frontier
        """
        n_assets = len(expected_returns)

        # Optimize for minimum variance at different returns
        min_return = expected_returns.min()
        max_return = expected_returns.max()

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
                return expected_returns @ weights - ret

            # Bounds: weights between 0 and 1
            bounds = tuple((0, 1) for _ in range(n_assets))

            # Initial guess: equal weights
            x0 = np.ones(n_assets) / n_assets

            # Optimize
            try:
                from scipy.optimize import minimize
                result = minimize(
                    lambda w: w @ cov_matrix @ w,
                    x0, method='SLSQP', bounds=bounds,
                    constraints=[{'type': 'eq', 'fun': constraint_sum_weights},
                                 {'type': 'eq', 'fun': constraint_target_return}]
                )
                if result.success:
                    weights = result.x
                    volatility = np.sqrt(weights @ cov_matrix @ weights)
                else:
                    weights = x0
                    volatility = np.sqrt(x0 @ cov_matrix @ x0)
            except ImportError:
                # Fallback simple approach
                weights = x0.copy()
                volatility = np.sqrt(weights @ cov_matrix @ weights)

            volatilities.append(volatility)
            weights_list.append(weights)

        return returns, np.array(volatilities), weights_list
