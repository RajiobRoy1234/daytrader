import test from 'node:test';
import assert from 'node:assert/strict';
import { getSectorSnapshots } from '../src/sectorData.js';

test('builds the sector snapshot list from the provided market data', () => {
  const sectors = getSectorSnapshots();

  assert.equal(sectors.length, 11);

  const technology = sectors.find((sector) => sector.symbol === 'SIXT');
  assert.ok(technology);
  assert.equal(technology.name, 'Technology');
  assert.equal(technology.price, 3445.26);
  assert.equal(technology.change, -292.00);
  assert.equal(technology.changePercent, -7.81);
  assert.ok(technology.stocks.includes('AAPL'));
  assert.ok(technology.stocks.includes('MSFT'));
});

test('includes a broad market benchmark and a representative stock list for each sector', () => {
  const sectors = getSectorSnapshots();
  const spy = sectors.find((sector) => sector.symbol === 'SPY');
  assert.ok(spy);
  assert.ok(spy.stocks.includes('SPY'));

  for (const sector of sectors) {
    assert.ok(Array.isArray(sector.stocks));
    assert.ok(sector.stocks.length >= 4);
  }
});
