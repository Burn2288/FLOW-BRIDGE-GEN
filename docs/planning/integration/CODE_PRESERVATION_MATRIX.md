# CODE PRESERVATION MATRIX

Сравнение blob — только идентичность содержимого на текущем дереве #17, не доказательство эквивалентности изменённого файла или runtime. Полные результаты: [preservation-evidence.json](preservation-evidence.json); range-diff: [#4](range-diff-pr4-pr8.txt), [#6](range-diff-pr6-pr8.txt), [#7](range-diff-pr7-pr8.txt).

| PR | Работа | HEAD предок #17 | Совпадающие source blobs / paths | Риск / решение |
| --- | --- | --- | --- | --- |
| [#2](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/2) | S0: импорт тестового стенда и проверка доставки изображений | True | 99/126 | Сохранить ancestry и review изменений на каждом шаге. |
| [#4](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/4) | S1-TG-RECOVERY: повторная выдача сохранённого изображения | True | 5/6 | Сохранить ancestry и review изменений на каждом шаге. |
| [#6](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/6) | P0: проверка целостности PNG и JPEG до сохранения | True | 4/7 | Сохранить ancestry и review изменений на каждом шаге. |
| [#7](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/7) | P0 smoke: combined image recovery and validation | True | 9/14 | Сохранить ancestry и review изменений на каждом шаге. |
| [#8](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/8) | Интеграция генерации и восстановления изображений | True | 118/142 | Сохранить ancestry и review изменений на каждом шаге. |
| [#9](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/9) | Veo 3.1: текст в видео с подтверждением стоимости | True | 2/9 | Сохранить ancestry и review изменений на каждом шаге. |
| [#10](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/10) | Подключить отдельный тестовый агрегатор AnyModel | True | 1/7 | Сохранить ancestry и review изменений на каждом шаге. |
| [#11](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/11) | Добавить FIBO 2 и разделы AnyModel | True | 1/10 | Сохранить ancestry и review изменений на каждом шаге. |
| [#12](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/12) | Подключить закрытый видеопилот Grok 1.5 через AnyModel | True | 1/11 | Сохранить ancestry и review изменений на каждом шаге. |
| [#13](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/13) | Add closed AnyModel text-to-speech pilot | True | 2/11 | Сохранить ancestry и review изменений на каждом шаге. |
| [#14](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/14) | Add DarkFlow Gen Telegram welcome screen | True | 3/14 | Сохранить ancestry и review изменений на каждом шаге. |
| [#15](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/15) | Показывать отдельный статус выполнения задач в Telegram | True | 2/15 | Сохранить ancestry и review изменений на каждом шаге. |
| [#16](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/16) | Admin Edition: общая оценка AnyModel и CLODEX, ручные тарифы | True | 82/89 | Сохранить ancestry и review изменений на каждом шаге. |
| [#17](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/17) | Mini App на чтение и проверка пополнения с единым конфигом | True | 23/23 | Сохранить ancestry и review изменений на каждом шаге. |

ProviderRegistry `aggregate.py`, Pricing/model_policy, TaskLaunch/worker, wallet/ledger, Stars/Platega, Telegram admin, Mini App и media/test suites присутствуют в candidate #17; факт наличия не доказывает сохранения каждого исторического поведения. Для ранних пилотов и изменённых blobs нужен конкретный semantic review по тестам, patch-id/range-diff и решение vankhu21. До него полная сохранность **NOT_PROVEN**. Никакой компонент здесь не переписан.

Отдельно `git merge-base --is-ancestor` подтвердил, что HEAD каждого раннего PR #2, #4, #6 и #7 является предком HEAD #8. Следовательно, отдельный перенос тех же коммитов не нужен при сохранении этой ancestry; изменённые после них файлы всё ещё требуют semantic review.

Автоматическая сверка имён тестов ранних PR и #17: [historical-test-names.json](historical-test-names.json). Найдено одно отсутствующее прежнее имя: `test_private_access_denied_before_registration` из #2. В #17 есть тест `test_non_admin_in_private_pilot_can_accept_terms_and_open_user_menu` с другим ожидаемым поведением. Это конкретное изменение политики доступа, а не доказанный дефект; его намеренность, совместимость и разрешение на сохранение нового поведения требуют решения владельца и проверки vankhu21. Сравнение имён остальных тестов не доказывает неизменность их тела.

## IN-01-FIX-01 — открытый access gate

[ADR PROPOSED](PRIVATE_PILOT_ACCESS_ADR.md), [матрица сценариев](ACCESS_CONTROL_TEST_MATRIX.md), [semantic review и вопросы vankhu21](SEMANTIC_PRESERVATION_REVIEW.md). Режим private в #17 не доказывает запрет outsider до identity; owner approval и peer review NOT_PROVEN. После утверждения отдельная кодовая задача; этот PR не меняет runtime. До решения не считать поведенческую сохранность или командное согласование подтверждёнными.
