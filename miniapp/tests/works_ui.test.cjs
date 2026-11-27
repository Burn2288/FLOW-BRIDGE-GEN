const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

test('a late library response does not replace a newer page', async () => {
  const elements = new Map();
  function element(selector) {
    if (!elements.has(selector)) elements.set(selector, {
      hidden: false, disabled: false, dataset: {}, children: [], textContent: '',
      replaceChildren(...children) { this.children = children; },
      append(...children) { this.children.push(...children); },
      setAttribute() {}, removeAttribute() {},
    });
    return elements.get(selector);
  }
  let resolveOld;
  const old = new Promise(resolve => { resolveOld = resolve; });
  const response = data => ({ok: true, json: async () => data});
  const document = {
    querySelector: element, querySelectorAll: () => [], getElementById: element,
    createElement: () => ({children: [], textContent: '', append(...items) { this.children.push(...items); }}),
  };
  const context = vm.createContext({window: {}, document, history: {},
    fetch: url => url.endsWith('page=0') ? old : Promise.resolve(response({works: [
      {kind: 'image', model: 'new-page', status: 'succeeded', price: null, available: false},
    ]}))});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../frontend/app.js'), 'utf8'), context);
  const first = vm.runInContext('showWorks(0)', context);
  await vm.runInContext('showWorks(1)', context);
  resolveOld(response({works: [{kind: 'image', model: 'old-page', status: 'succeeded', price: null, available: false}]}));
  await first;
  assert.match(element('#works').children[0].textContent, /new-page/);
  assert.equal(element('#previous').disabled, false);
});
