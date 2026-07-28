from __future__ import annotations

from app.keyboards.admin import admin_menu, admin_navigation
from app.keyboards.game import card_actions, intensity_menu, level_menu, main_menu
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
    assert "Закрытые темы: выключены" in off_texts
    assert "Закрытые темы: включены" in on_texts


def test_game_keyboards_have_main_menu_and_dynamic_modes():
    assert "game:home" in _callbacks(level_menu())
    assert "game:home" in _callbacks(intensity_menu(3))
    assert "game:home" in _callbacks(card_actions(1, True))
    texts = [button.text for row in main_menu(allow_level_4=True, hard_enabled=True).inline_keyboard for button in row]
    assert "Уровень 4: включен" in texts
    assert "Жесткий режим: включен" in texts


def test_inventory_keyboard_displays_frequency_and_menu_return():
    markup = inventory_menu([{"code": "oil", "name": "Масло"}], {"oil": 3})
    texts = [button.text for row in markup.inline_keyboard for button in row]
    assert "Масло: часто" in texts
    assert "game:home" in _callbacks(markup)
