import re

from ai.schemas import CriteriaScores, SalesQAResult


QUESTION_WORDS = ("?", "как", "что", "когда", "для чего", "какой", "какая", "сколько", "почему")
PRICE_WORDS = ("цена", "стоимость", "стоит", "прайс", "тенге", "руб", "₸", "₽", "$")
OBJECTION_WORDS = ("дорого", "подумаю", "не сейчас", "сомневаюсь", "дешевле", "позже", "нет")
CLOSE_WORDS = ("оформим", "забронируем", "записать", "созвон", "оплата", "счет", "когда удобно", "давайте")
GREETING_WORDS = ("здравствуйте", "добрый", "привет", "ассаламу", "сәлем")
POLITE_WORDS = ("пожалуйста", "спасибо", "благодарю", "подскажите", "буду рад")


class RuleBasedSalesQAAnalyzer:
    def analyze(self, ocr_text: str) -> SalesQAResult:
        text = normalize(ocr_text)
        messages = [line.strip() for line in re.split(r"[\n\r]+", ocr_text) if line.strip()]

        greeting = score_contains(text, GREETING_WORDS, 8, 3)
        needs = score_needs(text)
        politeness = score_contains(text, POLITE_WORDS, 8, 5)
        initiative = score_contains(text, CLOSE_WORDS + QUESTION_WORDS, 7, 4)
        objections = score_objections(text)
        follow_up = score_contains(text, ("напомню", "актуально", "что скажете", "готовы", "вернуться"), 7, 2)
        close = score_contains(text, CLOSE_WORDS, 8, 2)
        emotional = score_contains(text, ("понимаю", "важно", "удобно", "помогу", "подберем"), 7, 3)
        literacy = score_literacy(text)
        structure = round((greeting + needs + initiative + objections + close) / 5)

        criteria = CriteriaScores(
            greeting=greeting,
            needs_discovery=needs,
            politeness=politeness,
            speed_and_initiative=initiative,
            objections_handling=objections,
            follow_up_pressure=follow_up,
            close_to_action=close,
            emotional_contact=emotional,
            literacy=literacy,
            sales_structure=structure,
        )
        score = round(sum(criteria.model_dump().values()))
        sale_probability = max(5, min(95, round(score * 0.82)))

        mistakes = build_mistakes(criteria, text)
        recommendations = build_recommendations(criteria)

        return SalesQAResult(
            score=score,
            sale_probability=sale_probability,
            summary=(
                "OpenAI Vision сейчас недоступен или нет баланса, поэтому это бесплатная OCR-оценка "
                "по правилам продаж. Для точного разбора скриншотов пополните OpenAI API billing."
            ),
            strengths=build_strengths(criteria, messages),
            mistakes=mistakes,
            missed_opportunities=build_missed(criteria, text),
            recommendations=recommendations,
            criteria_scores=criteria,
        )


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()


def score_contains(text: str, words: tuple[str, ...], yes: int, no: int) -> int:
    return yes if any(word in text for word in words) else no


def score_needs(text: str) -> int:
    question_hits = sum(1 for word in QUESTION_WORDS if word in text)
    price_early = any(word in text[:700] for word in PRICE_WORDS)
    score = min(10, 2 + question_hits * 2)
    if price_early and score < 7:
        score = max(1, score - 2)
    return score


def score_objections(text: str) -> int:
    has_objection = any(word in text for word in OBJECTION_WORDS)
    if not has_objection:
        return 4
    has_answer = any(word in text for word in ("понимаю", "потому", "выгода", "гарантия", "можем", "вариант"))
    return 7 if has_answer else 2


def score_literacy(text: str) -> int:
    if not text:
        return 1
    bad_spacing = text.count("  ")
    very_short = len(text) < 120
    return 5 if very_short else max(4, 9 - bad_spacing)


def build_strengths(criteria: CriteriaScores, messages: list[str]) -> list[str]:
    strengths = []
    if criteria.greeting >= 7:
        strengths.append("есть корректное начало контакта")
    if criteria.politeness >= 7:
        strengths.append("тон общения выглядит вежливым")
    if criteria.close_to_action >= 7:
        strengths.append("есть попытка закрыть клиента на следующий шаг")
    if len(messages) >= 6:
        strengths.append("диалог достаточно развернутый для первичной оценки")
    return strengths or ["виден базовый контакт с клиентом"]


def build_mistakes(criteria: CriteriaScores, text: str) -> list[str]:
    mistakes = []
    if criteria.needs_discovery <= 4:
        mistakes.append("слабое выявление потребности")
    if criteria.close_to_action <= 4:
        mistakes.append("нет четкого закрытия на действие")
    if criteria.objections_handling <= 4 and any(word in text for word in OBJECTION_WORDS):
        mistakes.append("возражения клиента не обработаны достаточно убедительно")
    if any(word in text[:700] for word in PRICE_WORDS) and criteria.needs_discovery <= 5:
        mistakes.append("цена могла быть отправлена слишком рано, до диагностики")
    return mistakes or ["критичных ошибок по OCR-правилам не найдено"]


def build_missed(criteria: CriteriaScores, text: str) -> list[str]:
    missed = []
    if criteria.needs_discovery <= 5:
        missed.append("можно было уточнить задачу, сроки, бюджет и критерии выбора")
    if criteria.emotional_contact <= 4:
        missed.append("не хватило персонализации и эмоционального контакта")
    if "подумаю" in text and criteria.follow_up_pressure <= 4:
        missed.append("после 'подумаю' нужен мягкий следующий шаг или дедлайн")
    return missed or ["явных потерянных моментов OCR не выделил"]


def build_recommendations(criteria: CriteriaScores) -> list[str]:
    recommendations = []
    if criteria.needs_discovery <= 5:
        recommendations.append("задавать 2-3 уточняющих вопроса перед ценой или презентацией")
    if criteria.close_to_action <= 5:
        recommendations.append("заканчивать диалог конкретным действием: звонок, бронь, оплата или встреча")
    if criteria.objections_handling <= 5:
        recommendations.append("обрабатывать сомнения через пользу, кейсы, гарантию или альтернативный вариант")
    recommendations.append("вести клиента по структуре: контакт → диагностика → решение → возражения → следующий шаг")
    return recommendations
