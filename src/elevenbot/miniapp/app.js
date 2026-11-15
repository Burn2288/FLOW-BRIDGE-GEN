const telegram = window.Telegram?.WebApp;
const status = document.querySelector('#status');
const account = document.querySelector('#account');
const works = document.querySelector('#works');
let token;
let page = 0;

async function request(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { ...(options.headers ?? {}), ...(token ? { Authorization: 'Bearer ' + token } : {}) },
  });
  if (response.status === 401) throw Error('Откройте приложение заново из Telegram.');
  if (response.status === 403) throw Error('Откройте бот и проверьте доступ к аккаунту.');
  if (!response.ok) throw Error('Не удалось получить данные.');
  return response;
}

function listItem(text) {
  const item = document.createElement('li');
  item.textContent = text;
  return item;
}

function showError(error) {
  status.textContent = error.message;
}

async function download(work) {
  const response = await request('/api/v1/works/' + encodeURIComponent(work.kind) + '/' + work.id);
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement('a');
  link.href = url;
  link.download = response.headers.get('Content-Disposition')?.match(/filename="([^"]+)"/)?.[1] ?? 'darkflow';
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 30000);
}

async function showWorks(target) {
  const data = await (await request('/api/v1/works?page=' + target)).json();
  works.replaceChildren();
  for (const work of data.works) {
    const item = listItem(work.model ?? work.kind);
    if (work.available) {
      const button = document.createElement('button');
      button.textContent = 'Скачать';
      button.onclick = () => download(work).catch(showError);
      item.append(button);
    }
    works.append(item);
  }
  if (!data.works.length) works.append(listItem('Работ пока нет.'));
  page = target;
  document.querySelector('#previous').disabled = !page;
  document.querySelector('#next').disabled = data.works.length < 10;
}

async function start() {
  telegram?.ready();
  if (!telegram?.initData) throw Error('Откройте Mini App из личного чата с ботом.');
  const session = await request('/api/v1/session', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ initData: telegram.initData }),
  });
  token = (await session.json()).token;
  const [wallet, catalogue] = await Promise.all([
    request('/api/v1/wallet').then(response => response.json()),
    request('/api/v1/catalogue').then(response => response.json()),
    showWorks(0),
  ]);
  document.querySelector('#wallet').textContent =
    'Доступно: ' + wallet.available + ' · Зарезервировано: ' + wallet.reserved;
  const models = document.querySelector('#models');
  for (const model of catalogue.models) models.append(listItem(model.aggregator + ' · ' + model.title));
  for (const [name, available] of Object.entries(catalogue.availability)) {
    if (!available) models.append(listItem(name + ' · каталог временно недоступен'));
  }
  if (!models.children.length) models.append(listItem('Нет доступных моделей.'));
  status.textContent = '';
  account.hidden = false;
}

document.querySelector('#previous').onclick = () => showWorks(page - 1).catch(showError);
document.querySelector('#next').onclick = () => showWorks(page + 1).catch(showError);
start().catch(showError);
