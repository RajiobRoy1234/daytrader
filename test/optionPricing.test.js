import test from 'node:test';
import assert from 'node:assert/strict';
import { blackScholesOption } from '../src/optionPricing.js';

test('computes a realistic call premium and Greeks', () => {
  const result = blackScholesOption({
    spot: 100,
    strike: 100,
    rate: 5,
    volatility: 20,
    daysToExpiry: 365,
    optionType: 'call'
  });

  assert.ok(result.premium > 0);
  assert.ok(result.delta > 0);
  assert.ok(result.gamma > 0);
  assert.ok(result.vega > 0);
  assert.ok(result.rho > 0);
  assert.ok(result.theta < 0);
});

test('computes a put premium with the expected sign profile', () => {
  const result = blackScholesOption({
    spot: 100,
    strike: 110,
    rate: 2,
    volatility: 25,
    daysToExpiry: 180,
    optionType: 'put'
  });

  assert.ok(result.premium > 0);
  assert.ok(result.delta < 0);
  assert.ok(result.gamma > 0);
  assert.ok(result.rho < 0);
});
