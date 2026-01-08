# Arquitectura del Sistema

## Visión General
El sistema sigue una arquitectura **Cliente-Servidor con Procesamiento Asíncrono**. Se prioriza la velocidad de respuesta para el monitoreo en vivo y se delega el guardado de registros históricos a un proceso secundario para no bloquear el sistema.



## Componentes Principales

### 1. El Agente (Cliente en NUCs)
* Script Python ligero.
* Recopila: Uso CPU, RAM, Disco, Temperatura, Latencia (Ping).
* Envía JSON vía HTTP POST al servidor.
* Almacena caché local si no hay internet (Store & Forward).

### 2. El Núcleo (Backend Flask)
* **API Controller:** Recibe los reportes POST.
* **Device Manager (Modelo):** Mantiene el estado de los 500 equipos en memoria RAM para acceso instantáneo (O(1)).
* **Alert Service:** Evalúa reglas de negocio (ej. Si RAM > 90% -> Alerta).

### 3. Capa de Datos (Híbrida)
* **Hot Storage (Tiempo Real):** Archivo `data.json`. Se actualiza periódicamente para persistencia rápida.
* **Cold Storage (Histórico):** Cola de tareas (Queue) -> Google Sheets. Se usa para auditoría y análisis de tendencias a largo plazo.

### 4. Interfaz de Usuario (Frontend)
* **Tecnología:** HTML5 + Jinja2 (Renderizado en servidor) + JavaScript (Actualización dinámica).
* **Diseño:** Estilo Dashboard Ejecutivo (KPIs, Gráficos, Tablas).
* **Librerías:** TailwindCSS (Estilos), Chart.js (Gráficos), Leaflet (Mapas).

## Flujo de Datos
1.  NUC envía POST `/api/report`.
2.  Servidor valida Token y actualiza `DeviceManager`.
3.  Si el estado cambia (Online -> Offline), `AlertService` dispara emails.
4.  Si hay datos críticos, se encolan hacia el `StorageWorker` (Google Sheets).
5.  El Dashboard consulta `/api/data` y actualiza la vista del usuario en tiempo real.
