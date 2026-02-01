"""Configuration management for Boring CLI."""

import os
from pathlib import Path
from typing import Optional

import yaml

CONFIG_DIR = Path.home() / ".boring-agents"
CONFIG_FILE = CONFIG_DIR / "config.yaml"


def ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    with open(CONFIG_FILE, "r") as f:
        return yaml.safe_load(f) or {}


def save_config(config: dict) -> None:
    ensure_config_dir()
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(config, f, default_flow_style=False)


def get_value(key: str) -> Optional[str]:
    return load_config().get(key)


def set_value(key: str, value: str) -> None:
    config = load_config()
    config[key] = value
    save_config(config)


def get_server_url() -> Optional[str]:
    return get_value("server_url")


def get_jwt_token() -> Optional[str]:
    return get_value("jwt_token")


def get_bugs_dir() -> Optional[str]:
    return get_value("bugs_dir")


def get_tasklist_guid() -> Optional[str]:
    return get_value("tasklist_guid")


def get_section_guid() -> Optional[str]:
    return get_value("section_guid")


def get_solved_section_guid() -> Optional[str]:
    return get_value("solved_section_guid")


def set_server_url(url: str) -> None:
    set_value("server_url", url)


def set_jwt_token(token: str) -> None:
    set_value("jwt_token", token)


def set_bugs_dir(path: str) -> None:
    set_value("bugs_dir", path)


def set_tasklist_guid(guid: str) -> None:
    set_value("tasklist_guid", guid)


def set_section_guid(guid: str) -> None:
    set_value("section_guid", guid)


def set_solved_section_guid(guid: str) -> None:
    set_value("solved_section_guid", guid)


def get_lark_token() -> Optional[str]:
    return get_value("lark_token")


def set_lark_token(token: str) -> None:
    set_value("lark_token", token)


def get_backend_type() -> Optional[str]:
    return get_value("backend_type") or "lark"


def set_backend_type(backend_type: str) -> None:
    if backend_type not in ["lark", "kanban"]:
        raise ValueError(f"Invalid backend type: {backend_type}")
    set_value("backend_type", backend_type)


def get_kanban_base_url() -> Optional[str]:
    return get_value("kanban_base_url")


def set_kanban_base_url(url: str) -> None:
    set_value("kanban_base_url", url)


def get_kanban_api_key() -> Optional[str]:
    return get_value("kanban_api_key")


def set_kanban_api_key(key: str) -> None:
    set_value("kanban_api_key", key)


def get_kanban_board_id() -> Optional[str]:
    return get_value("kanban_board_id")


def set_kanban_board_id(board_id: str) -> None:
    set_value("kanban_board_id", board_id)


def get_kanban_list_id() -> Optional[str]:
    return get_value("kanban_list_id")


def set_kanban_list_id(list_id: str) -> None:
    set_value("kanban_list_id", list_id)


def get_kanban_done_list_id() -> Optional[str]:
    return get_value("kanban_done_list_id")


def set_kanban_done_list_id(list_id: str) -> None:
    set_value("kanban_done_list_id", list_id)


def is_configured() -> bool:
    config_data = load_config()
    backend_type = config_data.get("backend_type", "lark")
    bugs_dir = config_data.get("bugs_dir")

    if not bugs_dir:
        return False

    if backend_type == "lark":
        return all([config_data.get("server_url"), config_data.get("jwt_token")])
    elif backend_type == "kanban":
        return all([config_data.get("kanban_base_url"), config_data.get("kanban_api_key")])

    return False
