const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

test('closing either Stars invoice refreshes the wallet and payment history from HTTP', async () => {
  const elements = new Map();
  function element(selector) {
    if (!elements.has(selector)) elements.set(selector, {
      replaceChildren(...children) { this.children = children; },
    });
    return elements.get(selector);
  }
  const document = {querySelector: element, querySelectorAll: () => [], createElement: () => ({})};
  const invoices = [];
  const reads = [];
  let paid = false;
  let close;
  const telegram = {
    ready() {}, isVersionAtLeast: () => true,
    openInvoice(url, callback) {
      assert.equal(url, 'https://t.me/$' + invoices.length);
      close = callback;
    },
  };
  async function fetch(url, options) {
    let data;
    if (url === '/api/v1/stars/invoices') {
      assert.equal(options.method, 'POST');
      invoices.push({id: String(invoices.length + 1), created_at: '2026-01-01', amount: 100, currency: 'XTR'});
      data = {url: 'https://t.me/$' + invoices.length};
    } else if (url === '/api/v1/wallet') {
      reads.push('wallet');
      data = {available: paid ? '10000' : '0', reserved: '0'};
    } else {
      assert.equal(url, '/api/v1/stars/payments?page=0');
      reads.push('history');
      data = {checkout_enabled: true, payments: invoices.map(p => ({
        ...p, status: paid && p.id === '2' ? 'succeeded' : 'pending',
      }))};
    }
    return {ok: true, json: async () => data};
  }
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../frontend/app.js'), 'utf8'),
    {window: {Telegram: {WebApp: telegram}}, document, fetch});
  for (const outcome of ['cancelled', 'paid']) {
    await element('#buy-stars').onclick();
    assert.equal(element('#buy-stars').disabled, true);
    await close(outcome);
    assert.deepEqual(reads.splice(0), ['wallet', 'history']);
    assert.equal(element('#available').textContent, '0');
    assert.equal(element('#buy-stars').disabled, false);
    assert.ok(element('#stars-history').children.every(p => p.textContent.includes('Ожидает оплаты')));
  }
  paid = true;
  await element('#stars-refresh').onclick();
  assert.equal(element('#available').textContent, '10000');
  assert.ok(element('#stars-history').children[1].textContent.includes('Оплачен'));
});
