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

from quant_math.risk import ValueAtRisk, ExpectedShortfall


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





def main():
    """Run all examples."""
    print("\n" + "="*70)
    print("QUANT-MATH MODULE 8: Risk Management")
    print("="*70)
    
    try:
        example_var_calculation()
        example_expected_shortfall()
        
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
