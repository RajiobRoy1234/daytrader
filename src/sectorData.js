const sectorDefinitions = [
  {
    name: 'Technology',
    symbol: 'SIXT',
    price: 3445.26,
    change: -292.0,
    changePercent: -7.81,
    stocks: ['AAPL', 'MSFT', 'NVDA', 'AMD', 'INTC', 'CRM']
  },
  {
    name: 'Financials',
    symbol: 'SIXM',
    price: 709.77,
    change: 46.87,
    changePercent: 7.07,
    stocks: ['JPM', 'BAC', 'GS', 'MS', 'C', 'WFC']
  },
  {
    name: 'Communication Services',
    symbol: 'SIXC',
    price: 572.76,
    change: 7.86,
    changePercent: 1.39,
    stocks: ['XOM', 'CVX', 'COP', 'SLB', 'OXY', 'KOS']
  },
  {
    name: 'Health Care',
    symbol: 'SIXV',
    price: 1689.05,
    change: 61.97,
    changePercent: 3.81,
    stocks: ['JNJ', 'PFE', 'LLY', 'MRK', 'UNH', 'ABBV']
  },
  {
    name: 'Materials',
    symbol: 'SIXB',
    price: 1111.63,
    change: 34.52,
    changePercent: 3.2,
    stocks: ['LIN', 'FCX', 'NEM', 'PPG', 'APD', 'DOW']
  },
  {
    name: 'Consumer Discretionary',
    symbol: 'SIXY',
    price: 2273.8,
    change: -94.51,
    changePercent: -3.99,
    stocks: ['AMZN', 'TSLA', 'HD', 'MCD', 'NKE', 'SBUX']
  },
  {
    name: 'Real Estate',
    symbol: 'SIXRE',
    price: 225.96,
    change: 4.81,
    changePercent: 2.17,
    stocks: ['PLD', 'AMT', 'EQIX', 'O', 'SPG', 'DLR']
  },
  {
    name: 'Consumer Staples',
    symbol: 'SIXR',
    price: 879.27,
    change: 25.04,
    changePercent: 2.93,
    stocks: ['PG', 'KO', 'PEP', 'COST', 'WMT', 'CL']
  },
  {
    name: 'Utilities',
    symbol: 'SIXU',
    price: 921.46,
    change: -10.97,
    changePercent: -1.18,
    stocks: ['NEE', 'DUK', 'SO', 'D', 'EXC', 'PEG']
  },
  {
    name: 'Energy',
    symbol: 'SIXE',
    price: 1211.3,
    change: 82.79,
    changePercent: 7.34,
    stocks: ['XOM', 'CVX', 'COP', 'EOG', 'SLB', 'KMI']
  },
  {
    name: 'Industrials',
    symbol: 'SIXI',
    price: 1839.8,
    change: -4.62,
    changePercent: -0.25,
    stocks: ['CAT', 'GE', 'MMM', 'BA', 'UNP', 'RTX']
  }
];

const benchmarkSector = {
  name: 'S&P 500',
  symbol: 'SPY',
  price: 740.86,
  change: -0.14,
  changePercent: -0.02,
  stocks: ['SPY', 'IVV', 'VOO']
};

export function getSectorSnapshots() {
  return [benchmarkSector, ...sectorDefinitions];
}
