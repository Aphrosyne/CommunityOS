"""config.py 环境变量解析测试

依据:
    docs/technical-debt.md L2
    bot/services/config.py 的 _parse_int_env / _parse_int_list_env

覆盖:
    - 合法 ADMINS / OWNER / BOT_QQ 解析
    - 空 ADMINS 返回空列表
    - 非法 ADMINS 抛带上下文的 ValueError
    - 非法 OWNER / BOT_QQ 抛带上下文的 ValueError
"""
import importlib
import sys

import pytest


def _reload_config_with_env(monkeypatch, env: dict[str, str]):
    """用指定环境变量重新加载 services.config 模块

    config 在模块加载时执行环境变量解析，需重新 import 才能生效。
    """
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    # 清除已加载的 config 模块，强制重新加载
    if "services.config" in sys.modules:
        del sys.modules["services.config"]
    if "services" in sys.modules:
        del sys.modules["services"]
    return importlib.import_module("services.config")


def test_parse_valid_admins(monkeypatch):
    """合法 ADMINS 逗号分隔列表正确解析"""
    config = _reload_config_with_env(monkeypatch, {
        "OWNER": "123456",
        "ADMINS": "111,222,333",
        "BOT_QQ": "999999",
    })
    assert config.OWNER == 123456
    assert config.ADMINS == [111, 222, 333]
    assert config.BOT_QQ == 999999


def test_parse_empty_admins(monkeypatch):
    """空 ADMINS 返回空列表（不报错）"""
    config = _reload_config_with_env(monkeypatch, {
        "OWNER": "0",
        "ADMINS": "",
        "BOT_QQ": "0",
    })
    assert config.OWNER == 0
    assert config.ADMINS == []
    assert config.BOT_QQ == 0


def test_parse_admins_with_spaces(monkeypatch):
    """ADMINS 含空格自动 strip"""
    config = _reload_config_with_env(monkeypatch, {
        "OWNER": "100",
        "ADMINS": " 111 , 222 , 333 ",
        "BOT_QQ": "200",
    })
    assert config.ADMINS == [111, 222, 333]


def test_parse_invalid_admins_raises_with_context(monkeypatch):
    """L2: 非法 ADMINS 抛 ValueError 并包含变量名和非法值"""
    with pytest.raises(ValueError) as exc_info:
        _reload_config_with_env(monkeypatch, {
            "OWNER": "100",
            "ADMINS": "111,abc,333",
            "BOT_QQ": "200",
        })
    msg = str(exc_info.value)
    assert "ADMINS" in msg
    assert "abc" in msg
    assert "整数" in msg


def test_parse_invalid_owner_raises_with_context(monkeypatch):
    """L2: 非法 OWNER 抛 ValueError 并包含变量名和非法值"""
    with pytest.raises(ValueError) as exc_info:
        _reload_config_with_env(monkeypatch, {
            "OWNER": "not_a_number",
            "ADMINS": "",
            "BOT_QQ": "0",
        })
    msg = str(exc_info.value)
    assert "OWNER" in msg
    assert "not_a_number" in msg
    assert "整数" in msg


def test_parse_invalid_bot_qq_raises_with_context(monkeypatch):
    """L2: 非法 BOT_QQ 抛 ValueError 并包含变量名和非法值"""
    with pytest.raises(ValueError) as exc_info:
        _reload_config_with_env(monkeypatch, {
            "OWNER": "100",
            "ADMINS": "",
            "BOT_QQ": "abc",
        })
    msg = str(exc_info.value)
    assert "BOT_QQ" in msg
    assert "abc" in msg


def test_parse_missing_env_uses_defaults(monkeypatch):
    """未设置环境变量时使用默认值"""
    # 清除环境变量
    monkeypatch.delenv("OWNER", raising=False)
    monkeypatch.delenv("ADMINS", raising=False)
    monkeypatch.delenv("BOT_QQ", raising=False)
    config = _reload_config_with_env(monkeypatch, {})
    assert config.OWNER == 0
    assert config.ADMINS == []
    assert config.BOT_QQ == 0
