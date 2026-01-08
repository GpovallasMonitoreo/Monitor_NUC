# Especificación de Requerimientos de Software (SRS)
## Proyecto: Sistema de Monitoreo Integral (Argos)

### 1. Actores y Roles
* **Director de Área:** Visualiza KPIs globales, disponibilidad de la red y justificación de presupuesto (reemplazo de hardware).
* **Coordinadores / Supervisores:** Monitorean el estado operativo por zonas/unidades de negocio (BioBox, EcoVallas y ViaVerde).
* **Ing. Soporte Técnico:** Recibe alertas inmediatas, diagnostica fallos específicos (CPU, RAM, Disco) y ejecuta mantenimiento.
* **Agente Remoto (NUC):** Software instalado en los equipos que reporta telemetría.

### 2. Requerimientos Funcionales (Lo que hace el sistema)
* **RF-01 Monitoreo en Tiempo Real:** El sistema debe recibir "latidos" (heartbeats) de equipos cada 60 segundos (puede variar de acuerdo a la operación).
* **RF-02 Alertas Críticas:** Enviar correo electrónico inmediato a Soporte cuando:
    * Un equipo deja de reportar por > 3 minutos (Desconexión).
    * Sensores críticos superan umbrales (Temp > 90°C, Disco > 95%).
* **RF-03 Análisis Predictivo:** Almacenar métricas históricas para identificar equipos que requieren reemplazo (toma de decisiones).
* **RF-04 Visualización Jerárquica:** Dashboard filtrable por Unidad de Negocio y estatus.

### 3. Requerimientos No Funcionales (Cómo se comporta)
* **RNF-01 Escalabilidad:** Soporte para hasta 500 dispositivos concurrentes.
* **RNF-02 Persistencia Híbrida:** * Datos en vivo: Memoria/JSON (Alta velocidad).
    * Datos históricos: Google Sheets/CSV (Análisis a largo plazo).
* **RNF-03 Disponibilidad:** El servidor debe estar activo 24/7 (Requiere plan de pago en Render/Cloud para evitar "sleep mode").

### 4. Riesgos Críticos a Mitigar
1.  **Falso Positivo:** Alertar que un equipo se cayó cuando solo fue un retraso de red. -> *Solución: Lógica de "consecutive_failures".*
2.  **Pérdida de Datos:** Que un reinicio del servidor borre el estado actual. -> *Solución: Persistencia en JSON local.*
