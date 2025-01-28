from http import HTTPStatus

from fastapi import APIRouter

from app.database.engine import check_availability
from app.models.app_status import AppStatus


router = APIRouter()


@router.get("/status", status_code=HTTPStatus.OK)
def status() -> AppStatus:
    return AppStatus(database=check_availability())
