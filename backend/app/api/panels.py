from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field

from app.panels import GRID_COLS, PanelStore, Widget

router = APIRouter(prefix="/panels", tags=["painéis"])


def _store(request: Request) -> PanelStore:
    return request.app.state.panels


class PanelIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    widgets: list[Widget] = Field(default_factory=list)


@router.get("")
def list_panels(request: Request) -> dict:
    return {"grid_cols": GRID_COLS, "panels": _store(request).list()}


@router.post("", status_code=201)
def create_panel(body: PanelIn, request: Request) -> dict:
    return _store(request).create(body.name, body.widgets)


@router.get("/{panel_id}")
def get_panel(panel_id: int, request: Request) -> dict:
    return _store(request).get(panel_id)


@router.put("/{panel_id}")
def update_panel(panel_id: int, body: PanelIn, request: Request) -> dict:
    return _store(request).update(panel_id, body.name, body.widgets)


@router.delete("/{panel_id}", status_code=204)
def delete_panel(panel_id: int, request: Request) -> Response:
    _store(request).delete(panel_id)
    return Response(status_code=204)
