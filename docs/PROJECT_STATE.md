# PROJECT_STATE — текущая доказанная точка и граница интеграции

Дата: 2026-11-15. Статус: DOCS_UPDATED / CODE_CANDIDATE_PRESENT / MAIN_NOT_INTEGRATED.

## Проверенные исходные точки
- Репозиторий Burn2288/FLOW-BRIDGE-GEN; `main` SHA `98d05504446458252ede2df35e8870b2e1bc63e2`, в нём первичный README и .gitignore.
- Общая нормативная документация `docs/bootstrap` SHA `008951279802ee0761da998e71c5a6e78c21a6d5`, PR #1 открыт.
- Документационная надстройка `docs/foundation-contracts-v1` — PR #18 к `docs/bootstrap`; полный актуальный HEAD смотреть на PR. Здесь обновляются реестр контрактов, структура продукта и промпты Codex. **Не слито**.
- Исходный код vankhu21 до `work/vankhu21/miniapp-read` SHA `d691d54e0266c3d519d66575555fa45895ef40ac`, PR #17 открыт, draft, база — PR #16. PR #8–#17 образуют зависимый стэк и не слиты в main.
- На SHA `d691d54...` два GitHub Actions завершились success: [Isolated acceptance](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/43759469582) и [Documentation](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/43759469627). PR #17 сообщает 392 passed на отдельной PostgreSQL. Это **не** live-прогон Telegram Mini App или провайдеров.
- Исторический стенд `flowbridge-live-smoke` по аудиту в PR #16 был на SHA `5601faa0481a52a67e0ada43a8a48f07bd3d1968`. Нельзя смешивать этот build с текущим PR #17.

## Source facts
- `src/elevenbot`: Telegram UI/navigation, Admin Edition, ProviderRegistry, Pricing, TaskLaunch, Wallet/Ledger, CLODEX/AnyModel/Fal и музыка/видео/изображения, Platega и базовая Stars оплата.
- `miniapp/backend/web.py`: Telegram initData validation, короткая bearer-сессия, каталог/кошелёк/работы/файл, тема пользователя. Нет создания генерации/платежа, веб-админки, рефералов.
- `src/elevenbot/config.py` уже использует `ADMIN_TELEGRAM_IDS`, `TELEGRAM_BOT_TOKEN`, `MINIAPP_URL`, `PAYMENTS_ENABLED`, `PUBLIC_IMAGE_MODELS`; `.env` контракт старого проекта должен быть согласован с этими ключами.
- Наработки AI-SHOP-BOT donor SHA `494ab81f5552be836a37ec3aa685e6be8308076c` нужны прежде всего для реферальной системы и дополнений к платёжным контрактам, но Platega и платёжный кошелёк уже существуют в кандидатном коде FLOW: не переносить повторно.

## Состояние проверки
- SOURCE_PRESENT (файлы и интерфейсы): проверено статически.
- CI_PASS на PR #17 SHA: подтверждены две завершившиеся success проверки.
- LIVE_PRODUCT_E2E / PUBLIC_PAYMENT / MINIAPP_ADMIN / FULL_PARITY: NOT_PROVEN.
- MERGED_IN_MAIN и local full-project sync: NOT_DONE.
- Production изменения/платные операции/слияния: не выполнялись.

## Главные риски
1. Зависимый стэк PR требует согласованного графа интеграции, ревью, актуальных CI и безопасного merge/rebase, без потери чужих изменений.
2. Для digital услуг внутри Telegram официальная политика требует Stars XTR; прямой Platega checkout не разрешено автоматически включать для таких операций. См. C-031.
3. В уже существующем коде Wallet хранит внутренние токены; рубли — внешний платёж и курс; Stars — отдельная платёжная единица. Сначала согласовать финансовый контракт, не переписывать ledger.
4. Mini App read-mostly, а не полный продукт; Admin Edition в Telegram имеет process-local password session и не авторизует Mini App.
5. Старый документ AS_IS_ARCHITECTURE зафиксировал риск публичной генерации после пополнения в прежнем SHA. PR #17 изменил public image policy и сообщил мок-E2E, поэтому риск проверять заново на точном текущем SHA, не объявлять прежний дефект доказанно сохраняющимся.

## Что изменено в данном документарном прогоне
Подготовлены [инвентаризация исходников](audit/VANKHU21_IMPLEMENTATION_BASELINE.md), [протокол веток](coordination/BRANCH_INTEGRATION_PROTOCOL.md), [конструктор промптов](codex/PROMPT_FACTORY.md), [доступные задачи](codex/NEXT_TASK_PROMPTS.md), [контракт Stars](contracts/TELEGRAM_STARS_CHANNEL.md); исходный код и личные workplans не тронуты.

## Следующий безопасный шаг
Согласовать документарный PR #18 с владельцем и вторым разработчиком. Отдельно выполнить read-only PROMPT-00: граф PR #1/#8–#17, последовательность приемки и регрессии. Не начинать разработку нового wallet/miniapp/providers поверх пустой main без интеграционной базы. После merge — сверка локального main целиком по CONTRIBUTING.md, с тестами на принятом SHA.
