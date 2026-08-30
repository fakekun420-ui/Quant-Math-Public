#!/usr/bin/env python3
"""
Module 8: Risk Management - Comprehensive Examples

This module demonstrates all risk management capabilities including:
- Value at Risk (VaR) calculations (parametric, historical, Monte Carlo)
- Expected Shortfall (ES) calculations
- Portfolio risk metrics (diversification, concentration)
- Risk budgeting and allocation
- Stress testing
- Tail risk measures
"""

import numpy as np
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quant_math.risk import (
    ValueAtRisk, ExpectedShortfall, PortfolioRisk, RiskBudget, StressTesting
)


def example_var_calculation():
    """Example: Value at Risk calculation."""
    print("\n" + "="*70)
    print("Module 8.1: Value at Risk (VaR)")
    print("="*70)
    
    # Generate synthetic market data
    np.random.seed(42)
    n = 1000
    
    # Generate returns with fat tails (Student's t)
    df = 3.0
    returns = np.random.standard_t(df, n)
    
    print(f"\nGenerated {n} returns with Student's t distribution (df={df})")
    print(f"Mean: {np.mean(returns):.4f}, Std: {np.std(returns):.4f}")
    
    # Calculate VaR at different confidence levels
    print("\n--- VaR Calculations at 95% Confidence ---")
    var = ValueAtRisk(confidence_level=0.95)
    
    # Parametric normal
    normal_var = var.parametric_normal(returns)
    print(f"Parametric (Normal): ${normal_var:.4f}")
    
    # Parametric Student's t
    t_var = var.parametric_student_t(returns, df=df)
    print(f"Parametric (Student's t): ${t_var:.4f}")
    
    # Historical
    historical_var = var.historical(returns)
    print(f"Historical: ${historical_var:.4f}")
    
    # Calculate both VaR and ES
    print("\n--- VaR and Expected Shortfall at 95% ---")
    var_es = ValueAtRisk(confidence_level=0.95)
    var_result = var_es.conditional_tail_expectation(returns)
    print(f"VaR: ${var_result.value_at_risk:.4f}")
    print(f"Expected Shortfall: ${var_result.tail_loss:.4f}")
    
    # Compare across confidence levels
    print("\n--- VaR at Different Confidence Levels ---")
    for conf in [0.90, 0.95, 0.99]:
        var = ValueAtRisk(confidence_level=conf)
        print(f"  {conf*100:.0f}% CI: ${var.parametric_normal(returns):.4f}")


def example_expected_shortfall():
    """Example: Expected Shortfall calculation."""
    print("\n" + "="*70)
    print("Module 8.2: Expected Shortfall (ES)")
    print("="*70)
    
    np.random.seed(42)
    n = 1000
    df = 3.0
    returns = np.random.standard_t(df, n)
    
    print(f"\nGenerated {n} returns with Student's t distribution (df={df})")
    
    # Calculate ES at different confidence levels
    print("\n--- Expected Shortfall Calculations ---")
    es = ExpectedShortfall(confidence_level=0.95)
    
    # Historical ES
    historical_es = es.historical(returns)
    print(f"Historical ES: ${historical_es:.4f}")
    
    # Parametric normal ES
    parametric_es = es.parametric_normal(returns)
    print(f"Parametric (Normal) ES: ${parametric_es:.4f}")
    
    # Calculate both VaR and ES together
    print("\n--- VaR and ES Together ---")
    var, es_value = es.calculate_es_var(returns, confidence_level=0.95)
    print(f"VaR (95%): ${var:.4f}")
    print(f"Expected Shortfall (95%): ${es_value:.4f}")
    
    # ES at different confidence levels
    print("\n--- Expected Shortfall at Different Confidence Levels ---")
    for conf in [0.90, 0.95, 0.99]:
        es = ExpectedShortfall(confidence_level=conf)
        es_value = es.historical(returns)
        print(f"  {conf*100:.0f}% CI ES: ${es_value:.4f}")


def example_portfolio_risk():
    """Example: Portfolio risk analysis."""
    print("\n" + "="*70)
    print("Module 8.3: Portfolio Risk Analysis")
    print("="*70)
    
    # Generate portfolio data
    np.random.seed(42)
    n = 500
    
    # Three assets
    np.random.seed(42)
    returns = np.random.randn(n, 3)
    
    # Correlated returns (make them more realistic)
    correlations = np.array([
        [1.0, 0.5, 0.3],
        [0.5, 1.0, 0.4],
        [0.3, 0.4, 1.0]
    ])
    
    # Generate correlated returns
    for i in range(1, 3):
        for j in range(i):
            returns[:, i] += correlations[i, j] * returns[:, j]
            returns[:, i] /= np.sqrt(1 + correlations[i, j]**2)
    
    # Portfolio weights (60/40 split)
    weights = np.array([0.6, 0.3, 0.1])
    
    print(f"\nPortfolio: {weights}")
    print(f"Number of observations: {n}")
    print(f"Covariance matrix:\n{np.cov(returns, rowvar=False)}")
    
    # Initialize portfolio risk analyzer
    portfolio_risk = PortfolioRisk(returns, weights)
    
    # Calculate comprehensive risk metrics
    print("\n--- Portfolio Risk Metrics at 95% ---")
    result = portfolio_risk.calculate_risk_metrics(confidence_level=0.95)
    
    print(f"\nTotal Portfolio Risk:")
    print(f"  VaR (Parametric): ${result.total_var:.4f}")
    print(f"  Expected Shortfall: ${result.total_expected_shortfall:.4f}")
    
    print(f"\nComponent VaR:")
    for asset, var in result.component_var.items():
        print(f"  {asset}: ${var:.4f}")
    
    print(f"\nComponent ES:")
    for asset, es in result.component_es.items():
        print(f"  {asset}: ${es:.4f}")
    
    # Diversification benefit
    print(f"\nDiversification Benefit:")
    for conf, benefit in result.diversification_benefit.items():
        print(f"  {conf*100:.0f}% CI: ${benefit:.4f}")
    
    # Concentration risk
    print(f"\nConcentration Risk (HHI):")
    print(f"  HHI: {result.concentration_risk['hhi']:.2f}")
    print(f"  Interpretation: {'High' if result.concentration_risk['hhi'] > 2500 else 'Low'}")
    
    # Correlation analysis
    print(f"\nAsset Correlations:")
    for i in range(result.correlations.shape[0]):
        for j in range(result.correlations.shape[1]):
            print(f"  Asset {i} vs Asset {j}: {result.correlations[i, j]:.3f}")


def example_risk_budgeting():
    """Example: Risk budgeting and allocation."""
    print("\n" + "="*70)
    print("Module 8.4: Risk Budgeting")
    print("="*70)
    
    # Generate asset data
    np.random.seed(42)
    n = 500
    
    # Three assets with different volatilities
    np.random.seed(42)
    returns = np.random.randn(n, 3)
    volatilities = np.array([0.2, 0.3, 0.15])
    returns = returns * volatilities
    
    # Equal risk budgeting
    print("\n--- Equal Risk Budgeting ---")
    risk_budget = RiskBudget(target_var=0.05, confidence_level=0.95)
    equal_weights = risk_budget.equal_risk_budget(returns)
    
    print(f"Equal risk allocation weights: {equal_weights}")
    
    # Marginal contributions
    print("\n--- Marginal Contributions to VaR ---")
    mcr = risk_budget.marginal_contributions(returns, equal_weights)
    for asset, contribution in mcr.items():
        print(f"  {asset}: ${contribution:.4f}")
    
    # Optimal allocation
    print("\n--- Optimal Risk Allocation ---")
    optimal_weights = risk_budget.optimal_allocation(returns, target_sharpe=1.5)
    
    print(f"Optimal risk allocation weights: {optimal_weights}")
    print(f"Mean return: {np.mean(returns @ optimal_weights):.4f}")
    print(f"Volatility: {np.std(returns @ optimal_weights):.4f}")
    
    # Risk contribution verification
    print("\n--- Risk Contribution Verification ---")
    portfolio_risk = PortfolioRisk(returns, optimal_weights)
    result = portfolio_risk.calculate_risk_metrics()
    component_var = result.component_var
    
    print(f"Component VaR:")
    total_var = sum(component_var.values())
    for asset, var in component_var.items():
        pct = (var / total_var) * 100
        print(f"  {asset}: ${var:.4f} ({pct:.1f}%)")
    
    print(f"\nTotal VaR: ${total_var:.4f}")


def example_stress_testing():
    """Example: Stress testing and scenario analysis."""
    print("\n" + "="*70)
    print("Module 8.5: Stress Testing")
    print("="*70)
    
    # Generate returns
    np.random.seed(42)
    n = 1000
    returns = np.random.normal(0, 0.02, n)
    
    print(f"\nGenerated {n} daily returns with mean=0, std=0.02")
    
    # Initialize stress tester
    stress_tester = StressTesting(returns)
    
    # Historical scenarios
    print("\n--- Historical Scenarios (Bootstrap) ---")
    n_scenarios = 100
    scenarios = stress_tester.historical_scenarios(n_scenarios)
    
    scenario_losses = np.abs(scenarios)
    print(f"Generated {n_scenarios} scenarios")
    print(f"Loss statistics:")
    print(f"  Mean: ${np.mean(scenario_losses):.4f}")
    print(f"  Std: ${np.std(scenario_losses):.4f}")
    print(f"  Max: ${np.max(scenario_losses):.4f}")
    
    # Industry standard scenarios
    print("\n--- Industry Standard Stress Scenarios ---")
    stressed_scenarios = stress_tester.industry_scenarios(multiplier=1.5)
    
    stress_names = ['Normal Market', 'Bear Market', 'Mild Recession', 'Severe Recession', 'Crash', 'Financial Crisis']
    
    for i, (name, scenario) in enumerate(zip(stress_names, stressed_scenarios)):
        print(f"  {name}: ${scenario:.4f}")
    
    # Monte Carlo stress test
    print("\n--- Monte Carlo Stress Test ---")
    mc_results = stress_tester.monte_carlo_stress_test(
        n_scenarios=1000,
        confidence_level=0.95
    )
    
    print(f"Number of scenarios: {mc_results['n_scenarios']}")
    print(f"Value at Risk (95%): ${mc_results['var']:.4f}")
    print(f"Expected Shortfall: ${mc_results['expected_shortfall']:.4f}")
    print(f"Extreme loss percentiles:")
    for percentile, value in mc_results['extreme_loss_percentiles'].items():
        print(f"  {percentile}: ${value:.4f}")
    
    # Backtest risk limits
    print("\n--- Risk Limit Backtesting ---")
    
    # Simulate portfolio returns
    portfolio_returns = returns + 0.0005  # Add small drift
    
    var_threshold = 0.03  # 3% daily VaR limit
    backtest_results = stress_tester.backtest_risk_limits(
        portfolio_returns,
        var_threshold=var_threshold,
        confidence_level=0.95
    )
    
    print(f"Risk Limit: ${var_threshold:.4f}")
    print(f"Actual VaR: ${backtest_results['actual_var']:.4f}")
    print(f"Within limits: {backtest_results['is_within_limits']}")
    print(f"Number of exceedances: {backtest_results['n_exceedances']} / {backtest_results['expected_exceedances']:.1f}")
    print(f"Exceedance ratio: {backtest_results['exceedance_ratio']:.2%}")


def main():
    """Run all examples."""
    print("\n" + "="*70)
    print("QUANT-MATH MODULE 8: Risk Management")
    print("="*70)
    
    try:
        example_var_calculation()
        example_expected_shortfall()
        example_portfolio_risk()
        example_risk_budgeting()
        example_stress_testing()
        
        print("\n" + "="*70)
        print("All Module 8 examples completed successfully!")
        print("="*70 + "\n")
        
    except Exception as e:
        print(f"\nError running examples: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
