from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class Signal:
    index: int
    action: str
    price: float


class SimpleMovingAverageStrategy:
    def __init__(self, short_window: int = 3, long_window: int = 5):
        self.short_window = short_window
        self.long_window = long_window

    def generate_signals(self, prices: List[float]) -> List[Signal]:
        if not prices:
            return []

        signals: List[Signal] = []
        for index in range(len(prices)):
            if index < max(self.short_window, self.long_window):
                continue

            short_avg = sum(prices[index - self.short_window + 1:index + 1]) / self.short_window
            long_avg = sum(prices[index - self.long_window + 1:index + 1]) / self.long_window

            if short_avg > long_avg:
                signals.append(Signal(index=index, action="buy", price=prices[index]))
            else:
                signals.append(Signal(index=index, action="hold", price=prices[index]))

        return signals


class TradingSimulator:
    def __init__(self, initial_cash: float = 1000.0):
        self.initial_cash = initial_cash

    def run(self, prices: List[float], strategy: SimpleMovingAverageStrategy) -> Dict[str, Any]:
        signals = strategy.generate_signals(prices)
        cash = self.initial_cash
        shares = 0
        trades = []

        for signal in signals:
            if signal.action == "buy" and cash > 0:
                shares = max(shares, 1)
                cash -= signal.price
                trades.append({"index": signal.index, "action": "buy", "price": signal.price})

        final_value = cash + shares * prices[-1]
        return {"final_value": final_value, "trades": trades}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a simple moving-average trading demo")
    parser.add_argument("--prices", required=True, help="Comma-separated price series")
    args = parser.parse_args()

    prices = [float(value.strip()) for value in args.prices.split(",") if value.strip()]
    strategy = SimpleMovingAverageStrategy(short_window=2, long_window=3)
    simulator = TradingSimulator(initial_cash=1000.0)
    report = simulator.run(prices, strategy)

    print("Signals:")
    for signal in strategy.generate_signals(prices):
        print(f"  index={signal.index} action={signal.action} price={signal.price}")

    print(f"Final portfolio value: {report['final_value']:.2f}")
    print(f"Trades executed: {len(report['trades'])}")
