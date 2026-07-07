# Muestras locales de prueba

Este microservicio NO usa cámaras reales. Analiza imágenes o videos locales
colocados en esta carpeta para validar la arquitectura de visión artificial.

## Dónde colocar los archivos

Coloca aquí (mismo nombre, cualquiera de los dos formatos):

```
samples/BIBLIO1.jpg          o samples/BIBLIO1.mp4
samples/biblioteca_general.jpg       o samples/biblioteca_general.mp4
samples/sala_grupal_2.jpg            o samples/sala_grupal_2.mp4
samples/laboratorio_computadoras.jpg o samples/laboratorio_computadoras.mp4
samples/sala_lectura_humanidades.jpg o samples/sala_lectura_humanidades.mp4
```

Estos nombres son los que el scheduler del vision-service analiza
automáticamente cada 30 segundos (ver `app/space_registry.py`, en este mismo
microservicio, para el detalle de qué espacio usa cada archivo).

## Qué pasa si no colocas ningún archivo

El servicio **no falla**. Si `sourcePath` no existe, o si el modelo YOLO no
pudo cargarse (por ejemplo, sin conexión a internet para descargar los pesos
`yolov8n.pt` la primera vez), tanto el scheduler automático como
`POST /vision/analyze` responden igual con `ok: true` y una ocupación
simulada, marcando claramente:

```json
"source": "vision-service-fallback"
```

Esto permite probar toda la cadena backend → vision-service → frontend sin
necesitar imágenes reales ni conexión a internet.

## Requisitos de las imágenes/videos reales (opcional)

- Formatos soportados: `.jpg`/`.jpeg`/`.png` para imágenes, `.mp4`/`.mov` para video.
- No se guardan, no se procesan rostros ni se identifica a nadie: solo se
  cuenta la clase `"person"` de forma anónima y se descarta el resultado
  después de responder (el servicio no persiste nada).
- Cualquier foto de una sala/biblioteca con personas sirve para probar la
  detección real (no hace falta que sea de la UCE).
