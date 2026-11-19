const telegram = window.Telegram?.WebApp;
const status = document.querySelector('#status');
const themeStatus = document.querySelector('#theme-status');
const retryTheme = document.querySelector('#retry-theme');
const themeInputs = [...document.querySelectorAll('[name=theme]')];
let wantedTheme;
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
  if (!response.ok) throw Object.assign(Error('Не удалось получить данные.'), { status: response.status });
  return response;
}

function listItem(text) {
  const item = document.createElement('li');
  item.textContent = text;
  return item;
}

function showError(error) {
  status.dataset.error = 'true';
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
    const kinds = { image: 'Изображение', video: 'Видео', audio: 'Аудио', chat: 'Текст' };
    const states = { queued: 'В очереди', dispatching: 'Выполняется', succeeded: 'Готово',
      failed: 'Ошибка', cancelled: 'Отменено', uncertain: 'Требует проверки' };
    const label = kinds[work.kind] ?? work.kind;
    const state = states[work.status] ?? work.status;
    const item = listItem([label, work.model, state].filter(Boolean).join(' · '));
    const historyButton = document.createElement('button');
    historyButton.textContent = 'История';
    const details = document.createElement('ul');
    historyButton.onclick = async () => {
      try {
        const data = await (await request('/api/v1/works/' + encodeURIComponent(work.kind) + '/' + work.id + '/timeline')).json();
        details.replaceChildren(...data.events.map(event => listItem(event.label + (event.at ? ' · ' + event.at : ''))));
      } catch (error) { showError(error); }
    };
    item.append(historyButton, details);
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

function imageForm(model) {
  const form = document.querySelector('#image-form').content.firstElementChild.cloneNode(true);
  const prompt = form.elements.prompt;
  const calculate = form.querySelector('[type=submit]');
  const confirm = form.querySelector('[type=button]');
  const message = form.querySelector('[role=status]');
  let quote;
  let revision = 0;

  function invalidate() {
    revision++;
    quote = null;
    confirm.hidden = true;
    calculate.disabled = !prompt.value.trim();
    message.textContent = '';
  }
  prompt.oninput = invalidate;
  form.onsubmit = async event => {
    event.preventDefault();
    if (calculate.disabled || prompt.disabled) return;
    invalidate();
    const requested = revision;
    calculate.disabled = true;
    message.textContent = 'Рассчитываем стоимость…';
    try {
      const response = await request('/api/v1/quotes', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model, prompt: prompt.value }),
      });
      const result = await response.json();
      if (requested !== revision) return;
      quote = result;
      const priceLabel = quote.price.estimate ? 'Оценка' : 'Стоимость';
      message.textContent = `${priceLabel}: ${quote.price.total} токенов.`;
      confirm.textContent = `Подтвердить за ${quote.price.total} токенов`;
      confirm.hidden = false;
    } catch (error) {
      if (requested === revision) {
        message.textContent = error.message;
        calculate.disabled = false;
      }
    }
  };
  confirm.onclick = async () => {
    if (!quote || confirm.disabled) return;
    confirm.disabled = prompt.disabled = true;
    message.textContent = 'Отправляем задание…';
    try {
      await request('/api/v1/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Idempotency-Key': quote.quote_id },
        body: JSON.stringify({ quote_id: quote.quote_id }),
      });
      prompt.value = '';
      invalidate();
      message.textContent = 'Задание принято.';
    } catch (error) {
      if (error.status === 409) {
        invalidate();
        message.textContent = 'Рассчитайте стоимость заново.';
      } else {
        message.textContent = error.message;
      }
    } finally {
      confirm.disabled = prompt.disabled = false;
    }
  };
  return form;
}

async function start() {
  telegram?.ready();
  if (!telegram?.initData) {
    const hint = telegram?.sendData
      ? 'Для входа закройте окно, отправьте /miniapp и нажмите «Открыть каталог».'
      : 'Для входа отправьте /miniapp в личном чате с ботом и нажмите «Открыть каталог».';
    status.textContent = hint;
    return;
  }
  // initData is single-use. Resume only the session for this launch in this tab.
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(telegram.initData));
  const launch = Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('');
  const saved = JSON.parse(sessionStorage.getItem('miniapp.session'));
  if (saved?.launch === launch) token = saved.token;
  if (!token) {
    history.replaceState({ ...history.state, jobId: null }, '');
    const session = await request('/api/v1/session', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ initData: telegram.initData }),
    });
    token = (await session.json()).token;
    sessionStorage.setItem('miniapp.session', JSON.stringify({ launch, token }));
  }
  const [wallet, catalogue, settings] = await Promise.all([
    request('/api/v1/wallet').then(response => response.json()),
    request('/api/v1/catalogue').then(response => response.json()),
    request('/api/v1/settings').then(response => response.json()),
    showWorks(0),
  ]);
  document.querySelector('#available').textContent = wallet.available;
  document.querySelector('#reserved').textContent = wallet.reserved;
  applyTheme(settings.theme);
  themeInputs.forEach(input => input.disabled = false);
  const models = document.querySelector('#models');
  for (const model of catalogue.models) {
    const item = listItem(model.aggregator + ' · ' + model.title);
    if (model.image_card) {
      const parameters = document.createElement('small');
      parameters.textContent = model.image_card.label;
      item.append(parameters);
      item.append(imageForm(model.id));
    }
    models.append(item);
  }
  for (const [name, available] of Object.entries(catalogue.availability)) {
    if (!available) models.append(listItem(name + ' · каталог временно недоступен'));
  }
  if (!models.children.length) models.append(listItem('Нет доступных моделей.'));
  status.textContent = '';
  if (history.state?.jobId) {
    selectPanel('library');
    await openJob(history.state.jobId);
  }
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  for (const input of themeInputs) input.checked = input.value === theme;
}

async function saveTheme() {
  retryTheme.hidden = true;
  themeInputs.forEach(input => input.disabled = true);
  themeStatus.dataset.error = 'false';
  themeStatus.textContent = 'Сохраняем…';
  try {
    await request('/api/v1/settings', {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ theme: wantedTheme }),
    });
    themeStatus.textContent = 'Тема сохранена.';
  } catch (error) {
    themeStatus.dataset.error = 'true';
    themeStatus.textContent = 'Не удалось сохранить тему. ' + error.message;
    retryTheme.hidden = false;
  } finally {
    themeInputs.forEach(input => input.disabled = false);
  }
}

for (const input of themeInputs) input.onchange = () => {
  wantedTheme = input.value;
  applyTheme(wantedTheme);
  saveTheme();
};
retryTheme.onclick = saveTheme;

const tabs = [...document.querySelectorAll('nav [data-panel]')];
const card = document.querySelector('#job-card');
const overview = document.querySelector('#library-overview');
const jobStatus = document.querySelector('#job-status');
const cancelJob = document.querySelector('#cancel-job');
const reloadJob = document.querySelector('#reload-job');
const states = {
  pending: 'Ожидает запуска', dispatching: 'Выполняется', delegated: 'Передано исполнителю',
  completed: 'Завершено', interrupted: 'Прервано', rejected: 'Отклонено',
  uncertain: 'Результат пока неизвестен', cancelled: 'Отменено',
};
let cardRevision = 0;

function selectPanel(panel) {
  for (const button of tabs) {
    const selected = button.dataset.panel === panel;
    document.getElementById(button.dataset.panel).hidden = !selected;
    if (selected) button.setAttribute('aria-current', 'page');
    else button.removeAttribute('aria-current');
  }
}

async function showJobs() {
  const { jobs } = await (await request('/api/v1/jobs')).json();
  document.querySelector('#jobs-title').hidden = jobs.length === 0;
  document.querySelector('#jobs').replaceChildren(...jobs.map(job => {
    const item = listItem(job.model + ' · ' + (states[job.state] ?? job.state));
    const open = document.createElement('button');
    open.textContent = 'Открыть задание ' + job.id;
    open.onclick = () => openJob(job.id);
    item.append(open);
    return item;
  }));
}

async function openJob(id, cancel = false) {
  const revision = ++cardRevision;
  history.replaceState({ ...history.state, jobId: id }, '');
  overview.hidden = true;
  card.hidden = false;
  document.querySelector('#job-id').textContent = id;
  cancelJob.hidden = true;
  reloadJob.disabled = true;
  jobStatus.textContent = cancel ? 'Проверяем отмену…' : 'Получаем статус…';
  try {
    const path = '/api/v1/jobs/' + encodeURIComponent(id);
    if (cancel) await request(path + '/cancel', { method: 'POST' });
    const job = await (await request(path)).json();
    if (revision !== cardRevision) return;
    jobStatus.textContent = states[job.state] ?? job.state;
    cancelJob.hidden = !(job.origin === 'http' && job.state === 'pending');
  } catch (error) {
    if (revision === cardRevision) jobStatus.textContent = error.message;
  } finally {
    if (revision === cardRevision) reloadJob.disabled = false;
  }
}

function navigate(panel) {
  cardRevision++;
  history.replaceState({ ...history.state, jobId: null }, '');
  overview.hidden = false;
  card.hidden = true;
  selectPanel(panel);
  if (panel === 'library' && token) showJobs().catch(showError);
}

for (const tab of tabs) tab.onclick = () => navigate(tab.dataset.panel);
cancelJob.onclick = () => openJob(history.state.jobId, true);
reloadJob.onclick = () => openJob(history.state.jobId);
document.querySelector('#back-to-works').onclick = () => navigate('library');

document.querySelector('#previous').onclick = () => showWorks(page - 1).catch(showError);
document.querySelector('#next').onclick = () => showWorks(page + 1).catch(showError);
start().catch(showError);
