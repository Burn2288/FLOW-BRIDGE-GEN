const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {webcrypto} = require('node:crypto');

const response = (data, status = 200) => ({ok: status >= 200 && status < 300, status, json: async () => data});
async function until(predicate) {
  for (let i = 0; i < 100; i++) {
    if (predicate()) return;
    await new Promise(resolve => setImmediate(resolve));
  }
  assert.fail('condition was not reached');
}

test('support remains usable when operations report fails, but disappears when access is denied', async () => {
  const elements = new Map();
  const element = selector => {
    if (!elements.has(selector)) elements.set(selector, {
      hidden: false, disabled: false, dataset: {}, children: [], textContent: '',
      replaceChildren(...children) { this.children = children; },
      append(...children) { this.children.push(...children); },
      setAttribute(name, value) { this[name] = value; },
      removeAttribute(name) { delete this[name]; },
    });
    return elements.get(selector);
  };
  const panels = ['catalogue', 'library', 'balance', 'settings', 'referral', 'administration'];
  const tabs = panels.map(panel => Object.assign(element(`tab:${panel}`), {dataset: {panel}}));
  const document = {querySelector: element, getElementById: element,
    querySelectorAll: selector => selector === 'nav [data-panel]' ? tabs : [],
    createElement: () => element(`created:${elements.size}`)};
  let reportStatus = 503;
  let catalogueRequested = false;
  async function fetch(url) {
    if (url === '/api/v1/session') return response({token: 'fixture'});
    if (url === '/api/v1/catalogue') { catalogueRequested = true; return response({models: [], availability: {}}); }
    if (url === '/api/v1/settings') return response({theme: 'dark'});
    if (url === '/api/v1/admin/capabilities') return response({role: 'OWNER_ADMIN', capabilities: ['operations.read', 'support.operate']});
    if (url === '/api/v1/admin/support') return response({tickets: []});
    if (url.startsWith('/api/v1/admin/operations?')) return response({}, reportStatus);
    assert.fail(`unexpected request ${url}`);
  }
  const context = {window: {Telegram: {WebApp: {initData: 'fixture', ready() {}}}}, document, fetch,
    crypto: webcrypto, TextEncoder, Promise, setImmediate, URLSearchParams,
    history: {state: {}, replaceState(state) { this.state = state; }},
    sessionStorage: {getItem: () => null, setItem() {}}};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../frontend/app.js'), 'utf8'), context);
  await until(() => catalogueRequested);
  tabs.find(tab => tab.dataset.panel === 'administration').onclick();
  await until(() => element('#admin-status').textContent.includes('Обзор недоступен'));
  assert.equal(element('#admin-report').children.length, 1, 'support form must remain on a reporting outage');
  reportStatus = 403;
  element('#admin-reload').onclick();
  await until(() => element('#admin-status').textContent.includes('проверьте доступ'));
  assert.equal(element('#admin-report').children.length, 0, 'access denial must clear privileged controls');
});
