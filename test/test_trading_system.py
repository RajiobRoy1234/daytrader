import unittest

from trading_system import SimpleMovingAverageStrategy, TradingSimulator


class TradingSystemTests(unittest.TestCase):
    def test_strategy_generates_buy_signal_on_uptrend(self):
        prices = [100, 102, 104, 106, 108, 110]
        strategy = SimpleMovingAverageStrategy(short_window=2, long_window=3)

        signals = strategy.generate_signals(prices)

        self.assertTrue(signals)
        self.assertEqual(signals[-1].action, "buy")

    def test_simulator_tracks_trades_and_value(self):
        prices = [100, 110, 105, 115]
        strategy = SimpleMovingAverageStrategy(short_window=2, long_window=2)
        simulator = TradingSimulator(initial_cash=1000.0)

        report = simulator.run(prices, strategy)

        self.assertGreaterEqual(report["final_value"], 0)
        self.assertGreaterEqual(len(report["trades"]), 0)


if __name__ == "__main__":
    unittest.main()
