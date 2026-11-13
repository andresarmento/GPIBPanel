import asyncio

from fastapi import APIRouter, Request, Response, UploadFile
from pydantic import BaseModel, Field

from app.drivers import identify
from app.drivers.base import InstrumentIO
from app.equipment import MAX_IMAGE_BYTES, EquipmentStore
from app.gpib.bus import GpibBus
from app.gpib.errors import GpibTimeout
from app.gpib.transport import MAX_ADDRESS, MIN_ADDRESS

router = APIRouter(prefix="/equipment", tags=["equipamentos"])


def _store(request: Request) -> EquipmentStore:
    return request.app.state.equipment


class EquipmentIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    address: int = Field(ge=MIN_ADDRESS, le=MAX_ADDRESS)
    driver: str
    notes: str = ""


@router.get("")
def list_equipment(request: Request) -> list[dict]:
    return _store(request).list()


@router.post("", status_code=201)
def create_equipment(body: EquipmentIn, request: Request) -> dict:
    return _store(request).create(**body.model_dump())


@router.get("/{equipment_id}")
def get_equipment(equipment_id: int, request: Request) -> dict:
    return _store(request).get(equipment_id)


@router.put("/{equipment_id}")
def update_equipment(equipment_id: int, body: EquipmentIn, request: Request) -> dict:
    return _store(request).update(equipment_id, **body.model_dump())


@router.delete("/{equipment_id}", status_code=204)
def delete_equipment(equipment_id: int, request: Request) -> Response:
    _store(request).delete(equipment_id)
    return Response(status_code=204)


@router.get("/{equipment_id}/image")
def get_image(equipment_id: int, request: Request) -> Response:
    data, mime = _store(request).get_image(equipment_id)
    # A URL leva ?v=<updated_at>, então cada versão da foto pode ficar em cache
    return Response(data, media_type=mime, headers={"Cache-Control": "private, max-age=31536000, immutable"})


@router.put("/{equipment_id}/image")
def put_image(equipment_id: int, file: UploadFile, request: Request) -> dict:
    data = file.file.read(MAX_IMAGE_BYTES + 1)  # +1 para detectar arquivo grande demais
    return _store(request).set_image(equipment_id, data)


@router.delete("/{equipment_id}/image")
def delete_image(equipment_id: int, request: Request) -> dict:
    return _store(request).clear_image(equipment_id)


@router.post("/{equipment_id}/check")
async def check_equipment(equipment_id: int, request: Request) -> dict:
    """Pergunta *IDN? no endereço cadastrado e confere se o modelo bate com o driver."""
    eq = _store(request).get(equipment_id)
    bus: GpibBus = request.app.state.bus
    try:
        idn, cls = await asyncio.wrap_future(
            bus.transaction(lambda t: identify(InstrumentIO(t, eq["address"])))
        )
    except GpibTimeout:
        return {"online": False, "idn": None, "detected_driver": None, "matches": False}
    detected = cls.name if cls else None
    return {"online": True, "idn": idn.to_dict(), "detected_driver": detected, "matches": detected == eq["driver"]}
