# Tests

Локально: check_docs.py — 65 документов до добавления пакета; check_planning.py — 81 задача, 27 направлений, 31 контракт, DAG без циклов, 193 task anchors, семь отрицательных и два положительных сценария; git diff --check — exit 0. Final CI и SHA будут внесены после публикации.

Вердикт исходного аудита: [PARTIAL](https://github.com/Burn2288/FLOW-BRIDGE-GEN/pull/19#issuecomment-6917957969). Ревизия FIX-01 дополняет историю, не заменяет предыдущий пакет. Независимое решение по FIX-01 ожидается.

Locally tested tree matches GitHub content SHA `de1fa29fdee06e0c106507855f8e312c60d6c2e1`; seven negative and two positive parallel fixtures passed; 75 Markdown files; no application tests. GitHub Actions: NOT_PROVEN, no run returned by connector.

Обновление: [Documentation CI](https://github.com/Burn2288/FLOW-BRIDGE-GEN/actions/runs/43880313962) completed/success на SHA `fc83392d6de3d4d7959946659af9e6daf60faca2`. Предыдущее состояние ожидания CI сохраняется как история. SHA публикационной ревизии и её CI указаны в PR #19.
