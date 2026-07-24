import { blackScholesOption } from './src/optionPricing.js';

const form = document.querySelector('#option-form');
const premiumValue = document.querySelector('#premiumValue');
const deltaValue = document.querySelector('#deltaValue');
const gammaValue = document.querySelector('#gammaValue');
const thetaValue = document.querySelector('#thetaValue');
const vegaValue = document.querySelector('#vegaValue');
const rhoValue = document.querySelector('#rhoValue');

function formatCurrency(value) {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 2
  }).format(value);
}

function formatPercent(value) {
  return `${value.toFixed(4)}%`;
}

function renderResults(result) {
  premiumValue.textContent = formatCurrency(result.premium);
  deltaValue.textContent = result.delta.toFixed(4);
  gammaValue.textContent = result.gamma.toFixed(4);
  thetaValue.textContent = `${result.theta.toFixed(4)} per day`;
  vegaValue.textContent = result.vega.toFixed(2);
  rhoValue.textContent = result.rho.toFixed(4);
}

form.addEventListener('submit', (event) => {
  event.preventDefault();

  const data = new FormData(form);
  const result = blackScholesOption({
    spot: data.get('spot') || document.querySelector('#spot').value,
    strike: data.get('strike') || document.querySelector('#strike').value,
    rate: data.get('rate') || document.querySelector('#rate').value,
    volatility: data.get('volatility') || document.querySelector('#volatility').value,
    daysToExpiry: data.get('days') || document.querySelector('#days').value,
    optionType: data.get('optionType') || document.querySelector('#optionType').value
  });

  renderResults(result);
});

const defaultResult = blackScholesOption({
  spot: 100,
  strike: 100,
  rate: 5,
  volatility: 20,
  daysToExpiry: 365,
  optionType: 'call'
});
renderResults(defaultResult);
