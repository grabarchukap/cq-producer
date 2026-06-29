from enum import Enum


class CaseState(str, Enum):
    IDLE           = "idle"
    QUESTION       = "question"
    EXTRA          = "extra"
    CONFIRM_SKIP   = "confirm_skip"
    CONFIRM_DONE   = "confirm_done"
    CONFIRM_CANCEL = "confirm_cancel"


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
    AWAIT_EDIT_TEXT      = "await_edit_text"
    AWAIT_CASE_Q_ADD     = "await_case_q_add"
    AWAIT_CASE_Q_EDIT    = "await_case_q_edit"
    AWAIT_NOTIFIER_ADD   = "await_notifier_add"
    AWAIT_DRAFT_PROMPT   = "await_draft_prompt"
