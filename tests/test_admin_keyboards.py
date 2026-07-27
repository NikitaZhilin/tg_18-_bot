from __future__ import annotations

from app.keyboards.admin import admin_menu, admin_navigation


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
