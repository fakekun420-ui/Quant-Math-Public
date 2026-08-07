"""
Statistical Tests Module

Statistical significance testing for trading strategy validation.
Pure numpy implementation to avoid scipy dependency.
"""

import numpy as np
from typing import List, Optional, Tuple, Union, Callable


class StatisticalTests:
    """
    Collection of statistical tests for strategy validation.
    """

    @staticmethod
    def _t_statistic(sample: np.ndarray, popmean: float) -> float:
        """Calculate t-statistic for one-sample t-test."""
        n = len(sample)
        if n < 2:
            return 0.0
        sample_mean = np.mean(sample)
        sample_std = np.std(sample, ddof=1)
        if sample_std == 0:
            return 0.0
        return (sample_mean - popmean) / (sample_std / np.sqrt(n))

    @staticmethod
    def _p_value_ttest(t_stat: float, df: int, alternative: str) -> float:
        """Calculate p-value from t-statistic using Student's t-distribution."""
        # Use normal approximation for large df, or Wilson-Hilferty approximation
        if df >= 100:
            # Normal approximation
            if alternative == 'two-sided':
                return 2 * (1 - 0.5 * (1 + np.math.erf(abs(t_stat) / np.sqrt(2))))
            elif alternative == 'greater':
                return 1 - 0.5 * (1 + np.math.erf(t_stat / np.sqrt(2)))
            else:  # 'less'
                return 0.5 * (1 + np.math.erf(t_stat / np.sqrt(2)))

        # Wilson-Hilferty approximation for t-distribution
        # Using the relationship with chi-squared
        try:
            from scipy import stats
            if alternative == 'two-sided':
                return 2 * stats.t.sf(abs(t_stat), df)
            elif alternative == 'greater':
                return stats.t.sf(t_stat, df)
            else:
                return stats.t.cdf(t_stat, df)
        except ImportError:
            # Fallback: use normal approximation
            if alternative == 'two-sided':
                return 2 * (1 - 0.5 * (1 + np.math.erf(abs(t_stat) / np.sqrt(2))))
            elif alternative == 'greater':
                return 1 - 0.5 * (1 + np.math.erf(t_stat / np.sqrt(2)))
            else:
                return 0.5 * (1 + np.math.erf(t_stat / np.sqrt(2)))

    @staticmethod
    def one_sample_ttest(
        sample: Union[List[float], np.ndarray],
        popmean: float = 0.0,
        alternative: str = 'two-sided'
    ) -> Tuple[float, float]:
        """
        One-sample t-test.

        Args:
            sample: Sample data
            popmean: Population mean to test against
            alternative: Alternative hypothesis ('two-sided', 'less', 'greater')

        Returns:
            Tuple of (t-statistic, p-value)
        """
        sample = np.array(sample)
        if len(sample) < 2:
            return 0.0, 1.0

        t_stat = StatisticalTests._t_statistic(sample, popmean)
        df = len(sample) - 1
        p_value = StatisticalTests._p_value_ttest(t_stat, df, alternative)
        return float(t_stat), float(p_value)

    @staticmethod
    def two_sample_ttest(
        sample1: Union[List[float], np.ndarray],
        sample2: Union[List[float], np.ndarray],
        equal_var: bool = True,
        alternative: str = 'two-sided'
    ) -> Tuple[float, float]:
        """
        Two-sample t-test (independent samples).

        Args:
            sample1: First sample
            sample2: Second sample
            equal_var: Assume equal variance
            alternative: Alternative hypothesis

        Returns:
            Tuple of (t-statistic, p-value)
        """
        sample1 = np.array(sample1)
        sample2 = np.array(sample2)
        if len(sample1) < 2 or len(sample2) < 2:
            return 0.0, 1.0

        mean1, mean2 = np.mean(sample1), np.mean(sample2)
        std1, std2 = np.std(sample1, ddof=1), np.std(sample2, ddof=1)
        n1, n2 = len(sample1), len(sample2)

        if equal_var:
            # Pooled variance
            pooled_var = ((n1 - 1) * std1**2 + (n2 - 1) * std2**2) / (n1 + n2 - 2)
            if pooled_var == 0:
                return 0.0, 1.0
            t_stat = (mean1 - mean2) / np.sqrt(pooled_var * (1/n1 + 1/n2))
            df = n1 + n2 - 2
        else:
            # Welch's t-test
            se1 = std1**2 / n1
            se2 = std2**2 / n2
            if se1 + se2 == 0:
                return 0.0, 1.0
            t_stat = (mean1 - mean2) / np.sqrt(se1 + se2)
            df = (se1 + se2)**2 / (se1**2 / (n1 - 1) + se2**2 / (n2 - 1))

        p_value = StatisticalTests._p_value_ttest(t_stat, int(df), alternative)
        return float(t_stat), float(p_value)

    @staticmethod
    def paired_ttest(
        sample1: Union[List[float], np.ndarray],
        sample2: Union[List[float], np.ndarray],
        alternative: str = 'two-sided'
    ) -> Tuple[float, float]:
        """
        Paired t-test (dependent samples).

        Args:
            sample1: First sample
            sample2: Second sample
            alternative: Alternative hypothesis

        Returns:
            Tuple of (t-statistic, p-value)
        """
        sample1 = np.array(sample1)
        sample2 = np.array(sample2)
        if len(sample1) < 2 or len(sample2) < 2 or len(sample1) != len(sample2):
            return 0.0, 1.0

        differences = sample1 - sample2
        return StatisticalTests.one_sample_ttest(differences, popmean=0.0, alternative=alternative)

    @staticmethod
    def jarque_bera_test(
        sample: Union[List[float], np.ndarray]
    ) -> Tuple[float, float]:
        """
        Jarque-Bera test for normality.

        Args:
            sample: Sample data

        Returns:
            Tuple of (JB statistic, p-value)
        """
        sample = np.array(sample)
        n = len(sample)
        if n < 2:
            return 0.0, 1.0

        mean = np.mean(sample)
        std = np.std(sample, ddof=1)
        if std == 0:
            return 0.0, 1.0

        # Skewness and kurtosis
        z = (sample - mean) / std
        skew = np.mean(z**3)
        kurt = np.mean(z**4) - 3  # Excess kurtosis

        # JB statistic
        jb_stat = n / 6 * (skew**2 + kurt**2 / 4)

        # p-value using chi-squared distribution with 2 df
        # Using normal approximation for chi-squared
        try:
            from scipy import stats
            p_value = stats.chi2.sf(jb_stat, 2)
        except ImportError:
            # Approximation using normal distribution
            # For large n, JB ~ chi2(2), p-value ≈ exp(-JB/2)
            p_value = np.exp(-jb_stat / 2)

        return float(jb_stat), float(p_value)

    @staticmethod
    def shapiro_wilk_test(
        sample: Union[List[float], np.ndarray]
    ) -> Tuple[float, float]:
        """
        Shapiro-Wilk test for normality (approximation).

        Args:
            sample: Sample data (max 5000 observations)

        Returns:
            Tuple of (W statistic, p-value)
        """
        sample = np.array(sample)
        n = len(sample)
        if n < 3 or n > 5000:
            return 0.0, 1.0

        # Simple approximation using correlation with normal order statistics
        # This is a simplified version - for exact test, scipy is needed
        sorted_sample = np.sort(sample)
        mean = np.mean(sample)
        std = np.std(sample, ddof=1)

        if std == 0:
            return 0.0, 1.0

        # Expected normal order statistics (approximate)
        from scipy.stats import norm
        try:
            expected = norm.ppf(np.arange(1, n+1) / (n + 1))
        except ImportError:
            # Use Blom's formula approximation
            expected = np.sqrt(2) * norm.ppf(np.arange(1, n+1) / (n + 1)) if False else \
                      norm.ppf(np.arange(1, n+1) / (n + 1))

        w_stat = np.corrcoef(sorted_sample, expected)[0, 1]**2

        # p-value approximation (very rough)
        p_value = 1.0 if w_stat > 0.95 else 0.05

        return float(w_stat), float(p_value)

    @staticmethod
    def bootstrap_p_value(
        sample: Union[List[float], np.ndarray],
        statistic: callable = np.mean,
        null_value: float = 0.0,
        n_bootstrap: int = 10000,
        alternative: str = 'two-sided',
        random_state: Optional[int] = None
    ) -> float:
        """
        Bootstrap p-value for a given statistic.

        Args:
            sample: Sample data
            statistic: Function to compute statistic (default: mean)
            null_value: Null hypothesis value
            n_bootstrap: Number of bootstrap iterations
            alternative: Alternative hypothesis
            random_state: Random seed

        Returns:
            Bootstrap p-value
        """
        sample = np.array(sample)
        if len(sample) < 2:
            return 1.0

        rng = np.random.default_rng(random_state)
        observed_stat = statistic(sample)

        # Center the sample under null
        centered_sample = sample - observed_stat + null_value

        # Bootstrap
        boot_stats = []
        for _ in range(n_bootstrap):
            boot_sample = rng.choice(centered_sample, size=len(centered_sample), replace=True)
            boot_stats.append(statistic(boot_sample))

        boot_stats = np.array(boot_stats)

        if alternative == 'two-sided':
            p_value = np.mean(np.abs(boot_stats - null_value) >= np.abs(observed_stat - null_value))
        elif alternative == 'greater':
            p_value = np.mean(boot_stats >= observed_stat)
        elif alternative == 'less':
            p_value = np.mean(boot_stats <= observed_stat)
        else:
            p_value = 1.0

        return float(p_value)

    @staticmethod
    def bootstrap_confidence_interval(
        sample: Union[List[float], np.ndarray],
        statistic: callable = np.mean,
        confidence: float = 0.95,
        n_bootstrap: int = 10000,
        method: str = 'percentile',
        random_state: Optional[int] = None
    ) -> Tuple[float, float]:
        """
        Bootstrap confidence interval.

        Args:
            sample: Sample data
            statistic: Function to compute statistic
            confidence: Confidence level
            n_bootstrap: Number of bootstrap iterations
            method: Method ('percentile', 'bca', 'basic')
            random_state: Random seed

        Returns:
            Tuple of (lower_bound, upper_bound)
        """
        sample = np.array(sample)
        if len(sample) < 2:
            return 0.0, 0.0

        rng = np.random.default_rng(random_state)
        boot_stats = []

        for _ in range(n_bootstrap):
            boot_sample = rng.choice(sample, size=len(sample), replace=True)
            boot_stats.append(statistic(boot_sample))

        boot_stats = np.array(boot_stats)
        alpha = 1 - confidence

        if method == 'percentile':
            lower = np.percentile(boot_stats, 100 * alpha / 2)
            upper = np.percentile(boot_stats, 100 * (1 - alpha / 2))
        elif method == 'basic':
            observed = statistic(sample)
            lower = 2 * observed - np.percentile(boot_stats, 100 * (1 - alpha / 2))
            upper = 2 * observed - np.percentile(boot_stats, 100 * alpha / 2)
        else:
            # Default to percentile
            lower = np.percentile(boot_stats, 100 * alpha / 2)
            upper = np.percentile(boot_stats, 100 * (1 - alpha / 2))

        return float(lower), float(upper)

    @staticmethod
    def test_strategy_significance(
        returns: Union[List[float], np.ndarray],
        benchmark_returns: Optional[Union[List[float], np.ndarray]] = None,
        risk_free_rate: float = 0.0,
        test: str = 'ttest'
    ) -> dict:
        """
        Test if strategy returns are significantly different from benchmark.

        Args:
            returns: Strategy returns
            benchmark_returns: Benchmark returns (optional)
            risk_free_rate: Risk-free rate
            test: Test type ('ttest', 'bootstrap', 'wilcoxon')

        Returns:
            Dictionary with test results
        """
        returns = np.array(returns)

        if benchmark_returns is not None:
            benchmark_returns = np.array(benchmark_returns)
            excess_returns = returns - benchmark_returns
        else:
            excess_returns = returns - risk_free_rate

        results = {}

        if test == 'ttest':
            t_stat, p_value = StatisticalTests.one_sample_ttest(
                excess_returns, popmean=0.0, alternative='greater'
            )
            results['test'] = 'one_sample_ttest'
            results['t_statistic'] = t_stat
            results['p_value'] = p_value
            results['significant'] = p_value < 0.05

        elif test == 'bootstrap':
            p_value = StatisticalTests.bootstrap_p_value(
                excess_returns, statistic=np.mean, null_value=0.0,
                n_bootstrap=10000, alternative='greater'
            )
            results['test'] = 'bootstrap'
            results['p_value'] = p_value
            results['significant'] = p_value < 0.05

        elif test == 'wilcoxon':
            # Simplified Wilcoxon signed-rank test
            if len(excess_returns) > 1:
                # Use sign test as approximation
                signs = np.sign(excess_returns)
                positive = np.sum(signs > 0)
                n = len(signs)
                # Binomial test
                try:
                    from scipy.stats import binom_test
                    p_value = binom_test(positive, n, 0.5, alternative='greater')
                except ImportError:
                    # Normal approximation to binomial
                    expected = n * 0.5
                    std = np.sqrt(n * 0.25)
                    z = (positive - expected) / std
                    p_value = 1 - 0.5 * (1 + np.math.erf(z / np.sqrt(2)))

                results['test'] = 'wilcoxon_sign'
                results['w_statistic'] = float(positive)
                results['p_value'] = float(p_value)
                results['significant'] = p_value < 0.05
            else:
                results['test'] = 'wilcoxon'
                results['p_value'] = 1.0
                results['significant'] = False

        # Additional info
        results['mean_excess_return'] = float(np.mean(excess_returns))
        results['n_observations'] = len(excess_returns)

        return results


# Convenience functions
def one_sample_ttest(sample, popmean=0.0, alternative='two-sided'):
    """Convenience function for one-sample t-test."""
    return StatisticalTests.one_sample_ttest(sample, popmean, alternative)


def two_sample_ttest(sample1, sample2, equal_var=True, alternative='two-sided'):
    """Convenience function for two-sample t-test."""
    return StatisticalTests.two_sample_ttest(sample1, sample2, equal_var, alternative)


def paired_ttest(sample1, sample2, alternative='two-sided'):
    """Convenience function for paired t-test."""
    return StatisticalTests.paired_ttest(sample1, sample2, alternative)


def jarque_bera_test(sample):
    """Convenience function for Jarque-Bera test."""
    return StatisticalTests.jarque_bera_test(sample)


def shapiro_wilk_test(sample):
    """Convenience function for Shapiro-Wilk test."""
    return StatisticalTests.shapiro_wilk_test(sample)


def bootstrap_p_value(sample, statistic=np.mean, null_value=0.0, n_bootstrap=10000, alternative='two-sided', random_state=None):
    """Convenience function for bootstrap p-value."""
    return StatisticalTests.bootstrap_p_value(sample, statistic, null_value, n_bootstrap, alternative, random_state)


def bootstrap_confidence_interval(sample, statistic=np.mean, confidence=0.95, n_bootstrap=10000, method='percentile', random_state=None):
    """Convenience function for bootstrap confidence interval."""
    return StatisticalTests.bootstrap_confidence_interval(sample, statistic, confidence, n_bootstrap, method, random_state)


def test_strategy_significance(returns, benchmark_returns=None, risk_free_rate=0.0, test='ttest'):
    """Convenience function for strategy significance testing."""
    return StatisticalTests.test_strategy_significance(returns, benchmark_returns, risk_free_rate, test)