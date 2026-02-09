"""
Catálogo de soluciones y SLA para soporte técnico
"""

# ==============================================================================
# 📚 CATÁLOGO DE SOPORTE - GENERADO DESDE EXCEL (COMPLETO)
# ==============================================================================

CATALOGO_SOPORTE = {
    "Conectividad y Red": {
        "Falla de Conectividad (Proveedor / Intermitencia Masiva)": {
            "Falla de Internet / Intermitencia": {
                "soluciones": ["Restablecimiento de Servicio", "Reconfiguración de Red", "Validación Remota", "Escalamiento a Proveedor"],
                "slas": {
                    "Restablecimiento de Servicio": {"min": 6, "objetivo": 8, "max": 12},
                    "Reconfiguración de Red": {"min": 6, "objetivo": 8, "max": 12},
                    "Validación Remota": {"min": 6, "objetivo": 8, "max": 12},
                    "Escalamiento a Proveedor": {"min": 72.0, "objetivo": 84, "max": 96}
                }
            },
            "Falla de Internet Falta de Pago": {
                "soluciones": ["Escalamiento a TI"],
                "slas": {"Escalamiento a TI": {"min": 24.0, "objetivo": 28, "max": 32}}
            }
        },
        "Falla de Conectividad (Corte de Fibra)": {
            "Fibra Óptica Dañada": {
                "soluciones": ["Escalamiento a Proveedor", "Reparación de Enlace", "Validación Remota"],
                "slas": {
                    "Escalamiento a Proveedor": {"min": 72.0, "objetivo": 84, "max": 96},
                    "Reparación de Enlace": {"min": 72.0, "objetivo": 84, "max": 96},
                    "Validación Remota": {"min": 24.0, "objetivo": 28, "max": 32}
                }
            }
        },
        "Falla de Conectividad Local (Intermitencia / VPN)": {
            "VPN Desactivada / No Conecta": {
                "soluciones": ["Reinicio de Comunicaciones", "Reconfiguración de Red", "Cierre de Ventanas Emergentes"],
                "slas": {
                    "Reinicio de Comunicaciones": {"min": 2, "objetivo": 4, "max": 6},
                    "Reconfiguración de Red": {"min": 2, "objetivo": 4, "max": 6},
                    "Cierre de Ventanas Emergentes": {"min": 2, "objetivo": 4, "max": 6}
                }
            }
        },
        "Falla de Hardware de Red (Rut) (Falla de Router)": {
            "Módem / Router Alarmado o Sin Datos": {
                "soluciones": ["Reinicio de Comunicaciones", "Reconfiguración de Red", "Cambio de Equipo de Red"],
                "slas": {
                    "Reinicio de Comunicaciones": {"min": 2, "objetivo": 4, "max": 6},
                    "Reconfiguración de Red": {"min": 2, "objetivo": 4, "max": 6},
                    "Cambio de Equipo de Red": {"min": 24.0, "objetivo": 28, "max": 32}
                }
            }
        },
        "Falla de Hardware (Módem)": {
            "Módem / Router Alarmado o Sin Datos": {
                "soluciones": ["Reinicio de Comunicaciones", "Reconfiguración de Red", "Cambio de Equipo de Red", "Proveedor reestable el servicio"],
                "slas": {
                    "Reinicio de Comunicaciones": {"min": 2, "objetivo": 4, "max": 6},
                    "Reconfiguración de Red": {"min": 2, "objetivo": 4, "max": 6},
                    "Cambio de Equipo de Red": {"min": 24.0, "objetivo": 28, "max": 32},
                    "Proveedor reestable el servicio": {"min": 72.0, "objetivo": 84, "max": 96}
                }
            }
        },
        "Falla de Hardware (Cable Ethernet)": {
            "Cableado Dañado (Red / PLC / Eléctrico)": {
                "soluciones": ["Cambio de Componente Físico", "Reconexión de Cableado"],
                "slas": {
                    "Cambio de Componente Físico": {"min": 24.0, "objetivo": 28, "max": 32},
                    "Reconexión de Cableado": {"min": 6.0, "objetivo": 8, "max": 12}
                }
            }
        },
        "Falla de Hardware de Red (Falla en Datos SIM)": {
            "SIM sin Datos / Falta de Pago": {
                "soluciones": ["Restablecimiento de Servicio", "Cambio de Equipo de Red", "Escalamiento a Proveedor", "Escalamiento a TI"],
                "slas": {
                    "Restablecimiento de Servicio": {"min": 2, "objetivo": 4, "max": 6},
                    "Cambio de Equipo de Red": {"min": 24.0, "objetivo": 28, "max": 32},
                    "Escalamiento a Proveedor": {"min": 24.0, "objetivo": 28, "max": 32},
                    "Escalamiento a TI": {"min": 24.0, "objetivo": 28, "max": 32}
                }
            }
        },
        "Falla de enlace de Pantalla (Error de Comunicación)": {
            "Pérdida de Comunicación NUC–App": {
                "soluciones": ["Reinicio de Comunicaciones", "Reinicio de Servicios", "Validación de Logs"],
                "slas": {
                    "Reinicio de Comunicaciones": {"min": 6, "objetivo": 8, "max": 12},
                    "Reinicio de Servicios": {"min": 6, "objetivo": 8, "max": 12},
                    "Validación de Logs": {"min": 6, "objetivo": 8, "max": 12}
                }
            }
        }
    },
    "Hardware": {
        "Pantalla en Negro / Sin Señal (Posible causa de hardware)": {
            "Pantalla en Negro por Hardware": {
                "soluciones": ["Reinicio de Controlador de Pantalla", "Cambio de Componente Físico"],
                "slas": {
                    "Reinicio de Controlador de Pantalla": {"min": 6, "objetivo": 8, "max": 12},
                    "Cambio de Componente Físico": {"min": 24.0, "objetivo": 28, "max": 32}
                }
            }
        },
        "Falla de NUC (Apagado / Congelado / Reinicios)": {
            "NUC Apagado / Congelado / Fuera de Línea": {
                "soluciones": ["Reinicio de Equipo", "Encendido Manual", "Liberación de Recursos"],
                "slas": {
                    "Reinicio de Equipo": {"min": 0.3, "objetivo": 1, "max": 2},
                    "Encendido Manual": {"min": 0.3, "objetivo": 1, "max": 2},
                    "Liberación de Recursos": {"min": 0.3, "objetivo": 1, "max": 2}
                }
            },
            "Reinicio por Actualización de SO": {
                "soluciones": ["Reinstalación de Sistema Operativo", "Validación de Logs"],
                "slas": {
                    "Reinstalación de Sistema Operativo": {"min": 24.0, "objetivo": 28, "max": 32},
                    "Validación de Logs": {"min": 0.3, "objetivo": 1, "max": 2}
                }
            },
            "Falla Física en NUC": {
                "soluciones": ["Cambio de NUC", "Reconexión de Periféricos"],
                "slas": {
                    "Cambio de NUC": {"min": 24.0, "objetivo": 28, "max": 32},
                    "Reconexión de Periféricos": {"min": 6.0, "objetivo": 8, "max": 12}
                }
            }
        },
        "Módulo LED Dañado": {
            "Módulo LED Dañado": {"soluciones": ["Cambio de Módulo LED"], "slas": {"Cambio de Módulo LED": {"min": 24.0, "objetivo": 28, "max": 32}}},
            "Corto circuito (en tira LED o cables).": {"soluciones": ["Cambio de Módulo LED"], "slas": {"Cambio de Módulo LED": {"min": 24.0, "objetivo": 28, "max": 32}}},
            "Falla o variación en el suministro eléctrico (CFE, voltaje).": {"soluciones": ["Cambio de Módulo LED"], "slas": {"Cambio de Módulo LED": {"min": 24.0, "objetivo": 28, "max": 32}}},
            "Vandalismo o robo (daño físico intencional).": {"soluciones": ["Cambio de Módulo LED"], "slas": {"Cambio de Módulo LED": {"min": 24.0, "objetivo": 28, "max": 32}}},
            "Desgaste por tiempo de uso.": {"soluciones": ["Cambio de Módulo LED"], "slas": {"Cambio de Módulo LED": {"min": 24.0, "objetivo": 28, "max": 32}}},
            "Daño por agua o humedad (filtraciones).": {"soluciones": ["Cambio de Módulo LED"], "slas": {"Cambio de Módulo LED": {"min": 24.0, "objetivo": 28, "max": 32}}},
            "Sobrecalentamiento (falta de ventilación).": {"soluciones": ["Cambio de Módulo LED"], "slas": {"Cambio de Módulo LED": {"min": 24.0, "objetivo": 28, "max": 32}}},
            "Conexiones flojas o cables dañados (problemas de ensamble/instalación).": {"soluciones": ["Cambio de Módulo LED"], "slas": {"Cambio de Módulo LED": {"min": 24.0, "objetivo": 28, "max": 32}}},
            "Falla en componente relacionado.": {"soluciones": ["Cambio de Módulo LED"], "slas": {"Cambio de Módulo LED": {"min": 24.0, "objetivo": 28, "max": 32}}}
        },
        "Falla de Puerto (COM, etc.)": {
            "Puerto COM Ocupado o Incorrecto": {
                "soluciones": ["Reconfiguración de Puerto COM", "Escalamiento a TI"],
                "slas": {"Reconfiguración de Puerto COM": {"min": 6, "objetivo": 8, "max": 12}, "Escalamiento a TI": {"min": 24.0, "objetivo": 28, "max": 32}}
            }
        },
        "Falla de Puerto (HDMI)": {
            "Cable HDMI / Datos Dañado": {"soluciones": ["Reconexión de Cableado de Video"], "slas": {"Reconexión de Cableado de Video": {"min": 24.0, "objetivo": 28, "max": 32}}}
        },
        "Falla de Tarjeta (Receptora, SD300, etc.)": {
            "Tarjeta Receptora / SD300 con Falla": {
                "soluciones": ["Cambio de Tarjeta Receptora", "Reinicio de Controlador de Pantalla"],
                "slas": {"Cambio de Tarjeta Receptora": {"min": 24.0, "objetivo": 28, "max": 32}, "Reinicio de Controlador de Pantalla": {"min": 6, "objetivo": 8, "max": 12}}
            },
            "SD300 No detecta puerto": {"soluciones": ["Cambio de SD300"], "slas": {"Cambio de SD300": {"min": 24.0, "objetivo": 28, "max": 32}}}
        },
        "Falla de Sensor (Brillo, Apertura, etc.)": {
            "Sensor de Brillo Mal Configurado": {
                "soluciones": ["Reconfiguración de Sensor de Brillo", "Ajuste Manual de Brillo"],
                "slas": {"Reconfiguración de Sensor de Brillo": {"min": 0.3, "objetivo": 1, "max": 2}, "Ajuste Manual de Brillo": {"min": 0.3, "objetivo": 1, "max": 2}}
            }
        },
        "Falla de Mecanismo Físico (Compuerta, Carrusel, Montaje)": {
            "Falla de Mecanismo (Compuerta / PLC / Arduino)": {
                "soluciones": ["Reinicio de Controlador (PLC / Arduino)", "Ajuste Mecánico"],
                "slas": {"Reinicio de Controlador (PLC / Arduino)": {"min": 6, "objetivo": 8, "max": 12}, "Ajuste Mecánico": {"min": 6, "objetivo": 8, "max": 12}}
            }
        },
        "Falla de Mecanismo Físico (BIOBOX / PLC)": {
            "Falla de Mecanismo (Compuerta / PLC / Arduino)": {
                "soluciones": ["Reinicio de Controlador (PLC / Arduino)", "Ajuste Mecánico"],
                "slas": {"Reinicio de Controlador (PLC / Arduino)": {"min": 6, "objetivo": 8, "max": 12}, "Ajuste Mecánico": {"min": 6, "objetivo": 8, "max": 12}}
            }
        },
        "Falla de Mecanismo Físico (BIOBOX / Arduino)": {
            "Falla de Mecanismo (Compuerta / PLC / Arduino)": {
                "soluciones": ["Reinicio de Controlador (PLC / Arduino)", "Ajuste Mecánico", "Escalamiento a TI"],
                "slas": {"Reinicio de Controlador (PLC / Arduino)": {"min": 6, "objetivo": 8, "max": 12}, "Ajuste Mecánico": {"min": 6, "objetivo": 8, "max": 12}, "Escalamiento a TI": {"min": 24.0, "objetivo": 28, "max": 32}}
            }
        }
    },
    "Falla Eléctrica": {
        "Falla en Pastillas / Centro de Carga": {
            "Pastillas Botadas / Centro de Carga": {
                "soluciones": ["Ajuste de Centro de Carga", "Cambio de pastillas", "Reinicio de tablero"],
                "slas": {"Ajuste de Centro de Carga": {"min": 12.0, "objetivo": 15, "max": 18}, "Cambio de pastillas": {"min": 24.0, "objetivo": 28, "max": 32}, "Reinicio de tablero": {"min": 6, "objetivo": 8, "max": 12}}
            }
        },
        "Falla de UPS / Regulador": {
            "Equipo Apagado por Energía": {
                "soluciones": ["Encendido Manual de Equipo", "Restablecimiento de Energía", "Reporte con proveedor (CFE)"],
                "slas": {"Encendido Manual de Equipo": {"min": 24.0, "objetivo": 28, "max": 32}, "Restablecimiento de Energía": {"min": 24.0, "objetivo": 28, "max": 32}, "Reporte con proveedor (CFE)": {"min": 72.0, "objetivo": 84, "max": 96}}
            },
            "No retiene carga": {"soluciones": ["Cambio de UPS"], "slas": {"Cambio de UPS": {"min": 12.0, "objetivo": 15, "max": 18}}}
        },
        "Daño en Cableado de Red (Eléctrico, Red, Flat, PLC)": {
            "Cableado Dañado (Red / PLC / Eléctrico)": {
                "soluciones": ["Cambio de Componente Físico", "Reconexión de Cableado"],
                "slas": {"Cambio de Componente Físico": {"min": 24.0, "objetivo": 28, "max": 32}, "Reconexión de Cableado": {"min": 24.0, "objetivo": 28, "max": 32}}
            }
        },
        "Falla de Suministro Eléctrico (CFE)": {
            "Falla de Suministro Eléctrico (CFE)": {
                "soluciones": ["Restablecimiento de Energía", "Escalamiento a Iluminacion", "Escalamiento a Proveedor", "Validación Eléctrica"],
                "slas": {
                    "Restablecimiento de Energía": {"min": 24.0, "objetivo": 28, "max": 32},
                    "Escalamiento a Iluminacion": {"min": 24.0, "objetivo": 28, "max": 32},
                    "Escalamiento a Proveedor": {"min": 72.0, "objetivo": 84, "max": 96},
                    "Validación Eléctrica": {"min": 24.0, "objetivo": 28, "max": 32}
                }
            }
        },
        "Falla de Suministro Eléctrico (Variación de Voltaje)": {
            "Variación de Voltaje": {
                "soluciones": ["Corrección de Voltaje", "Validación Eléctrica"],
                "slas": {"Corrección de Voltaje": {"min": 24.0, "objetivo": 28, "max": 32}, "Validación Eléctrica": {"min": 24.0, "objetivo": 28, "max": 32}}
            }
        },
        "Falla de Suministro Eléctrico (Medidor Alarmado)": {
            "Variación de Voltaje": {
                "soluciones": ["Corrección de Voltaje", "Validación Eléctrica"],
                "slas": {"Corrección de Voltaje": {"min": 24.0, "objetivo": 28, "max": 32}, "Validación Eléctrica": {"min": 24.0, "objetivo": 28, "max": 32}}
            }
        }
    },
    "Software y Configuración": {
        "Ajuste o Falla de Brillo (Alto / Bajo)": {
            "Brillo Alto": {
                "soluciones": ["Ajuste Manual de Brillo", "Ajuste Automático por Clima u Horario"],
                "slas": {"Ajuste Manual de Brillo": {"min": 0.3, "objetivo": 1, "max": 2}, "Ajuste Automático por Clima u Horario": {"min": 0.3, "objetivo": 1, "max": 2}}
            },
            "Brillo Bajo": {
                "soluciones": ["Ajuste Manual de Brillo", "Ajuste Automático por Clima u Horario"],
                "slas": {"Ajuste Manual de Brillo": {"min": 0.3, "objetivo": 1, "max": 2}, "Ajuste Automático por Clima u Horario": {"min": 0.3, "objetivo": 1, "max": 2}}
            }
        },
        "Ventanas Emergentes / Pop-ups": {
            "Ventanas Emergentes Abiertas (Windows / VPN / TeamViewer / Nova)": {
                "soluciones": ["Cierre de Ventanas Emergentes", "Bloqueo de Notificaciones"],
                "slas": {"Cierre de Ventanas Emergentes": {"min": 0.3, "objetivo": 1, "max": 2}, "Bloqueo de Notificaciones": {"min": 0.3, "objetivo": 1, "max": 2}}
            }
        },
        "Actualización de SO (Inesperada o Fallida)": {
            "Reinicio por Actualización de SO": {
                "soluciones": ["Reinstalación de Sistema Operativo", "Validación de Logs"],
                "slas": {"Reinstalación de Sistema Operativo": {"min": 24.0, "objetivo": 28, "max": 32}, "Validación de Logs": {"min": 24.0, "objetivo": 28, "max": 32}}
            }
        },
        "Calibración Requerida (Báscula, Pantalla, etc.)": {
            "Sensor de Brillo Mal Configurado": {
                "soluciones": ["Reconfiguración de Sensor de Brillo"],
                "slas": {"Reconfiguración de Sensor de Brillo": {"min": 2, "objetivo": 4, "max": 6}}
            }
        },
        "Configuración General del Sistema": {
            "Configuración Incorrecta del Sistema": {
                "soluciones": ["Corrección de Configuración", "Mapeo de pantalla", "Restauración de Archivos del Sistema"],
                "slas": {
                    "Corrección de Configuración": {"min": 2, "objetivo": 4, "max": 6},
                    "Mapeo de pantalla": {"min": 2, "objetivo": 4, "max": 6},
                    "Restauración de Archivos del Sistema": {"min": 2, "objetivo": 4, "max": 6}
                }
            }
        },
        "Dirección o Enfoque de Cámara": {
            "Cámara Mal Enfocada / Inclinada": {"soluciones": ["Reorientación de Cámara"], "slas": {"Reorientación de Cámara": {"min": 6, "objetivo": 8, "max": 12}}}
        },
        "Cámara con desconexión": {
            "Cable UTP dañado": {"soluciones": ["Reemplazo de cable UTP"], "slas": {"Reemplazo de cable UTP": {"min": 12.0, "objetivo": 15, "max": 18}}},
            "POE dañado": {"soluciones": ["Reemplazo de POE", "Reinicio de POE"], "slas": {"Reemplazo de POE": {"min": 24.0, "objetivo": 28, "max": 32}, "Reinicio de POE": {"min": 6, "objetivo": 8, "max": 12}}},
            "Sin servicio de internet": {"soluciones": ["Reinicio de equipos de internet", "Reporte con proveedor"], "slas": {"Reinicio de equipos de internet": {"min": 6, "objetivo": 8, "max": 12}, "Reporte con proveedor": {"min": 6, "objetivo": 8, "max": 12}}}
        },
        "Iconos Visibles en Pantalla": {
            "Barra de Tareas Visible": {"soluciones": ["Ocultamiento de Barra de Tareas", "Ajuste de Interfaz de Usuario"], "slas": {"Ocultamiento de Barra de Tareas": {"min": 2, "objetivo": 4, "max": 6}, "Ajuste de Interfaz de Usuario": {"min": 2, "objetivo": 4, "max": 6}}},
            "Notificaciones en Pantalla": {"soluciones": ["Bloqueo de Notificaciones"], "slas": {"Bloqueo de Notificaciones": {"min": 2, "objetivo": 4, "max": 6}}}
        },
        "Aplicación JS (BIOBOX)": {
            "Error de Aplicación BIOBOX (Error -400 / JAVA)": {
                "soluciones": ["Reinicio de Servicios (Tomcat / JAVA / VPN)", "Corrección de Configuración", "Validación de Logs"],
                "slas": {"Reinicio de Servicios (Tomcat / JAVA / VPN)": {"min": 2, "objetivo": 4, "max": 6}, "Corrección de Configuración": {"min": 2, "objetivo": 4, "max": 6}, "Validación de Logs": {"min": 2, "objetivo": 4, "max": 6}}
            },
            "Error de Aplicación BIOBOX (Error -1)": {
                "soluciones": ["Validación de Logs"],
                "slas": {"Validación de Logs": {"min": 2, "objetivo": 4, "max": 6}}
            }
        }
    },
    "Contenido / Arte": {
        "Visualización de Campaña (No se muestra, intermitente)": {
            "Error de Programación de Campaña": {"soluciones": ["Reprogramación de Campaña"], "slas": {"Reprogramación de Campaña": {"min": 0, "objetivo": 0, "max": 0}}},
            "Arte No Disponible / Incompleto": {"soluciones": ["Carga de Contenido"], "slas": {"Carga de Contenido": {"min": 0, "objetivo": 0, "max": 0}}}
        },
        "Pantalla en Negro (Posible causa de contenido)": {
            "Pantalla en Negro por Contenido": {"soluciones": ["Corrección de Contenido Visual", "Validación Visual Final"], "slas": {"Corrección de Contenido Visual": {"min": 0, "objetivo": 0, "max": 0}, "Validación Visual Final": {"min": 0, "objetivo": 0, "max": 0}}}
        },
        "Discrepancia en Archivo de Arte (Formato, ajuste, daño)": {
            "Formato o Dimensiones Incorrectas": {"soluciones": ["Corrección de Arte"], "slas": {"Corrección de Arte": {"min": 0, "objetivo": 0, "max": 0}}},
            "Nomenclatura de Arte No Estándar": {"soluciones": ["Corrección de Arte"], "slas": {"Corrección de Arte": {"min": 0, "objetivo": 0, "max": 0}}}
        },
        "Ajuste de Programación de Campaña": {
            "Error de Programación de Campaña": {"soluciones": ["Reprogramación de Campaña"], "slas": {"Reprogramación de Campaña": {"min": 0, "objetivo": 0, "max": 0}}}
        },
        "Falla de Sincronización de Contenido": {
            "Versión Incorrecta de Campaña": {"soluciones": ["Actualización de Versión de Contenido"], "slas": {"Actualización de Versión de Contenido": {"min": 0, "objetivo": 0, "max": 0}}}
        },
        "Inconsistencia de Versión o Contenido": {
            "Versión Incorrecta de Campaña": {"soluciones": ["Actualización de Versión de Contenido"], "slas": {"Actualización de Versión de Contenido": {"min": 0, "objetivo": 0, "max": 0}}}
        },
        "Ajuste de Frame o Layout Visual": {
            "Formato o Dimensiones Incorrectas": {"soluciones": ["Corrección de Arte"], "slas": {"Corrección de Arte": {"min": 0, "objetivo": 0, "max": 0}}}
        },
        "Falla de Trigger o Activador": {
            "Error de Programación de Campaña": {"soluciones": ["Reprogramación de Campaña"], "slas": {"Reprogramación de Campaña": {"min": 0, "objetivo": 0, "max": 0}}}
        },
        "Afectación por Programmatica (SSP)": {
            "Error de Programación de Campaña": {"soluciones": ["Reprogramación de Campaña"], "slas": {"Reprogramación de Campaña": {"min": 0, "objetivo": 0, "max": 0}}}
        }
    },
    "Factores Externos y Seguridad": {
        "Vandalismo / Graffiti": {
            "Vandalismo / Grafiti": {
                "soluciones": ["Escalacion con Implemetaciones", "Reparación por Vandalismo o Grafiti"],
                "slas": {"Escalacion con Implemetaciones": {"min": 24.0, "objetivo": 28, "max": 32}, "Reparación por Vandalismo o Grafiti": {"min": 6.0, "objetivo": 8, "max": 12}}
            },
            "Acabados dañados por ácido": {
                "soluciones": ["Reemplazo de adicional"],
                "slas": {"Reemplazo de adicional": {"min": 24.0, "objetivo": 28, "max": 32}}
            }
        },
        "Robo de Componentes (NUC, UPS, etc.)": {
            "Robo de Componentes (NUC / UPS / Módulos)": {
                "soluciones": ["Reemplazo de Componentes Robados"],
                "slas": {"Reemplazo de Componentes Robados": {"min": 24.0, "objetivo": 28, "max": 32}}
            }
        },
        "Siniestro (Choque, etc.)": {
            "Siniestro (Choque, Impacto, Agua)": {
                "soluciones": ["Atención a Siniestro"],
                "slas": {"Atención a Siniestro": {"min": 24.0, "objetivo": 28, "max": 32}}
            }
        },
        "Obstrucción Física de Equipo o Cámara": {
            "Obstrucción Física de Cámara": {"soluciones": ["Limpieza de Lente"], "slas": {"Limpieza de Lente": {"min": 6, "objetivo": 8, "max": 12}}}
        }
    },
    "Procesos y Gestión": {
        "Discrepancia en Bitácora o Documentación": {
            "Bitácora Incorrecta o Incompleta": {"soluciones": ["Corrección de Registro en Bitácora"], "slas": {"Corrección de Registro en Bitácora": {"min": 0, "objetivo": 0, "max": 0}}}
        },
        "Notificación o Aprobación Faltante": {
            "Falta de Notificación / Aprobación": {"soluciones": ["Confirmación con Área Comercial"], "slas": {"Confirmación con Área Comercial": {"min": 0, "objetivo": 0, "max": 0}}}
        },
        "Falta de Sincronización entre Áreas": {
            "Cambios sin Aviso de Comercial": {"soluciones": ["Ajuste por Solicitud Operativa"], "slas": {"Ajuste por Solicitud Operativa": {"min": 0, "objetivo": 0, "max": 0}}}
        },
        "Consulta de Información": {
            "Falta de Notificación / Aprobación": {"soluciones": ["Confirmación con Área Comercial"], "slas": {"Confirmación con Área Comercial": {"min": 0, "objetivo": 0, "max": 0}}}
        }
    },
    "Mantenimiento y Solicitudes": {
        "Mantenimiento Preventivo (Limpieza, etc.)": {
            "Suciedad": {"soluciones": ["Limpieza de terminales en equipos (Nuc, UPS, Módem, etc)"], "slas": {"Limpieza de terminales en equipos (Nuc, UPS, Módem, etc)": {"min": 2, "objetivo": 3, "max": 4}}},
            "Pendiente de Validación en Campo": {"soluciones": ["Pendiente de Validación en Campo"], "slas": {"Pendiente de Validación en Campo": {"min": 2, "objetivo": 3, "max": 4}}}
        },
        "Soporte para Comprobaciones o Pruebas": {
            "Pendiente de Validación en Campo": {"soluciones": ["Pendiente de Validación en Campo"], "slas": {"Pendiente de Validación en Campo": {"min": 0, "objetivo": 0, "max": 0}}}
        },
        "Solicitud de Cliente (No es una falla)": {
            "Pendiente de Validación en Campo": {"soluciones": ["Pendiente de Validación en Campo"], "slas": {"Pendiente de Validación en Campo": {"min": 0, "objetivo": 0, "max": 0}}}
        },
        "Otro (Describir en notas)": {
            "Incidencia No Determinada": {"soluciones": ["Incidencia No Determinada"], "slas": {"Incidencia No Determinada": {"min": 0, "objetivo": 0, "max": 0}}}
        }
    }
}

print("✅ Catálogo de soporte cargado")
