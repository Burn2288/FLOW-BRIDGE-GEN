const telegram = window.Telegram?.WebApp;
const status = document.querySelector('#status');
const themeStatus = document.querySelector('#theme-status');
const retryTheme = document.querySelector('#retry-theme');
const themeInputs = [...document.querySelectorAll('[name=theme]')];
let wantedTheme;
const works = document.querySelector('#works');
let token;
let page = 0;
let worksRevision = 0;
let previewRevision = 0;
let openPreview;
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
  if (response.status === 401) throw Object.assign(Error('Откройте приложение заново из Telegram.'), {status: 401});
  if (response.status === 403) throw Object.assign(Error('Откройте бот и проверьте доступ к аккаунту.'), {status: 403});
  if (response.status === 428 && path === '/api/v1/session') {
    throw Object.assign(Error('Прочитайте документы и подтвердите согласие.'), {documents: await response.json()});
  }
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

const previewFormats = {
  image: ['img', 'image/png'],
  video: ['video', 'video/mp4'],
  audio: ['audio', 'audio/mpeg'],
  music: ['audio', 'audio/mpeg'],
};

function closePreview() {
  previewRevision++;
  if (!openPreview) return;
  openPreview.container.replaceChildren();
  openPreview.button.textContent = 'Просмотр';
  URL.revokeObjectURL(openPreview.url);
  openPreview = null;
}

function appendPreview(item, work) {
  const [tag, contentType] = previewFormats[work.kind];
  const button = document.createElement('button');
  button.textContent = 'Просмотр';
  const container = document.createElement('div');
  const message = document.createElement('p');
  message.className = 'notice';
  message.setAttribute('role', 'status');
  button.onclick = async () => {
    if (openPreview?.button === button) {
      closePreview();
      return;
    }
    closePreview();
    const revision = previewRevision;
    button.disabled = true;
    message.textContent = 'Загружаем результат…';
    try {
      const response = await request('/api/v1/works/' + encodeURIComponent(work.kind) + '/' + work.id);
      const file = await response.blob();
      if (revision !== previewRevision) return;
      const jpeg = tag === 'img' && response.headers.get('Content-Disposition')?.endsWith('.jpg"');
      const url = URL.createObjectURL(file.slice(0, file.size, jpeg ? 'image/jpeg' : contentType));
      const media = document.createElement(tag);
      if (tag === 'img') media.alt = 'Результат генерации';
      else {
        media.controls = true;
        if (tag === 'video') media.playsInline = true;
      }
      media.onerror = () => { message.textContent = 'Этот результат можно скачать для просмотра.'; };
      media.src = url;
      container.replaceChildren(media);
      openPreview = {url, container, button};
      button.textContent = 'Закрыть просмотр';
    } catch (error) {
      if (revision === previewRevision) message.textContent = error.message;
    } finally {
      button.disabled = false;
      if (message.textContent === 'Загружаем результат…') message.textContent = '';
    }
  };
  item.append(button, message, container);
}

async function showWorks(target) {
  const revision = ++worksRevision;
  const data = await (await request('/api/v1/works?page=' + target)).json();
  if (revision !== worksRevision) return;
  closePreview();
  works.replaceChildren();
  for (const work of data.works) {
    const kinds = { image: 'Изображение', video: 'Видео', audio: 'Аудио', chat: 'Текст', music: 'Музыка' };
    const states = { queued: 'В очереди', dispatching: 'Выполняется', succeeded: 'Готово',
      failed: 'Ошибка', cancelled: 'Отменено', uncertain: 'Требует проверки' };
    const label = kinds[work.kind] ?? work.kind;
    const state = states[work.status] ?? work.status;
    const price = work.price === null ? 'Цена недоступна' : work.price + ' кредитов';
    const item = listItem([label, work.model, state, price].filter(Boolean).join(' · '));
    item.id = 'work-' + work.id;
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
      if (previewFormats[work.kind]) appendPreview(item, work);
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

const consentPanel = document.querySelector('#consent');
const consentAccept = document.querySelector('#accept-consent');
const navigation = document.querySelector('nav');
let presentedTerms;

function showDocuments(container, docs) {
  const version = document.createElement('p');
  version.textContent = 'Версия документов ' + docs.version + (docs.test_only ? ' · Тестовые документы' : '');
  container.replaceChildren(version);
  for (const [field, label] of [['terms', 'Условия использования'], ['privacy', 'Обработка данных']]) {
    const details = document.createElement('details');
    const title = document.createElement('summary');
    const text = document.createElement('pre');
    title.textContent = label;
    text.textContent = docs[field];
    details.append(title, text);
    container.append(details);
  }
}

async function showProfile() {
  const notice = document.querySelector('#profile-status');
  const docs = document.querySelector('#profile-documents');
  notice.textContent = 'Загружаем профиль…';
  docs.replaceChildren();
  try {
    const profile = await (await request('/api/v1/profile')).json();
    notice.textContent = 'Telegram ID: ' + profile.telegram_id + ' · Условия приняты';
    showDocuments(docs, profile.documents);
  } catch (error) {
    notice.textContent = error.message;
  }
}

document.querySelector('#reload-profile').onclick = () => { if (token) void showProfile(); };

async function start(termsVersion) {
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
    try {
      const session = await request('/api/v1/session', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({initData: telegram.initData, terms_version: termsVersion ?? null}),
      });
      token = (await session.json()).token;
    } catch (error) {
      if (!error.documents) throw error;
      selectPanel('consent');
      navigation.hidden = true;
      status.textContent = error.message;
      consentPanel.hidden = false;
      showDocuments(document.querySelector('#consent-documents'), error.documents);
      presentedTerms = error.documents.version;
      return;
    }
    sessionStorage.setItem('miniapp.session', JSON.stringify({ launch, token }));
  }
  if (activePanel === 'consent') {
    consentPanel.hidden = true;
    navigation.hidden = false;
    selectPanel('catalogue');
  }
  // The user may select a panel while authentication is still pending.
  if (activePanel === 'support') void showSupport();
  if (activePanel === 'profile') void showProfile();
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
  renderCatalogue(catalogue);
  status.textContent = '';
  if (!document.querySelector('#balance').hidden) await showBalance();
  if (history.state?.jobId) {
    selectPanel('library');
    await openJob(history.state.jobId);
  }
}

const studioSelect = document.querySelector('#studio-select');
const catalogueEmpty = document.querySelector('#catalogue-empty');
let catalogueEntries = [];

function filterStudios() {
  const studio = studioSelect.value || '';
  let visible = 0;
  for (const {item, operation} of catalogueEntries) {
    item.hidden = Boolean(studio) && operation !== studio;
    if (!item.hidden) visible++;
  }
  catalogueEmpty.hidden = visible > 0;
}
studioSelect.onchange = filterStudios;

function renderCatalogue(catalogue) {
  const models = document.querySelector('#models');
  models.replaceChildren();
  catalogueEntries = [];
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
    catalogueEntries.push({item, operation: model.operation});
  }
  for (const [name, available] of Object.entries(catalogue.availability)) {
    if (!available) {
      const item = listItem(name + ' · каталог временно недоступен');
      models.append(item);
      catalogueEntries.push({item});
    }
  }
  studioSelect.disabled = false;
  filterStudios();
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
      const link = document.querySelector('#referral-link');
      link.textContent = referral.link ?? '';
      link.hidden = !referral.link;
      copy.textContent = referral.link ? 'Скопировать ссылку' : 'Скопировать код';
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
    const link = document.querySelector('#referral-link').textContent;
    await navigator.clipboard.writeText(link || document.querySelector('#referral-code').textContent);
    result.textContent = link ? 'Ссылка скопирована.' : 'Код скопирован.';
  } catch {
    result.textContent = 'Не удалось скопировать. Выделите ссылку или код вручную.';
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

function appendOperatorReply(container, current) {
  const form = document.createElement('form');
  form.className = 'operator-support card';
  const ticket = document.createElement('select');
  const ticketHistory = document.createElement('ul');
  const body = document.createElement('textarea');
  const send = document.createElement('button');
  const notice = document.createElement('p');
  ticket.setAttribute('aria-label', 'Обращение');
  ticket.required = true;
  body.setAttribute('aria-label', 'Ответ оператора');
  body.placeholder = 'Ответ оператора';
  body.maxLength = 2000;
  body.required = true;
  send.type = 'submit';
  send.disabled = true;
  send.textContent = 'Сохранить ответ';
  notice.setAttribute('role', 'status');
  let historyRevision = 0;
  async function loadTicket() {
    const revision = ++historyRevision;
    send.disabled = true;
    ticketHistory.replaceChildren();
    if (!ticket.value) return;
    const selection = ticket.value;
    const response = await request('/api/v1/admin/support?ticket_id=' + encodeURIComponent(selection));
    const data = await response.json();
    if (!current() || revision !== historyRevision) return;
    const selected = ticket.selectedOptions[0];
    selected.textContent = ticketLabel(data);
    for (const item of data.messages) {
      const row = document.createElement('li');
      row.textContent = (item.author === 'operator' ? 'Оператор: ' : 'Пользователь: ') + item.body;
      ticketHistory.append(row);
    }
    send.disabled = false;
  }
  function ticketLabel(item) {
    return (item.status === 'answered' ? 'Есть ответ' : 'Открыто') + ' · ' +
      new Date(item.created_at).toLocaleString('ru-RU') + ' · ' + item.id;
  }
  const refreshHistory = async () => {
    const loading = loadTicket();
    const revision = historyRevision;
    try {
      await loading;
    } catch (error) {
      if (!current() || revision !== historyRevision) return;
      if (error.status === 401 || error.status === 403) void showAdministration();
      else notice.textContent = 'Не удалось открыть обращение. ' + error.message;
    }
  };
  ticket.onchange = refreshHistory;
  void (async () => {
    const response = await request('/api/v1/admin/support');
    const inbox = await response.json();
    if (!current()) return;
    for (const item of inbox.tickets) {
      const option = document.createElement('option');
      option.value = item.id;
      option.textContent = ticketLabel(item);
      ticket.append(option);
    }
    if (!inbox.tickets.length) notice.textContent = 'Обращений пока нет.';
    else refreshHistory();
  })().catch(error => {
    if (current()) notice.textContent = 'Не удалось загрузить обращения. ' + error.message;
  });
  let pending;
  form.onsubmit = async event => {
    event.preventDefault();
    if (!current() || send.disabled) return;
    const ticketId = ticket.value.trim();
    const text = body.value.trim();
    if (!ticketId || !text) return;
    if (!pending || pending.ticket_id !== ticketId || pending.text !== text) {
      pending = {ticket_id: ticketId, text, request_id: crypto.randomUUID()};
    }
    send.disabled = true;
    ticket.disabled = true;
    body.disabled = true;
    notice.textContent = 'Сохраняем ответ…';
    try {
      await request('/api/v1/admin/support/reply', {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(pending),
      });
      if (!current()) return;
      body.value = '';
      pending = null;
      notice.textContent = 'Ответ сохранён. Владелец увидит его в истории обращения.';
      await loadTicket();
    } catch (error) {
      if (!current()) return;
      if (error.status === 401 || error.status === 403) {
        void showAdministration();
        return;
      }
      if (pending) {
        notice.textContent = 'Ответ не подтверждён. ' + error.message;
        send.disabled = false;
      } else {
        notice.textContent = 'Ответ сохранён. Не удалось обновить историю. ' + error.message;
      }
    } finally {
      ticket.disabled = false;
      body.disabled = false;
    }
  };
  form.append(ticket, ticketHistory, body, send, notice);
  container.append(form);
}

async function refreshCatalogue() {
  const session = token;
  const catalogue = await (await request('/api/v1/catalogue')).json();
  if (session === token) renderCatalogue(catalogue);
}

function appendModelVisibility(container, current) {
  const path = '/api/v1/admin/model-visibility';
  const form = document.createElement('form');
  const title = document.createElement('h3');
  const selection = document.createElement('select');
  const notice = document.createElement('p');
  const preview = document.createElement('button');
  const rollback = document.createElement('button');
  const confirm = document.createElement('button');
  title.textContent = 'Видимость моделей';
  selection.setAttribute('aria-label', 'Модель');
  notice.setAttribute('role', 'status');
  preview.type = rollback.type = confirm.type = 'button';
  rollback.textContent = 'Предпросмотр отката';
  confirm.textContent = 'Подтвердить видимость';
  let models = [];
  let pending;

  const selected = () => models[Number(selection.value)];
  const display = value => value === 'VISIBLE' ? 'Видима' : 'Скрыта';
  const render = () => {
    const model = selected();
    preview.textContent = model?.visibility === 'VISIBLE' ? 'Предпросмотр скрытия' : 'Предпросмотр показа';
    preview.disabled = !model;
    rollback.disabled = !model?.previous_visibility;
    confirm.hidden = !pending;
  };
  const send = async (action, body) => (await request(path + '/' + action, {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body),
  })).json();
  async function load() {
    const response = await request(path);
    const data = await response.json();
    if (!current()) return;
    const index = selection.selectedIndex;
    models = data.models;
    selection.replaceChildren();
    models.forEach((model, position) => {
      const option = document.createElement('option');
      option.value = String(position);
      option.textContent = model.title + ' · ' + model.provider + ' · ' + model.operation +
        ' · ' + display(model.visibility);
      selection.append(option);
    });
    if (index >= 0 && index < models.length) selection.selectedIndex = index;
    if (!models.length) notice.textContent = 'Моделей пока нет.';
    render();
  }
  selection.onchange = () => {
    pending = null;
    notice.textContent = '';
    render();
  };
  async function action(run) {
    if (!current() || selection.disabled) return;
    selection.disabled = preview.disabled = rollback.disabled = confirm.disabled = true;
    try {
      await run();
    } catch (error) {
      if (!current()) return;
      if (error.status === 409) {
        pending = null;
        notice.textContent = 'Настройка изменилась. Запросите новый предпросмотр.';
        await load().catch(() => {});
      } else {
        if ([400, 401, 403, 404].includes(error.status)) pending = null;
        notice.textContent = error.message;
      }
    } finally {
      selection.disabled = confirm.disabled = false;
      render();
    }
  }
  function prepare(restore) {
    const model = selected();
    if (!model) return;
    pending = null;
    const visibility = restore ? model.previous_visibility : (model.visibility === 'VISIBLE' ? 'HIDDEN' : 'VISIBLE');
    const keys = {provider: model.provider, model_id: model.model_id, operation: model.operation, visibility};
    if (restore) keys.rollback_of = model.version;
    return action(async () => {
      notice.textContent = 'Проверяем настройку…';
      const result = await send('preview', keys);
      if (!current()) return;
      pending = {...keys, expected_version: result.version, request_id: crypto.randomUUID()};
      notice.textContent = result.title + ' · ' + display(result.visibility) + ' → ' +
        display(result.desired_visibility);
    });
  }
  preview.onclick = () => { void prepare(false); };
  rollback.onclick = () => { void prepare(true); };
  confirm.onclick = () => {
    if (!pending) return;
    void action(async () => {
      const result = await send('confirm', pending);
      pending = null;
      if (current()) {
        notice.textContent = result.title + ' · ' + display(result.visibility) + '. Изменение сохранено.';
      }
      await Promise.all([current() && load(), refreshCatalogue()]);
    });
  };
  form.onsubmit = event => event.preventDefault();
  form.append(title, selection, preview, rollback, confirm, notice);
  container.append(form);
  render();
  void load().catch(error => {
    if (current()) notice.textContent = error.message;
  });
}

let adminRequest = 0;
const operationsFields = {
  registered_users: 'Пользователи',
  legacy_queued_jobs: 'Задания в старой очереди',
  quoted_pending_tasks: 'Задания с расчётом, ожидающие запуска',
  legacy_running_or_uncertain: 'Запущенные или неопределённые задания в старой очереди',
  quoted_running_or_uncertain: 'Запущенные или неопределённые задания с расчётом',
  live_reserved_tokens: 'Токены в резерве',
  live_payment_debt_tokens: 'Платёжный долг, токены',
  referral_debt_tokens: 'Реферальный долг, токены',
  referral_payment_review_cases: 'Реферальные платежи на сверке',
};
const operationsSections = [
  ['tasks_by_period_and_status', 'Задания по дням', {local_day: 'Дата', source: 'Очередь', status: 'Статус', task_count: 'Заданий'}],
  ['tasks_by_provider_and_model', 'Провайдеры и модели', {provider: 'Провайдер', model_id: 'Модель', source: 'Очередь', task_count: 'Заданий'}],
  ['provider_job_statuses', 'Статусы заданий у провайдеров', {provider: 'Провайдер', model_id: 'Модель', kind: 'Тип', status: 'Статус', task_count: 'Заданий'}],
  ['wallet_movements', 'Движения кошелька', {local_day: 'Дата', mode: 'Режим', kind: 'Тип', operation_count: 'Операций',
    available_delta: 'Изменение баланса, токены', reserved_delta: 'Изменение резерва, токены'}],
  ['payments', 'Платежи', {local_day: 'Дата', provider: 'Провайдер', currency: 'Валюта', status: 'Статус',
    payment_count: 'Платежей', order_amount: 'Сумма'}],
  ['reconciliation_queue', 'Очередь сверки', {source: 'Источник', provider: 'Провайдер', operation: 'Операция', status: 'Статус', case_count: 'Случаев'}],
  ['provider_cost_evidence', 'Подтверждённая себестоимость', {provider: 'Провайдер', unit: 'Единица', known_count: 'Подтверждено',
    unknown_count: 'Неизвестно', confirmed_unbilled_count: 'Без списания', amount: 'Сумма'}],
];

function appendOperationsReport(report, data) {
  const snapshot = document.createElement('ul');
  for (const [key, label] of Object.entries(operationsFields)) {
    snapshot.append(listItem(label + ': ' + data.current_state[key]));
  }
  const health = document.createElement('p');
  health.textContent = 'Текущая доступность провайдеров: ' +
    (data.current_state.provider_health === 'NOT_PROVEN' ? 'не проверена' : data.current_state.provider_health);
  const cost = document.createElement('p');
  const coverage = data.provider_cost_coverage;
  cost.textContent = 'Без подтверждения стоимости или списания: ' +
    coverage.without_cost_or_bill_evidence + ' из ' + coverage.accepted_task_count + ' принятых заданий.';
  const alerts = document.createElement('p');
  const queue = data.reconciliation_queue;
  const cases = queue.groups.reduce((sum, item) => sum + item.case_count, 0);
  alerts.textContent = 'Случаев на сверке за период: ' + (queue.truncated ? 'не менее ' : '') + cases + '.';
  report.append(snapshot, health, cost, alerts);

  for (const [key, label, columns] of operationsSections) {
    const section = data[key];
    const details = document.createElement('details');
    const title = document.createElement('summary');
    title.textContent = label;
    details.append(title);
    const rows = document.createElement('ul');
    rows.className = 'cards';
    for (const row of section.groups) {
      rows.append(listItem(Object.entries(columns).map(([field, caption]) =>
        caption + ': ' + (row[field] ?? '—')).join(' · ')));
    }
    if (!section.groups.length) rows.append(listItem('Нет данных за период.'));
    if (section.truncated) rows.append(listItem('Показано групп: ' + section.groups.length + ' из ' + section.group_count + '.'));
    details.append(rows);
    report.append(details);
  }
}

async function showAdministration() {
  if (!token) return;
  const id = ++adminRequest;
  const session = token;
  const current = () => id === adminRequest && token === session && activePanel === 'administration';
  const notice = document.querySelector('#admin-status');
  const report = document.querySelector('#admin-report');
  report.replaceChildren();
  notice.textContent = 'Проверяем полномочия…';
  let canReply = false;
  let canSetVisibility = false;
  try {
    const auth = await request('/api/v1/admin/capabilities');
    const authority = await auth.json();
    if (!current()) return;
    canReply = authority.capabilities.includes('support.operate');
    if (canReply) appendOperatorReply(report, current);
    canSetVisibility = authority.capabilities.includes('settings.visibility');
    if (canSetVisibility) appendModelVisibility(report, current);
    if (!authority.capabilities.includes('operations.read')) {
      notice.textContent = canSetVisibility ? 'Настройки каталога' : canReply ? 'Поддержка' : 'Нет доступа к административному обзору.';
      return;
    }
    notice.textContent = 'Загружаем обзор за 7 дней…';
    const end = new Date();
    const start = new Date(end.getTime() - 7 * 86400000);
    const query = new URLSearchParams({start: start.toISOString(), end: end.toISOString(), limit: '30'});
    const response = await request('/api/v1/admin/operations?' + query);
    const data = await response.json();
    if (!current()) return;
    appendOperationsReport(report, data);
    notice.textContent = 'Обзор за 7 дней · ' + authority.role;
  } catch (error) {
    if (!current()) return;
    if ((!canReply && !canSetVisibility) || error.status === 401 || error.status === 403) report.replaceChildren();
    notice.textContent = 'Обзор недоступен. ' + error.message;
  }
}

document.querySelector('#admin-reload').onclick = () => { void showAdministration(); };

const ownerSupportStatus = document.querySelector('#support-status');
const ownerSupportDraft = document.querySelector('#owner-support-text');
const ownerSupportList = document.querySelector('#owner-support-list');
const ownerSupportHistory = document.querySelector('#owner-support-history');
let ownerSupportRevision = 0;
let pendingSupport;

async function showSupport(ticket) {
  const revision = ++ownerSupportRevision;
  const session = token;
  const current = () => revision === ownerSupportRevision && token === session && activePanel === 'support';
  ownerSupportStatus.textContent = 'Загрузка…';
  ownerSupportHistory.replaceChildren();
  try {
    const path = '/api/v1/support' + (ticket ? '?ticket_id=' + encodeURIComponent(ticket) : '');
    const data = await (await request(path)).json();
    if (!current()) return;
    if (ticket) {
      ownerSupportHistory.replaceChildren(...data.messages.map(message =>
        listItem((message.author === 'operator' ? 'Поддержка: ' : 'Вы: ') + message.body)));
      if (data.has_more) ownerSupportHistory.append(listItem('Показаны первые сообщения.'));
    } else {
      ownerSupportList.replaceChildren(...data.tickets.map(entry => {
        const row = document.createElement('li');
        const open = document.createElement('button');
        open.textContent = new Date(entry.created_at).toLocaleString('ru-RU') +
          (entry.status === 'answered' ? ' · Есть ответ' : ' · Ожидает ответа');
        open.onclick = () => { void showSupport(entry.id); };
        row.append(open);
        return row;
      }));
      if (data.has_more) ownerSupportList.append(listItem('Показаны последние обращения.'));
    }
    ownerSupportStatus.textContent = ticket || data.tickets.length ? '' : 'Обращений пока нет.';
  } catch (error) {
    if (current()) ownerSupportStatus.textContent = error.message;
  }
}

document.querySelector('#owner-support-refresh').onclick = () => { if (token) void showSupport(); };
const ownerSupportCreate = document.querySelector('#owner-support-create');
ownerSupportCreate.onclick = async () => {
  if (!token || ownerSupportCreate.disabled) return;
  const text = ownerSupportDraft.value.trim();
  if (!text) {
    ownerSupportStatus.textContent = 'Введите текст обращения.';
    return;
  }
  ownerSupportCreate.disabled = true;
  ownerSupportDraft.disabled = true;
  const session = token;
  try {
    if (pendingSupport?.text !== text || pendingSupport.session !== session) {
      pendingSupport = {text, session, id: crypto.randomUUID()};
    }
    await request('/api/v1/support', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({text, request_id: pendingSupport.id}),
    });
    pendingSupport = null;
    if (token !== session) return;
    ownerSupportDraft.value = '';
    if (activePanel === 'support') await showSupport();
  } catch (error) {
    if (token === session && activePanel === 'support') ownerSupportStatus.textContent = error.message;
  } finally {
    ownerSupportCreate.disabled = false;
    ownerSupportDraft.disabled = false;
  }
};

function navigate(panel) {
  cardRevision++;
  if (panel !== 'library') closePreview();
  history.replaceState({ ...history.state, jobId: null }, '');
  overview.hidden = false;
  card.hidden = true;
  selectPanel(panel);
  if (panel === 'support' && token) void showSupport();
  if (panel === 'profile' && token) void showProfile();
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
consentAccept.onclick = async () => {
  if (!presentedTerms || consentAccept.disabled) return;
  consentAccept.disabled = true;
  try {
    await start(presentedTerms);
  } catch (error) {
    showError(error);
  } finally {
    consentAccept.disabled = false;
  }
};
start().catch(error => {
  showError(error);
  // Reload resumes the signed-in session and fetches the screens again.
  retryStartup.hidden = !(token && (error.networkError || error.status >= 500));
});
