import os

from fastapi import HTTPException, status
from openai import AsyncOpenAI


def obtener_cliente_openai() -> AsyncOpenAI:
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No está configurada la variable OPENAI_API_KEY en el backend.",
        )

    return AsyncOpenAI(api_key=api_key)