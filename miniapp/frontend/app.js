const telegram = window.Telegram?.WebApp;
const status = document.querySelector('#status');
const themeStatus = document.querySelector('#theme-status');
const retryTheme = document.querySelector('#retry-theme');
const themeInputs = [...document.querySelectorAll('[name=theme]')];
let wantedTheme;
const works = document.querySelector('#works');
let token;
let page = 0;
let referralLoaded = false;
let referralRequest;
let activePanel = 'catalogue';

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(path, {
      ...options,
      headers: { ...(options.headers ?? {}), ...(token ? { Authorization: 'Bearer ' + token } : {}) },
    });
  } catch (error) {
    if (!(error instanceof TypeError)) throw error;
    throw Object.assign(Error('Нет связи с сервером. Проверьте подключение.'), {networkError: true});
  }
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

const buyStars = document.querySelector('#buy-stars');
const invoiceNotice = document.querySelector('#invoice-notice');
const paymentStates = {pending: 'Ожидает оплаты', succeeded: 'Оплачен', refunding: 'Возврат в обработке',
  refunded: 'Возвращён', review: 'На проверке'};
let paymentPage = 0;
let balanceRevision = 0;

async function showBalance(target = 0) {
  const revision = ++balanceRevision;
  const [wallet, history] = await Promise.all([
    request('/api/v1/wallet').then(r => r.json()),
    request('/api/v1/stars/payments?page=' + target).then(r => r.json()),
  ]);
  if (revision !== balanceRevision) return;
  document.querySelector('#available').textContent = wallet.available;
  document.querySelector('#reserved').textContent = wallet.reserved;
  buyStars.hidden = !history.checkout_enabled || !telegram?.openInvoice || !telegram.isVersionAtLeast('6.1');
  document.querySelector('#stars-pack').hidden = buyStars.hidden;
  document.querySelector('#stars-history').replaceChildren(...(history.payments.length
    ? history.payments.map(p => listItem(new Date(p.created_at).toLocaleString('ru-RU') +
      ' · ' + p.amount + ' ' + p.currency + ' · ' + (paymentStates[p.status] ?? p.status)))
    : [listItem('Платежей пока нет.')]));
  paymentPage = target;
  document.querySelector('#stars-prev').hidden = target === 0;
  document.querySelector('#stars-next').hidden = !history.has_more;
}

buyStars.onclick = async () => {
  if (buyStars.disabled) return;
  buyStars.disabled = true;
  invoiceNotice.textContent = '';
  try {
    const invoice = await (await request('/api/v1/stars/invoices', {method: 'POST'})).json();
    telegram.openInvoice(invoice.url, async outcome => {
      invoiceNotice.textContent = outcome === 'cancelled' ? 'Окно оплаты закрыто.' : '';
      try { await showBalance(); } catch (error) { showError(error); }
      finally { buyStars.disabled = false; }
    });
  } catch (error) {
    invoiceNotice.textContent = 'Не удалось открыть счёт. ' + error.message;
    buyStars.disabled = false;
  }
};
document.querySelector('#stars-prev').onclick = () => showBalance(paymentPage - 1).catch(showError);
document.querySelector('#stars-next').onclick = () => showBalance(paymentPage + 1).catch(showError);
document.querySelector('#stars-refresh').onclick = () => showBalance().catch(showError);

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
    const kinds = { image: 'Изображение', video: 'Видео', audio: 'Аудио', chat: 'Текст', music: 'Музыка' };
    const states = { queued: 'В очереди', dispatching: 'Выполняется', succeeded: 'Готово',
      failed: 'Ошибка', cancelled: 'Отменено', uncertain: 'Требует проверки' };
    const label = kinds[work.kind] ?? work.kind;
    const state = states[work.status] ?? work.status;
    const price = work.price === null ? 'Цена недоступна' : work.price + ' кредитов';
    const item = listItem([label, work.model, state, price].filter(Boolean).join(' · '));
    if (work.prompt) {
      const prompt = document.createElement('p');
      prompt.textContent = 'Запрос: ' + work.prompt;
      item.append(prompt);
      if (work.kind === 'image' && work.model === 'flux-schnell') {
        const similar = document.createElement('button');
        similar.textContent = 'Создать похожее';
        similar.onclick = () => {
          const form = generationForm(work.model, 'images.generate');
          form.elements.prompt.value = work.prompt;
          form.elements.prompt.dispatchEvent(new Event('input'));
          similar.replaceWith(form);
        };
        item.append(similar);
      }
    }
    const historyButton = document.createElement('button');
    historyButton.textContent = 'История';
    const details = document.createElement('ul');
    historyButton.onclick = async () => {
      try {
        const data = await (await request('/api/v1/works/' + encodeURIComponent(work.kind) + '/' + work.id + '/timeline')).json();
        details.replaceChildren(...data.events.map(event => listItem(event.label + (event.at ? ' · ' + event.at : ''))));
      } catch (error) { showError(error); }
    };
    if (work.kind !== 'music') item.append(historyButton, details);
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

function generationForm(model, operation, voices) {
  const form = document.querySelector('#image-form').content.firstElementChild.cloneNode(true);
  if (operation === 'video') form.querySelector('label span').textContent = 'Описание видео';
  if (operation === 'audio.generate') {
    form.querySelector('label span').textContent = 'Описание трека';
    form.elements.prompt.maxLength = 5000;
  }
  let voice;
  if (operation === 'audio.speech') {
    form.querySelector('label span').textContent = 'Текст для озвучки';
    const label = document.createElement('label');
    label.textContent = 'Голос';
    voice = document.createElement('select');
    for (const entry of voices) voice.add(new Option(entry.title, entry.voice_id));
    voice.onchange = invalidate;
    label.append(voice);
    form.prepend(label);
  }
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
        body: JSON.stringify({ model, prompt: prompt.value, ...(voice ? { voice: voice.value } : {}) }),
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
    if (voice) voice.disabled = true;
    message.textContent = 'Отправляем задание…';
    try {
      const response = await request('/api/v1/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Idempotency-Key': quote.quote_id },
        body: JSON.stringify({ quote_id: quote.quote_id }),
      });
      prompt.value = '';
      invalidate();
      message.textContent = 'Задание принято.';
      if (operation === 'audio.generate') {
        form.replaceWith(document.createTextNode('Попытка использована.'));
        navigate('library');
      } else if (operation !== 'images.generate') {
        const job = await response.json();
        selectPanel('library');
        await openJob(job.id);
      }
    } catch (error) {
      if (error.status === 409) {
        invalidate();
        message.textContent = 'Рассчитайте стоимость заново.';
      } else {
        message.textContent = error.message;
      }
    } finally {
      confirm.disabled = prompt.disabled = false;
      if (voice) voice.disabled = false;
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
  // The user may select a panel while authentication is still pending.
  if (activePanel === 'referral') void showReferral();
  if (activePanel === 'administration') void showAdministration();
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
    if (model.music_card) {
      const limits = document.createElement('small');
      limits.textContent = 'Одна попытка · Один MP3 · До 5000 символов · Хранение 7 дней · Отдельный тестовый баланс. Лицензия не указана.';
      item.append(limits);
      if (model.music_card.used) item.append(document.createTextNode('Попытка использована.'));
      else {
        const choose = document.createElement('button');
        choose.textContent = 'Выбрать ' + model.title;
        choose.onclick = () => choose.replaceWith(generationForm(model.id, model.operation));
        item.append(choose);
      }
    }
    if (model.speech_card) {
      const { model: id, voices } = model.speech_card;
      if (voices.length) {
        const select = document.createElement('button');
        select.textContent = 'Выбрать голос';
        select.onclick = () => select.replaceWith(generationForm(id, model.operation, voices));
        item.append(select);
      } else {
        item.append(document.createTextNode(' · Нет доступных голосов'));
      }
    }
    const card = model.image_card ?? model.video_card;
    if (card) {
      const parameters = document.createElement('small');
      parameters.textContent = card.label;
      item.append(parameters);
      if (model.video_card) {
        const select = document.createElement('button');
        select.textContent = 'Выбрать ' + model.title;
        select.onclick = () => select.replaceWith(generationForm(model.id, model.operation));
        item.append(select);
      } else {
        item.append(generationForm(model.id, model.operation));
      }
    }
    models.append(item);
  }
  for (const [name, available] of Object.entries(catalogue.availability)) {
    if (!available) models.append(listItem(name + ' · каталог временно недоступен'));
  }
  if (!models.children.length) models.append(listItem('Нет доступных моделей.'));
  status.textContent = '';
  if (!document.querySelector('#balance').hidden) await showBalance();
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
  completed: 'Завершено', failed: 'Ошибка обработки', interrupted: 'Прервано', rejected: 'Отклонено',
  uncertain: 'Результат пока неизвестен', cancelled: 'Отменено',
};
let cardRevision = 0;

function selectPanel(panel) {
  activePanel = panel;
  for (const button of tabs) {
    const selected = button.dataset.panel === panel;
    document.getElementById(button.dataset.panel).hidden = !selected;
    if (selected) button.setAttribute('aria-current', 'page');
    else button.removeAttribute('aria-current');
  }
}

async function showReferral() {
  if (referralLoaded) return;
  if (referralRequest) return referralRequest;
  const status = document.querySelector('#referral-status');
  const retry = document.querySelector('#retry-referral');
  const copy = document.querySelector('#copy-referral');
  status.textContent = 'Загружаем код приглашения…';
  retry.hidden = true;
  retry.disabled = true;
  copy.disabled = true;
  const pending = (async () => {
    try {
      const response = await request('/api/v1/referral');
      const referral = await response.json();
      document.querySelector('#referral-code').textContent = referral.code;
      document.querySelector('#referrer-status').textContent = referral.has_referrer
        ? 'Вы зарегистрировались по приглашению.' : 'Вы зарегистрировались без приглашения.';
      copy.disabled = false;
      status.textContent = '';
      referralLoaded = true;
    } catch (error) {
      status.textContent = `Не удалось загрузить приглашения. ${error.message}`;
      retry.hidden = false;
    } finally {
      retry.disabled = false;
      if (referralRequest === pending) referralRequest = null;
    }
  })();
  referralRequest = pending;
  return pending;
}

let referralFinancePage = 0;
let referralFinanceRequest = 0;
async function loadReferralFinances(page) {
  const ownerToken = token;
  if (!ownerToken) return;
  const requestId = ++referralFinanceRequest;
  const status = document.querySelector('#referral-finances-status');
  const summary = document.querySelector('#referral-finances-summary');
  const history = document.querySelector('#referral-finances-history');
  const previous = document.querySelector('#referral-finances-prev');
  const next = document.querySelector('#referral-finances-next');
  const current = () => requestId === referralFinanceRequest && token === ownerToken;
  summary.textContent = '';
  history.replaceChildren();
  previous.hidden = next.hidden = true;
  status.textContent = 'Загружаем начисления…';
  try {
    const response = await request('/api/v1/referral/finances?page=' + page);
    const data = await response.json();
    if (!current()) return;
    referralFinancePage = data.page;
    summary.textContent = 'Приглашено: ' + data.invitee_count + ' · Доступно: ' + data.available +
      ' · Начислено: ' + data.total_rewards + ' · Долг: ' + data.debt +
      ' · ' + data.policy_version + '. ' + data.terms;
    const labels = {referral_reward: 'Начисление', referral_reversal: 'Сторно',
      referral_debt_repay: 'Погашение долга'};
    for (const item of data.history) {
      const row = document.createElement('li');
      row.textContent = labels[item.kind] + ': ' + item.amount + ' · Долг +' + item.debt_added;
      history.append(row);
    }
    status.textContent = data.history.length ? '' : 'На этой странице нет операций.';
    previous.hidden = data.page === 0;
    next.hidden = !data.has_more;
  } catch {
    if (current()) status.textContent = 'Не удалось загрузить начисления. Повторите запрос.';
  }
}
document.querySelector('#load-referral-finances').onclick = () => { void loadReferralFinances(0); };
document.querySelector('#referral-finances-prev').onclick = () => { void loadReferralFinances(referralFinancePage - 1); };
document.querySelector('#referral-finances-next').onclick = () => { void loadReferralFinances(referralFinancePage + 1); };

document.querySelector('#copy-referral').onclick = async () => {
  const result = document.querySelector('#referral-copy-status');
  try {
    await navigator.clipboard.writeText(document.querySelector('#referral-code').textContent);
    result.textContent = 'Код скопирован.';
  } catch {
    result.textContent = 'Не удалось скопировать. Выделите код вручную.';
  }
};
document.querySelector('#retry-referral').onclick = () => { void showReferral(); };

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
    cancelJob.hidden = !(job.operation === 'images.generate' && job.origin === 'http' && job.state === 'pending');
  } catch (error) {
    if (revision === cardRevision) jobStatus.textContent = error.message;
  } finally {
    if (revision === cardRevision) reloadJob.disabled = false;
  }
}

let adminRequest = 0;
async function showAdministration() {
  if (!token) return;
  const id = ++adminRequest;
  const session = token;
  const current = () => id === adminRequest && token === session && activePanel === 'administration';
  const notice = document.querySelector('#admin-status');
  const report = document.querySelector('#admin-report');
  report.replaceChildren();
  notice.textContent = 'Проверяем полномочия…';
  try {
    const auth = await request('/api/v1/admin/capabilities');
    const authority = await auth.json();
    if (!current()) return;
    if (!authority.capabilities.includes('operations.read')) {
      notice.textContent = 'Нет доступа к административному обзору.';
      return;
    }
    notice.textContent = 'Загружаем обзор за 7 дней…';
    const end = new Date();
    const start = new Date(end.getTime() - 7 * 86400000);
    const query = new URLSearchParams({start: start.toISOString(), end: end.toISOString(), limit: '30'});
    const response = await request('/api/v1/admin/operations?' + query);
    const data = await response.json();
    if (!current()) return;
    const fields = {
      registered_users: 'Пользователи', legacy_queued_jobs: 'Задания в очереди',
      quoted_pending_tasks: 'Ожидают запуска', live_reserved_tokens: 'Токены в резерве',
      live_payment_debt_tokens: 'Платёжный долг', referral_debt_tokens: 'Реферальный долг',
      referral_payment_review_cases: 'Платежи на сверке',
    };
    const summary = document.createElement('ul');
    for (const [key, label] of Object.entries(fields)) {
      const row = document.createElement('li');
      row.textContent = label + ': ' + data.current_state[key];
      summary.append(row);
    }
    report.append(summary);
    const sections = {
      tasks_by_period_and_status: 'Задания', tasks_by_provider_and_model: 'Провайдеры и модели',
      wallet_movements: 'Движения кошелька', payments: 'Платежи',
      reconciliation_queue: 'На сверке', provider_cost_coverage: 'Покрытие себестоимости',
    };
    for (const [key, label] of Object.entries(sections)) {
      const details = document.createElement('details');
      const title = document.createElement('summary');
      title.textContent = label;
      const body = document.createElement('pre');
      body.textContent = JSON.stringify(data[key], null, 2);
      details.append(title, body);
      report.append(details);
    }
    notice.textContent = 'Обзор за 7 дней · ' + authority.role;
  } catch (error) {
    if (!current()) return;
    report.replaceChildren();
    notice.textContent = 'Обзор недоступен. ' + error.message;
  }
}

document.querySelector('#admin-reload').onclick = () => { void showAdministration(); };

function navigate(panel) {
  cardRevision++;
  history.replaceState({ ...history.state, jobId: null }, '');
  overview.hidden = false;
  card.hidden = true;
  selectPanel(panel);
  if (panel === 'referral' && token) void showReferral();
  if (panel === 'administration' && token) void showAdministration();
  if (panel === 'balance' && token) showBalance().catch(showError);
  if (panel === 'library' && token) Promise.all([showJobs(), showWorks(0)]).catch(showError);
}

for (const tab of tabs) tab.onclick = () => navigate(tab.dataset.panel);
cancelJob.onclick = () => openJob(history.state.jobId, true);
reloadJob.onclick = () => openJob(history.state.jobId);
document.querySelector('#back-to-works').onclick = () => navigate('library');

document.querySelector('#previous').onclick = () => showWorks(page - 1).catch(showError);
document.querySelector('#next').onclick = () => showWorks(page + 1).catch(showError);
const retryStartup = document.querySelector('#retry-startup');
retryStartup.onclick = () => location.reload();
start().catch(error => {
  showError(error);
  // Reload resumes the signed-in session and fetches the screens again.
  retryStartup.hidden = !(token && (error.networkError || error.status >= 500));
});
