from ai.schemas import SalesQAResult
from database.repositories import StatsSnapshot


def format_analysis(result: SalesQAResult) -> str:
    return "\n".join(
        [
            f"📊 <b>Оценка: {result.score}/100</b>",
            "",
            f"🎯 <b>Вероятность продажи: {result.sale_probability}%</b>",
            "",
            f"🧾 <b>Summary:</b>\n{escape(result.summary)}",
            "",
            section("✅ Сильные стороны", result.strengths),
            "",
            section("❌ Ошибки", result.mistakes),
            "",
            section("⚠️ Потерянные моменты", result.missed_opportunities),
            "",
            section("📌 Рекомендации", result.recommendations),
            "",
            "<b>Детализация:</b>",
            criteria_line("Приветствие", result.criteria_scores.greeting),
            criteria_line("Выявление потребности", result.criteria_scores.needs_discovery),
            criteria_line("Вежливость", result.criteria_scores.politeness),
            criteria_line("Инициативность", result.criteria_scores.speed_and_initiative),
            criteria_line("Возражения", result.criteria_scores.objections_handling),
            criteria_line("Дожим", result.criteria_scores.follow_up_pressure),
            criteria_line("Закрытие", result.criteria_scores.close_to_action),
            criteria_line("Эмоц. контакт", result.criteria_scores.emotional_contact),
            criteria_line("Грамотность", result.criteria_scores.literacy),
            criteria_line("Структура продаж", result.criteria_scores.sales_structure),
        ]
    )


def format_stats(stats: StatsSnapshot) -> str:
    top_mistakes = "\n".join(f"• {escape(name)} — {count}" for name, count in stats.top_mistakes) or "• Пока нет данных"
    best = format_manager_score(stats.best_manager)
    worst = format_manager_score(stats.worst_manager)
    return "\n".join(
        [
            "📈 <b>Sales QA Stats</b>",
            "",
            f"Проверок: <b>{stats.total_analyses}</b>",
            f"Средний score: <b>{stats.average_score:.1f}/100</b>",
            f"Лучший менеджер: <b>{escape(best)}</b>",
            f"Худший менеджер: <b>{escape(worst)}</b>",
            "",
            "<b>Топ ошибок:</b>",
            top_mistakes,
        ]
    )


def section(title: str, items: list[str]) -> str:
    body = "\n".join(f"• {escape(item)}" for item in items) if items else "• Не выявлено"
    return f"<b>{title}:</b>\n{body}"


def criteria_line(label: str, value: int) -> str:
    return f"• {label}: <b>{value}/10</b>"


def format_manager_score(value: tuple[str, float] | None) -> str:
    if not value:
        return "нет данных"
    name, score = value
    return f"{name} ({score:.1f})"


def escape(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
