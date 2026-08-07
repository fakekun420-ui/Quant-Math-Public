"""
CLI interface for AQDE.

Provides command-line interface for hypothesis discovery and validation.
"""

import click
from typing import List, Optional
from datetime import datetime
import json

from ..adapters import QuantMathAdapter


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """Autonomous Quant Discovery Engine CLI"""
    pass


@cli.command()
@click.option('--symbol', required=True, help='Trading symbol (e.g., BTCUSDT)')
@click.option('--start-date', required=True, help='Start date (YYYY-MM-DD)')
@click.option('--end-date', required=True, help='End date (YYYY-MM-DD)')
@click.option('--initial-capital', default=100000.0, help='Initial capital for backtest')
@click.option('--output', default='backtest_results.json', help='Output file for results')
def backtest(symbol: str, start_date: str, end_date: str, initial_capital: float, output: str):
    """Run backtest on a hypothesis"""
    adapter = QuantMathAdapter()

    try:
        # Parse dates
        start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))

        # Fetch market data
        click.echo(f"Fetching market data for {symbol}...")
        data = adapter.fetch_market_data(symbol, start_dt, end_dt)

        # Run backtest (placeholder - would use actual hypothesis in full implementation)
        click.echo("Running backtest...")
        result = adapter.run_backtest(
            hypothesis={"hypothesis_id": "demo_hypothesis"},
            data=data,
            initial_capital=initial_capital
        )

        # Save results — serialize BacktestResult dataclass to dict
        results_dict = {
            "initial_capital": result.initial_capital,
            "final_capital": result.final_capital,
            "total_return": result.total_return,
            "total_return_pct": result.total_return_pct,
            "sharpe_ratio": result.sharpe_ratio,
            "sortino_ratio": result.sortino_ratio,
            "max_drawdown": result.max_drawdown,
            "annualized_volatility": result.annualized_volatility,
            "num_trades": result.num_trades,
            "win_rate": result.win_rate,
            "avg_win": result.avg_win,
            "avg_loss": result.avg_loss,
            "profit_factor": result.profit_factor,
        }
        with open(output, 'w') as f:
            json.dump({
                "symbol": symbol,
                "start_date": start_dt.isoformat(),
                "end_date": end_dt.isoformat(),
                "initial_capital": initial_capital,
                "results": results_dict
            }, f, indent=2)

        click.echo(f"Backtest complete. Results saved to {output}")
        click.echo(f"  Total Trades: {result.num_trades}")
        click.echo(f"  Win Rate: {result.win_rate:.2f}%")
        click.echo(f"  Net Profit: ${result.total_return:,.2f}")
        click.echo(f"  Total Return: {result.total_return_pct:.2f}%")
        click.echo(f"  Sharpe Ratio: {result.sharpe_ratio:.4f}")
        click.echo(f"  Sortino Ratio: {result.sortino_ratio:.4f}")
        click.echo(f"  Max Drawdown: {result.max_drawdown:.2f}%")
        click.echo(f"  Profit Factor: {result.profit_factor:.2f}")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@cli.command()
@click.option('--strategy-type', default='all', help='Filter by strategy type')
@click.option('--max-results', default=100, help='Maximum results to return')
def search(strategy_type: str, max_results: int):
    """Search for hypotheses in knowledge base"""
    adapter = QuantMathAdapter()

    try:
        criteria = {"strategy_type": strategy_type} if strategy_type != 'all' else {}

        results = adapter.search_hypotheses(criteria)

        click.echo(f"Found {len(results)} hypotheses")
        click.echo("=" * 80)

        for i, result in enumerate(results[:max_results], 1):
            click.echo(f"\n{i}. {result.get('name', 'Unnamed')}")
            click.echo(f"   ID: {result.get('hypothesis_id', 'N/A')}")
            click.echo(f"   Type: {result.get('strategy_type', 'N/A')}")
            click.echo(f"   Description: {result.get('description', 'N/A')}")
            click.echo(f"   Status: {result.get('status', 'N/A')}")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@cli.command()
@click.option('--output', default='discover_results.json', help='Output file for results')
def discover(output: str):
    """Discover new hypotheses"""
    adapter = QuantMathAdapter()

    try:
        # Check knowledge base for similar hypotheses
        click.echo("Checking knowledge base for similar hypotheses...")
        results = adapter.search_hypotheses({})

        if results:
            click.echo(f"Found {len(results)} similar hypotheses")
        else:
            click.echo("No similar hypotheses found. Would generate new hypotheses.")

        # Save results
        with open(output, 'w') as f:
            json.dump({
                "found_similar": len(results) > 0,
                "count": len(results),
                "results": results
            }, f, indent=2)

        click.echo(f"Discovery complete. Results saved to {output}")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@cli.command()
@click.option('--knowledge-base-path', default='autonomous_research/data/hypotheses',
              help='Path to knowledge base directory')
def init_kb(knowledge_base_path: str):
    """Initialize knowledge base"""
    adapter = QuantMathAdapter(knowledge_base_path=knowledge_base_path)
    stats = adapter.get_statistics()

    click.echo(f"Knowledge base initialized")
    click.echo(f"  Location: {knowledge_base_path}")
    click.echo(f"  Total hypotheses: {stats.get('total', 0)}")
    click.echo(f"  Active hypotheses: {stats.get('active', 0)}")


@cli.command()
@click.option('--output', default='hypotheses_export.json', help='Output file for export')
def export(output: str):
    """Export all hypotheses to JSON file"""
    adapter = QuantMathAdapter()

    try:
        stats = adapter.get_statistics()
        hypotheses = stats.get('hypotheses', [])

        with open(output, 'w') as f:
            json.dump({
                "total": len(hypotheses),
                "hypotheses": hypotheses
            }, f, indent=2)

        click.echo(f"Exported {len(hypotheses)} hypotheses to {output}")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


if __name__ == "__main__":
    cli()
