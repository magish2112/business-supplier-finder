"""Шаги сценария подбора поставщиков (MVP)."""

from enum import Enum


class OrchestrationStep(str, Enum):
    INTAKE = "INTAKE"
    LOCAL_MATCH = "LOCAL_MATCH"
    AWAIT_USER_LOCAL_CONFIRM = "AWAIT_USER_LOCAL_CONFIRM"
    WEB_DISCOVERY = "WEB_DISCOVERY"
    PROPOSE = "PROPOSE"
    AWAIT_SEND_CONFIRM = "AWAIT_SEND_CONFIRM"
    DONE = "DONE"
