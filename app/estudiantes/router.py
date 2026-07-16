from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.estudiantes.schemas import (
    AsignacionEstudianteResponse,
    AsignarGrupoEstudianteCreate,
    ClaseActualResponse,
    ClasesHoyResponse,
    ProximaClaseResponse,
    ReporteClaseActualResponse,
    MisReportesResponse,
    ClaseDetalleResponse,
)
from app.estudiantes import service
from app.usuarios.utils import requerir_roles
from app.realtime.manager import realtime_manager

router = APIRouter(prefix="/estudiantes", tags=["Estudiantes"])


async def emitir_actualizacion_reportes(origen: str) -> None:
    await realtime_manager.emitir({
        "tipo": "reportes_actualizados",
        "origen": origen,
    })

    await realtime_manager.emitir({
        "tipo": "dashboard_actualizado",
        "origen": origen,
    })


@router.get("/mis-clases-hoy", response_model=ClasesHoyResponse)
async def obtener_mis_clases_hoy(
    usuario_actual: dict = Depends(requerir_roles("estudiante")),
):
    clases = await service.get_mis_clases_hoy(usuario_actual)

    return {
        "ok": True,
        "message": "Clases del día obtenidas correctamente",
        "data": clases,
    }


@router.get("/proxima-clase", response_model=ProximaClaseResponse)
async def obtener_proxima_clase(
    usuario_actual: dict = Depends(requerir_roles("estudiante")),
):
    clase = await service.get_proxima_clase(usuario_actual)

    return {
        "ok": True,
        "message": "Próxima clase obtenida correctamente",
        "data": clase,
    }


@router.get("/clase-actual", response_model=ClaseActualResponse)
async def obtener_clase_actual(
    usuario_actual: dict = Depends(requerir_roles("estudiante")),
):
    clase = await service.get_clase_actual(usuario_actual)

    return {
        "ok": True,
        "message": "Clase actual obtenida correctamente",
        "data": clase,
    }


@router.get("/clases/{clase_id}", response_model=ClaseDetalleResponse)
async def obtener_detalle_clase(
    clase_id: str,
    usuario_actual: dict = Depends(requerir_roles("estudiante")),
):
    clase = await service.get_clase_por_id(usuario_actual, clase_id)

    return {
        "ok": True,
        "message": "Detalle de clase obtenido correctamente",
        "data": clase,
    }


@router.post(
    "/reportar-incidencia-actual",
    response_model=ReporteClaseActualResponse,
    status_code=status.HTTP_201_CREATED,
)
async def reportar_incidencia_clase_actual(
    descripcion: str = Form(..., min_length=10, max_length=500),
    gravedad: str = Form("media"),
    imagenes: Optional[List[UploadFile]] = File(None),
    usuario_actual: dict = Depends(requerir_roles("estudiante")),
):
    try:
        reporte = await service.crear_reporte_clase_actual_estudiante(
            descripcion=descripcion,
            gravedad=gravedad,
            usuario_actual=usuario_actual,
            imagenes=imagenes,
        )

        await emitir_actualizacion_reportes("crear_reporte_estudiante")

        return {
            "ok": True,
            "message": "Reporte registrado correctamente",
            "data": reporte,
        }

    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )


@router.get("/mis-reportes", response_model=MisReportesResponse)
async def obtener_mis_reportes(
    usuario_actual: dict = Depends(requerir_roles("estudiante")),
):
    reportes = await service.get_mis_reportes_estudiante(usuario_actual)

    return {
        "ok": True,
        "message": "Reportes del estudiante obtenidos correctamente",
        "data": reportes,
    }


@router.post(
    "/admin/asignar-grupo",
    response_model=AsignacionEstudianteResponse,
    status_code=status.HTTP_201_CREATED,
)
async def asignar_grupo_estudiante(
    payload: AsignarGrupoEstudianteCreate,
    usuario_actual: dict = Depends(requerir_roles("admin")),
):
    try:
        asignacion = await service.asignar_grupo_estudiante(payload, usuario_actual)

        return {
            "ok": True,
            "message": "Grupo asignado correctamente al estudiante",
            "data": asignacion,
        }

    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )