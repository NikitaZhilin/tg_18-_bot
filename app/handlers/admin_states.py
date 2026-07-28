from aiogram.fsm.state import State, StatesGroup


class AdminAddCard(StatesGroup):
    category = State()
    level = State()
    intensity = State()
    title = State()
    text = State()
    required_items = State()
    timer = State()
    risk_tags = State()
    pose_family = State()
    pose_difficulty = State()
    space_required = State()
    body_load = State()
    preview = State()
    search = State()
    import_file = State()
    edit_text = State()
    restricted_password = State()
