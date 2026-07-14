"""Bot control endpoints — Start / Stop / Pause / Resume / Restart /
Reset Session / Emergency Stop / Manual Refresh."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..bot.controller import InvalidTransition
from .state import get_controller

router = APIRouter()


@router.post("/start")
def start_bot():
    try:
        return get_controller().start()
    except InvalidTransition as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/stop")
def stop_bot():
    try:
        return get_controller().stop()
    except InvalidTransition as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/pause")
def pause_bot():
    try:
        return get_controller().pause()
    except InvalidTransition as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/resume")
def resume_bot():
    try:
        return get_controller().resume()
    except InvalidTransition as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/restart")
def restart_bot():
    try:
        return get_controller().restart()
    except InvalidTransition as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/reset-session")
def reset_session():
    return get_controller().reset_session()


@router.post("/emergency-stop")
def emergency_stop():
    try:
        return get_controller().emergency_stop()
    except InvalidTransition as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/refresh")
def manual_refresh():
    return get_controller().manual_refresh()


@router.get("/status")
def status():
    return get_controller().status()
