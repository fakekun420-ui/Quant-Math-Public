"""
QUANT-MATH Main Entry Point

Unified CLI entry point for the QUANT-MATH framework.
"""

import argparse
import sys


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="quant-math",
        description="QUANT-MATH Framework - Quantitative Mathematics for Algorithmic Trading"
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Test command
    test_parser = subparsers.add_parser("test", help="Run integration tests")
    test_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )

    # Info command
    info_parser = subparsers.add_parser("info", help="Show framework information")

    # Module commands
    modules_parser = subparsers.add_parser("modules", help="List available modules")

    args = parser.parse_args()

    if args.command == "test":
        return run_tests(args.verbose)
    elif args.command == "info":
        return show_info()
    elif args.command == "modules":
        return list_modules()
    else:
        parser.print_help()
        return 0


def run_tests(verbose: bool = False) -> int:
    """Run integration tests."""
    import subprocess

    test_file = "test_integration.py"
    cmd = [sys.executable, test_file]
    if verbose:
        cmd.append("-v")

    try:
        result = subprocess.run(cmd, cwd=".")
        return result.returncode
    except FileNotFoundError:
        print(f"Error: Test file {test_file} not found")
        return 1


def show_info() -> int:
    """Show framework information."""
    print("=" * 60)
    print("QUANT-MATH Framework")
    print("=" * 60)
    print("Version: 0.1.0")
    print("Description: Quantitative Mathematics for Algorithmic Trading")
    print("=" * 60)
    print("\nCore Modules:")
    modules = [
        "quant_math.expectation",
        "quant_math.risk",
        "quant_math.optimization",
        "quant_math.monte_carlo",
        "quant_math.portfolio_construction",
        "quant_math.pca_analysis",
        "quant_math.ml",
        "quant_math.spectral_analysis",
        "quant_math.regime_detection",
        "quant_math.signal_processing",
        "quant_math.data_processing",
        "quant_math.data_acquisition",
        "quant_math.order_management",
        "quant_math.execution",
        "quant_math.algo_trading",
        "quant_math.backtesting",
        "autonomous_research",
    ]
    for m in modules:
        print(f"  - {m}")
    print("\nCommands:")
    print("  quant-math test    Run integration tests")
    print("  quant-math info    Show this information")
    print("  quant-math modules List available modules")
    print("  aqde               Autonomous Quant Discovery Engine CLI")
    return 0


def list_modules() -> int:
    """List available modules with descriptions."""
    print("Available QUANT-MATH Modules:")
    print("-" * 60)
    modules = {
        "expectation": "Statistical tests and performance metrics",
        "risk": "Risk management (VaR, ES, Position Sizing, Kelly, PortfolioRisk)",
        "optimization": "Portfolio optimization and Kelly criterion",
        "monte_carlo": "Monte Carlo simulation engine",
        "portfolio_construction": "Portfolio building and optimization",
        "pca_analysis": "PCA decomposition, risk factors, covariance shrinkage",
        "ml": "Machine learning for quantitative finance",
        "spectral_analysis": "Spectral and frequency domain analysis",
        "regime_detection": "Market regime detection",
        "signal_processing": "Signal processing and filtering",
        "data_processing": "Data cleaning and preprocessing",
        "data_acquisition": "Market data fetching and storage",
        "order_management": "Order routing and management",
        "execution": "Trade execution algorithms",
        "algo_trading": "Algorithmic trading system",
        "backtesting": "Strategy backtesting framework",
        "autonomous_research": "AQDE - Autonomous hypothesis discovery",
    }
    for name, desc in modules.items():
        print(f"  {name:<25} {desc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())