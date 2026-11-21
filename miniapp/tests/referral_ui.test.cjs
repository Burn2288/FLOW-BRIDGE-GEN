const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {webcrypto} = require('node:crypto');

function deferred() {
  let resolve;
  const promise = new Promise(done => { resolve = done; });
  return {promise, resolve};
}

function response(data, status = 200) {
  return {ok: status >= 200 && status < 300, status, json: async () => data};
}

async function until(predicate) {
  for (let i = 0; i < 100; i++) {
    if (predicate()) return;
    await new Promise(resolve => setImmediate(resolve));
  }
  assert.fail('condition was not reached');
}

test('referral tab selected during delayed login loads once, reports failure, retries and renders owner data', async () => {
  const elements = new Map();
  function element(selector) {
    if (!elements.has(selector)) elements.set(selector, {
      hidden: false, disabled: false, dataset: {}, children: [], textContent: '',
      replaceChildren(...children) { this.children = children; },
      append(...children) { this.children.push(...children); },
      setAttribute(name, value) { this[name] = value; },
      removeAttribute(name) { delete this[name]; },
    });
    return elements.get(selector);
  }
  const panels = ['catalogue', 'library', 'balance', 'settings', 'referral'];
  for (const panel of panels) element(panel).hidden = panel !== 'catalogue';
  const tabs = panels.map(panel => Object.assign(element(`tab:${panel}`), {dataset: {panel}}));
  const document = {
    querySelector: element,
    querySelectorAll: selector => selector === 'nav [data-panel]' ? tabs : [],
    getElementById: element,
    createElement: () => element(`created:${elements.size}`),
  };
  const session = deferred();
  const firstReferral = deferred();
  let referralCalls = 0;
  let sessionCalls = 0;
  async function fetch(url) {
    if (url === '/api/v1/session') { sessionCalls++; return session.promise; }
    if (url === '/api/v1/referral') {
      referralCalls++;
      return referralCalls === 1 ? firstReferral.promise
        : response({code: 'AAAAAAAAAAAAAAAA', has_referrer: true});
    }
    if (url === '/api/v1/wallet') return response({available: '0', reserved: '0'});
    if (url === '/api/v1/catalogue') return response({models: [], availability: {}});
    if (url === '/api/v1/settings') return response({theme: 'dark'});
    if (url === '/api/v1/works?page=0') return response({works: []});
    assert.fail(`unexpected request ${url}`);
  }
  const telegram = {initData: 'signed-fixture', ready() {}};
  const context = {
    window: {Telegram: {WebApp: telegram}}, document, fetch,
    crypto: webcrypto, TextEncoder, Promise, setImmediate,
    history: {state: {}, replaceState(state) { this.state = state; }},
    sessionStorage: {getItem: () => null, setItem() {}},
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../frontend/app.js'), 'utf8'), context);

  await until(() => sessionCalls === 1);
  tabs.find(tab => tab.dataset.panel === 'referral').onclick();
  assert.equal(element('referral').hidden, false);
  assert.equal(referralCalls, 0, 'referral data must not be requested before auth resolves');

  session.resolve(response({token: 'owner-session'}));
  await until(() => referralCalls === 1);
  tabs.find(tab => tab.dataset.panel === 'balance').onclick();
  tabs.find(tab => tab.dataset.panel === 'referral').onclick();
  tabs.find(tab => tab.dataset.panel === 'referral').onclick();
  assert.equal(referralCalls, 1, 'concurrent tab activation must share one request');

  firstReferral.resolve(response({error: 'temporary'}, 503));
  await until(() => element('#retry-referral').hidden === false);
  assert.match(element('#referral-status').textContent, /Не удалось загрузить приглашения/);
  assert.equal(element('#copy-referral').disabled, true);

  element('#retry-referral').onclick();
  await until(() => element('#referral-code').textContent === 'AAAAAAAAAAAAAAAA');
  assert.equal(referralCalls, 2);
  assert.equal(element('#referrer-status').textContent, 'Вы зарегистрировались по приглашению.');
  assert.equal(element('#copy-referral').disabled, false);
  assert.equal(element('#retry-referral').hidden, true);
});
