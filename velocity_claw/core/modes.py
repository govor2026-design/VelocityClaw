from __future__ import annotations

from typing import Dict


HIGH_LEVEL_MODES: Dict[str, str] = {
    "analyze_repo": "Проанализируй структуру репозитория, выдели ключевые модули, риски и точки улучшения.",
    "fix_bug": "Найди вероятную причину бага, предложи минимальный фикс и подготовь проверку исправления.",
    "implement_feature": "Реализуй новую фичу по описанию, минимально затрагивая лишний код, и подготовь проверку результата.",
    "write_tests": "Добавь недостающие тесты для указанного кода и опиши, что именно они покрывают.",
    "repair_failed_tests": "Исправь код до прохождения указанных тестов, сохраняя минимальность правок.",
    "refactor_module": "Проведи безопасный рефакторинг модуля, сохрани поведение и предложи способ верификации.",
    "prepare_pr_summary": "Подготовь краткое, но технически точное summary изменений для pull request.",
    "summarize_architecture": "Опиши архитектуру проекта, связи между модулями и ключевые технические риски.",
}


def build_mode_task(mode: str, task: str) -> str:
    prefix = HIGH_LEVEL_MODES.get(mode)
    if not prefix:
        raise ValueError(f"Unknown mode: {mode}")
    return f"[{mode}] {prefix}\n\nИсходная задача: {task}"
