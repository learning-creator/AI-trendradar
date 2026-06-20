# coding=utf-8
"""
CLI 命令模块

独立的 CLI 子命令：doctor、test-notification、show-schedule、version-check
"""

from .doctor import run_doctor
from .test_notification import run_test_notification
from .status import handle_status_commands
from .version import check_all_versions
from .trend_summary import run_trend_summary

__all__ = [
    "run_doctor",
    "run_test_notification",
    "handle_status_commands",
    "check_all_versions",
    "run_trend_summary",
]
