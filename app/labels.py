from __future__ import annotations

from collections.abc import Mapping


LEVEL_NAMES = {
    1: "Флирт",
    2: "Разогрев",
    3: "Секс",
    4: "BDSM",
}

CATEGORY_NAMES = {
    "question": "Вопрос",
    "task": "Задание",
    "pose": "Поза",
    "desire": "Желание",
    "penalty": "Штраф",
}

INTENSITY_NAMES = {
    "light": "легкая",
    "medium": "средняя",
    "hard": "жесткая",
}

REVIEW_STATUS_NAMES = {
    "draft": "Черновик",
    "needs_review": "На доработке",
    "approved": "Одобрена",
    "disabled": "Отключена",
}

ITEM_MODE_NAMES = {
    "none": "Не использовать",
    "optional": "Можно добавить",
    "required": "Обязательно подобрать",
}

YES_NO_NAMES = {
    0: "Нет",
    1: "Да",
}

POSE_DIFFICULTY_NAMES = {
    "easy": "легкая",
    "medium": "средняя",
    "hard": "сложная",
}

SPACE_NAMES = {
    "bed": "кровать",
    "floor": "пол",
    "chair": "стул",
    "wall": "стена",
    "any": "любое место",
}

BODY_LOAD_NAMES = {
    "low": "низкая",
    "medium": "средняя",
    "high": "высокая",
}

POSE_FAMILY_NAMES = {
    "seated": "сидя",
    "side": "на боку",
    "reclined": "лежа",
    "face_to_face": "лицом к лицу",
    "top": "партнер сверху",
    "edge": "на краю кровати",
    "chair": "на стуле",
    "standing": "стоя",
    "support": "с опорой",
    "control": "контроль темпа",
    "hands": "положение рук",
    "tempo": "смена темпа",
    "stillness": "неподвижность",
    "protocol": "правила и разрешения",
    "sensory": "сенсорная",
    "role": "ролевая",
    "endurance": "на выдержку",
    "control_seated": "контроль темпа сидя",
    "control_wall": "контроль темпа у стены",
}

RISK_TAG_NAMES = {
    "power_exchange": "Обмен контролем",
    "roleplay": "Ролевая сцена",
    "command_language": "Командный тон",
    "denial_play": "Ограничение инициативы",
    "consent_check": "Частая проверка согласия",
    "pose_control": "Контроль позы",
    "sensory_deprivation": "Сенсорные ограничения",
    "food": "Еда и напитки",
    "toys": "Интимные игрушки",
    "fisting": "Фистинг",
    "advanced_insertion": "Сложное проникновение",
    "urethral_play": "Уретральная практика",
    "sterile_equipment": "Стерильный реквизит",
    "advanced_practice": "Практика для опытной пары",
    "aftercare": "Спокойное завершение",
    "injury": "Боль или травма",
    "medical_condition": "Ограничения по здоровью",
    "urinary_symptoms": "Симптомы мочевыводящих путей",
    "no_quick_release_restraint": "Фиксация",
    "unbounded_humiliation": "Унижение",
    "unsafe_wax": "Горячий воск",
}

COLLECTION_NAMES = {
    "base_tasks": "Основные карточки",
    "kamasutra_inspired_poses": "Позы",
    "restricted_content": "Экстрим",
}


def reverse_labels(values: Mapping[object, str]) -> dict[str, object]:
    return {label.casefold(): code for code, label in values.items()}


def code_from_label(
    value: object,
    labels: Mapping[object, str],
    *,
    allow_code: bool = True,
) -> object | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if allow_code and raw in labels:
        return raw
    return reverse_labels(labels).get(raw.casefold())


def label_for(value: object, labels: Mapping[object, str], default: str | None = None) -> str:
    if value in labels:
        return labels[value]
    return default if default is not None else str(value or "")
