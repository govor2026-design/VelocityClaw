from __future__ import annotations

from typing import Dict


HIGH_LEVEL_MODES: Dict[str, dict] = {
    "analyze_repo": {
        "goal": "Проанализируй структуру репозитория, выдели ключевые модули, риски и точки улучшения.",
        "workflow": "Сначала inspection-first: git.inspect -> fs/code inspection -> summary.",
        "verification": "Подтверди выводы ссылкой на реальные модули, файлы, тесты или workflow patterns.",
    },
    "fix_bug": {
        "goal": "Найди вероятную причину бага, предложи минимальный фикс и подготовь проверку исправления.",
        "workflow": "Сначала reproduction/inspection: test.run или code.read_symbol -> затем минимальный patch -> затем verification.",
        "verification": "Покажи, как будет проверяться фикс: tests, repro steps или targeted validation.",
    },
    "implement_feature": {
        "goal": "Реализуй новую фичу по описанию, минимально затрагивая лишний код, и подготовь проверку результата.",
        "workflow": "Сначала inspect current repo shape and related modules -> then code changes -> then tests or validation.",
        "verification": "Опиши проверку результата через тесты, run path или expected behavior.",
    },
    "write_tests": {
        "goal": "Добавь недостающие тесты для указанного кода и опиши, что именно они покрывают.",
        "workflow": "Сначала inspect target code and existing tests -> then add focused tests -> then run targeted verification.",
        "verification": "Укажи покрываемые сценарии и why these tests matter.",
    },
    "repair_failed_tests": {
        "goal": "Исправь код до прохождения указанных тестов, сохраняя минимальность правок.",
        "workflow": "Сначала run/read failing tests -> inspect relevant symbol/module -> minimal patch -> rerun tests.",
        "verification": "Проверь именно тот failing path, который был в исходной проблеме.",
    },
    "refactor_module": {
        "goal": "Проведи безопасный рефакторинг модуля, сохрани поведение и предложи способ верификации.",
        "workflow": "Сначала inspect module boundaries and tests -> then refactor -> then behavior verification.",
        "verification": "Подчеркни, как сохраняется поведение и чем это подтверждается.",
    },
    "prepare_pr_summary": {
        "goal": "Подготовь краткое, но технически точное summary изменений для pull request.",
        "workflow": "Сначала inspect git diff and changed modules -> then summarize user-visible and technical impact.",
        "verification": "Summary must reflect actual code changes, not generic claims.",
    },
    "summarize_architecture": {
        "goal": "Опиши архитектуру проекта, связи между модулями и ключевые технические риски.",
        "workflow": "Сначала inspect repo structure and important entrypoints -> then produce architecture summary.",
        "verification": "Архитектурные выводы должны опираться на реальные модули и boundaries.",
    },
}


def build_mode_task(mode: str, task: str) -> str:
    spec = HIGH_LEVEL_MODES.get(mode)
    if not spec:
        raise ValueError(f"Unknown mode: {mode}")
    return (
        f"[{mode}] {spec['goal']}\n\n"
        f"Repo workflow hint: {spec['workflow']}\n"
        f"Verification focus: {spec['verification']}\n\n"
        f"Исходная задача: {task}"
    )
