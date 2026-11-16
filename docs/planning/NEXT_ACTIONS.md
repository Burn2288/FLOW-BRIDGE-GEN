# NEXT ACTIONS — после согласования общего плана

Сейчас выполнялась только TASK-PLAN-001. Эти задания не запущены, никто не получил автоматического разрешения на merge/deploy/live spending. [Реестр](MASTER_WORK_BREAKDOWN.md), [решения](DECISIONS_REQUIRED.md), [audit protocol](EVIDENCE_PUBLICATION_PROTOCOL.md).

1. Burn2288: IN-01 — подтвердить текущие SHA/graph/supersession и предложить порядок review; vankhu21 reviewer. Параллельно vankhu21: TA-01 — read-only command/role inventory existing Admin Edition #16, пока IN-01 не принят никаких code changes; это подготовительная read-only часть, её финал зависит от IN-01.
2. Burn2288: IN-02 и IN-18 через установленную docs цепочку, peer review vankhu21. vankhu21: подготовить review evidence IN-08 без ретаргета/merge до IN-02. Оба согласуют AU-01 и D-01/02/04, фиксируют migration ownership.
3. vankhu21: IN-08 → IN-09…IN-17 как отдельные reviewable этапы; Burn2288 reviewer/integration sign-off, не переписывает code коллеги. Burn2288 параллельно DC-01 и AU-01 после IN-18, затем read-only deployment/test profiles. AU-02 — только после принятого AU-01.
4. IN-19: оба автора независимо обновляют полную accepted main на своих машинах и запускают изолированную сборку; недоступная машина NOT_PERFORMED. Burn2288 TQ-01, vankhu21 PC-01. Финансовые schema/DDL edits сериализованы.
5. Image priority: Burn2288 ML-01, vankhu21 IM-01 после PC-01. IM-01 сохраняет штатный adapter и HTTP fixture, один конфиг/DB. После D-06 vankhu21 IM-02 с review Burn2288. Без внешнего доступа — точный blocker, не fake live PASS; независимые offline tasks разрешены, S1 не закрыт.
6. Затем JO-01/02 у Burn2288, vankhu21 готовит UI fixtures/route parity на frozen contracts; широкую реконструкцию не начинать до image proof/конкретного внешнего blocker. Далее выбирать ready задачи по DAG и lock-check, не по номеру эпика.

## Передача персональных планов

В этом PR оба worklists — предложения. После approval Burn2288 переносит свой согласованный worklist в dev/burn2288; vankhu21 сам переносит свой в dev/vankhu21. Каждая передача записывает planning source SHA, target dev baseline/head, SHA сохранённого оригинала из history и подтверждение preservation. Никаких прямых записей Burn2288 в dev/vankhu21.
