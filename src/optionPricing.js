const PI = Math.PI;
const SQRT2PI = Math.sqrt(2 * PI);

function normalPDF(x) {
  return Math.exp(-0.5 * x * x) / SQRT2PI;
}

export function standardNormalCDF(x) {
  const t = 1 / (1 + 0.2316419 * Math.abs(x));
  const d = 0.3989423 * Math.exp(-0.5 * x * x) * t * (0.31938153 + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429))));
  if (x >= 0) {
    return 1 - d;
  }
  return d;
}

function getYearsToExpiry(daysToExpiry) {
  return daysToExpiry / 365;
}

export function blackScholesOption({ spot, strike, rate, volatility, daysToExpiry, optionType }) {
  const S = Number(spot);
  const K = Number(strike);
  const r = Number(rate) / 100;
  const sigma = Number(volatility) / 100;
  const T = getYearsToExpiry(Number(daysToExpiry));
  const type = (optionType || 'call').toLowerCase();

  if (!Number.isFinite(S) || !Number.isFinite(K) || !Number.isFinite(r) || !Number.isFinite(sigma) || !Number.isFinite(T) || T <= 0) {
    throw new Error('Please enter valid option inputs.');
  }

  const d1 = (Math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * Math.sqrt(T));
  const d2 = d1 - sigma * Math.sqrt(T);
  const discountFactor = Math.exp(-r * T);
  const callPrice = S * standardNormalCDF(d1) - K * discountFactor * standardNormalCDF(d2);
  const putPrice = K * discountFactor * standardNormalCDF(-d2) - S * standardNormalCDF(-d1);

  const premium = type === 'put' ? putPrice : callPrice;
  const pdfD1 = normalPDF(d1);
  const sqrtT = Math.sqrt(T);
  const gamma = pdfD1 / (S * sigma * sqrtT);
  const vega = S * pdfD1 * sqrtT;

  const callDelta = standardNormalCDF(d1);
  const putDelta = callDelta - 1;
  const delta = type === 'put' ? putDelta : callDelta;

  const callTheta = -(S * pdfD1 * sigma) / (2 * sqrtT) - r * K * discountFactor * standardNormalCDF(d2);
  const putTheta = -(S * pdfD1 * sigma) / (2 * sqrtT) + r * K * discountFactor * standardNormalCDF(-d2);
  const theta = type === 'put' ? putTheta / 365 : callTheta / 365;

  const callRho = K * T * discountFactor * standardNormalCDF(d2);
  const putRho = -K * T * discountFactor * standardNormalCDF(-d2);
  const rho = type === 'put' ? putRho : callRho;

  return {
    premium,
    delta,
    gamma,
    theta,
    vega,
    rho
  };
}
