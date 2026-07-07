from fastapi import APIRouter, HTTPException, status, Depends
from bson import ObjectId
from datetime import datetime, timezone

from app.database import db
from app.tickets.schemas import (
    TicketCreate,
    TicketResponse,
    TicketEstadoUpdate,
    EstadoTicketEnum
)
from app.usuarios.utils import verificar_roles


router = APIRouter(prefix="/tickets", tags=["Tickets"])

coleccion_tickets = db["tickets"]


def convertir_ticket(ticket) -> dict:
    ticket["id"] = str(ticket["_id"])
    return ticket


async def generar_codigo_ticket() -> str:
    total = await coleccion_tickets.count_documents({})
    numero = total + 1
    return f"TK-{str(numero).zfill(3)}"


@router.post(
    "/",
    response_model=TicketResponse,
    status_code=status.HTTP_201_CREATED
)
async def crear_ticket(
    ticket: TicketCreate,
    usuario: dict = Depends(verificar_roles("Ayudante", "Admin"))
):
    nuevo_ticket = ticket.model_dump()

    nuevo_ticket["codigo"] = await generar_codigo_ticket()
    nuevo_ticket["estado"] = EstadoTicketEnum.PENDIENTE.value
    nuevo_ticket["creado_por"] = usuario["email"]
    nuevo_ticket["nombre_creador"] = usuario["nombre"]
    nuevo_ticket["fecha_creacion"] = datetime.now(timezone.utc)
    nuevo_ticket["observacion_admin"] = None

    resultado = await coleccion_tickets.insert_one(nuevo_ticket)

    ticket_guardado = await coleccion_tickets.find_one(
        {"_id": resultado.inserted_id}
    )

    return convertir_ticket(ticket_guardado)


@router.get("/", response_model=list[TicketResponse])
async def listar_tickets(
    usuario: dict = Depends(verificar_roles("Admin"))
):
    tickets = []

    cursor = coleccion_tickets.find()

    async for ticket in cursor:
        tickets.append(convertir_ticket(ticket))

    return tickets


@router.get("/mis-tickets", response_model=list[TicketResponse])
async def listar_mis_tickets(
    usuario: dict = Depends(verificar_roles("Ayudante", "Admin"))
):
    tickets = []

    cursor = coleccion_tickets.find(
        {"creado_por": usuario["email"]}
    )

    async for ticket in cursor:
        tickets.append(convertir_ticket(ticket))

    return tickets


@router.put("/{ticket_id}/estado", response_model=TicketResponse)
async def actualizar_estado_ticket(
    ticket_id: str,
    datos: TicketEstadoUpdate,
    usuario: dict = Depends(verificar_roles("Admin"))
):
    if not ObjectId.is_valid(ticket_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID de ticket inválido"
        )

    resultado = await coleccion_tickets.update_one(
        {"_id": ObjectId(ticket_id)},
        {
            "$set": {
                "estado": datos.estado.value,
                "observacion_admin": datos.observacion_admin
            }
        }
    )

    if resultado.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket no encontrado"
        )

    ticket_actualizado = await coleccion_tickets.find_one(
        {"_id": ObjectId(ticket_id)}
    )

    return convertir_ticket(ticket_actualizado)


@router.put("/{ticket_id}/resolver", response_model=TicketResponse)
async def resolver_ticket(
    ticket_id: str,
    usuario: dict = Depends(verificar_roles("Admin"))
):
    if not ObjectId.is_valid(ticket_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID de ticket inválido"
        )

    resultado = await coleccion_tickets.update_one(
        {"_id": ObjectId(ticket_id)},
        {
            "$set": {
                "estado": EstadoTicketEnum.RESUELTO.value,
                "observacion_admin": "Ticket resuelto por el administrador"
            }
        }
    )

    if resultado.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket no encontrado"
        )

    ticket_actualizado = await coleccion_tickets.find_one(
        {"_id": ObjectId(ticket_id)}
    )

    return convertir_ticket(ticket_actualizado)