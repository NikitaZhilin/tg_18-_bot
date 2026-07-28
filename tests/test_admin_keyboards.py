from __future__ import annotations

from app.keyboards.admin import admin_menu, admin_navigation
from app.keyboards.game import (
    card_actions,
    intensity_menu,
    level_menu,
    main_menu,
    main_menu_for_status,
)
from app.keyboards.inventory import inventory_menu


def _callbacks(markup) -> set[str]:
    return {
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data
    }


def test_admin_navigation_returns_to_admin_and_main_menu():
    callbacks = _callbacks(admin_navigation())
    assert "admin:menu" in callbacks
    assert "admin:home" in callbacks


def test_admin_menu_has_main_menu_return():
    assert "admin:home" in _callbacks(admin_menu())


def test_restricted_button_shows_current_state():
    off_texts = [button.text for row in admin_menu(restricted_enabled=False).inline_keyboard for button in row]
    on_texts = [button.text for row in admin_menu(restricted_enabled=True).inline_keyboard for button in row]
    assert "Экстрим: доступ закрыт" in off_texts
    assert "Экстрим: доступ открыт" in on_texts


def test_game_keyboards_have_main_menu_and_dynamic_modes():
    assert "game:home" in _callbacks(level_menu())
    assert "game:home" in _callbacks(intensity_menu(3))
    assert "game:home" in _callbacks(card_actions(1, True))
    assert "game:replace" in _callbacks(card_actions(1, True))
    texts = [
        button.text
        for row in main_menu(
            restricted_enabled=True,
            enabled_levels=(3, 4),
        ).inline_keyboard
        for button in row
    ]
    assert not any(text.startswith("Уровень 4:") for text in texts)
    assert not any(text.startswith("Жесткий режим:") for text in texts)
    assert "Экстрим" in texts
    assert any(text.startswith("Уровни по умолчанию: Секс, BDSM") for text in texts)
    assert "game:level:4" in _callbacks(level_menu())
    assert "game:intensity:4:hard" in _callbacks(intensity_menu(4))


def test_status_menu_preserves_active_turn_and_restricted_access():
    markup = main_menu_for_status(
        {
            "active": True,
            "has_active_turn": True,
            "restricted_content": True,
            "enabled_levels": (3, 4),
        }
    )
    texts = [button.text for row in markup.inline_keyboard for button in row]
    assert "Продолжить текущую карточку" in texts
    assert "Экстрим" in texts
    assert "Уровни по умолчанию: Секс, BDSM" in texts


def test_inventory_keyboard_displays_frequency_and_menu_return():
    markup = inventory_menu([{"code": "oil", "name": "Масло"}], {"oil": 3})
    texts = [button.text for row in markup.inline_keyboard for button in row]
    assert "Масло: часто" in texts
    assert "game:home" in _callbacks(markup)
