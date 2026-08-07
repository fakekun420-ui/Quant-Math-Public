"""
Statistical Tests Module

Statistical significance testing for trading strategy validation.
"""

import numpy as np
from scipy import stats
from typing import List, Optional, Tuple, Union


class StatisticalTests:
    """
    Collection of statistical tests for strategy validation.
    """

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

        t_stat, p_value = stats.ttest_1samp(sample, popmean, alternative=alternative)
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

        t_stat, p_value = stats.ttest_ind(sample1, sample2, equal_var=equal_var, alternative=alternative)
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

        t_stat, p_value = stats.ttest_rel(sample1, sample2, alternative=alternative)
        return float(t_stat), float(p_value)

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
        if len(sample) < 2:
            return 0.0, 1.0

        jb_stat, p_value = stats.jarque_bera(sample)
        return float(jb_stat), float(p_value)

    @staticmethod
    def shapiro_wilk_test(
        sample: Union[List[float], np.ndarray]
    ) -> Tuple[float, float]:
        """
        Shapiro-Wilk test for normality.

        Args:
            sample: Sample data (max 5000 observations)

        Returns:
            Tuple of (W statistic, p-value)
        """
        sample = np.array(sample)
        if len(sample) < 3 or len(sample) > 5000:
            return 0.0, 1.0

        w_stat, p_value = stats.shapiro(sample)
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
            # Wilcoxon signed-rank test
            if len(excess_returns) > 1:
                w_stat, p_value = stats.wilcoxon(excess_returns, alternative='greater')
                results['test'] = 'wilcoxon'
                results['w_statistic'] = float(w_stat)
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