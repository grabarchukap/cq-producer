from enum import Enum


class UserState(str, Enum):
    IDLE = "idle"
    PROCESSING = "processing"
    EDITING = "editing"


class AdminState(str, Enum):
    IDLE = "idle"
    AWAIT_PASSWORD = "await_password"
    MENU = "menu"
    AWAIT_TOV_NAME = "await_tov_name"
    AWAIT_TOV_STYLE = "await_tov_style"
    AWAIT_EXAMPLE = "await_example"
    SELECT_DELETE_TOV = "select_delete_tov"
    SELECT_DEL_EXAMPLE = "select_del_example"
    AWAIT_ADD_USER = "await_add_user"
    AWAIT_DEL_USER = "await_del_user"
    AWAIT_EDIT_TEXT = "await_edit_text"
