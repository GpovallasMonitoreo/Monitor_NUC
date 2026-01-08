# Plan de Implementación

## Fase 1: Cimientos (ESTADO ACTUAL)
- [x] Definición de Requerimientos y Roles.
- [x] Definición de Arquitectura.
- [ ] Crear estructura de carpetas limpia en GitHub.
- [ ] Configurar entorno virtual (`venv`) y `requirements.txt`.

## Fase 2: Backend Core (Lógica)
- [ ] Implementar Clase `Device` (Modelo de datos).
- [ ] Implementar `StorageService` (Lectura/Escritura JSON).
- [ ] Implementar Worker de Google Sheets (Cola asíncrona).
- [ ] Crear API Endpoint `/report` para recibir datos de NUCs.

## Fase 3: Sistema de Alertas
- [ ] Implementar lógica de detección de desconexión (Timeout).
- [ ] Configurar envío de correos SMTP con plantillas HTML.
- [ ] Evitar spam de alertas (Lógica de "Email ya enviado").

## Fase 4: Frontend (Dashboard)
- [ ] Integrar plantilla base HTML (Sidebar, Header).
- [ ] Crear vista de Dashboard Principal (Tarjetas y Tablas).
- [ ] Integrar Mapa de Calor Leaflet con datos reales.
- [ ] Crear vista de Inventario/Detalle.

## Fase 5: Despliegue
- [ ] Pruebas de carga (Simular 500 NUCs).
- [ ] Configurar Gunicorn para producción.
- [ ] Despliegue en Render (Environment Variables).
