# RISKS AND LIMITATIONS

- План DESIGN/PROCESS PROPOSAL, owner assignments и normative changes ещё не приняты; peer review vankhu21 и независимый ChatGPT verdict PENDING.
- Main не содержит application code, все изученные PR открыты. Слияние не выполнялось. До integration новое feature задание зависит от соответствующего IN gate, а не от факта наличия кода.
- Планировочный clone доступен на этой машине; чужой компьютер не доступен. Whole-build runtime sync/health на обеих машинах NOT_PERFORMED.
- Actual deployed SHA, external tokens/accounts/DNS/HTTPS и provider/payment access не проверены. Historical reports не доказательство текущего стенда. Нет новых платных генераций/реальных платежей.
- Ветка audit-artifacts отсутствовала на snapshot. Bootstrap protocol подготовлен; создание/слияние/archive transfer не выполнены. Рабочий пакет публикуется в Draft PR до долгосрочного archive, статус ARCHIVE_PENDING.
- GitHub workflow query возвращает только первую страницу PR-triggered runs; это не полный исторический Actions архив. Сохранены точные run URLs каждого relevant head.
- Donor AI-SHOP-BOT private source не извлекался повторно в этой задаче; source-frozen foundation mapping — reference, RF-01 требует новый authorised read перед адаптацией.
- Относительные effort 142/121 различаются примерно на17%; Burn2288 несёт больше shared-core/ops complexity, vankhu21 больше UI/manual acceptance и author integration. Это не измеренные часы и не обещание сроков. После IN-19 оба уточняют размеры, не меняя author ownership без review.
- Схема/локальный checker доказывают структуру/связность/hash, не сетевую доступность всех source links, runtime или отсутствие всех потенциальных секретов. Публикуемые artifacts состоят из source paths/IDs/commit hashes и безопасных summary, без сырых private logs.
