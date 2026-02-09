"""
Cog principal para el sistema de tickets
"""

import discord
from discord import app_commands
from discord.ext import commands
import datetime
import traceback
import asyncio
import sys
import os
import json
import random

# Ajustar rutas para imports
current_dir = os.path.dirname(__file__)
discord_bot_dir = os.path.dirname(current_dir)
src_dir = os.path.dirname(discord_bot_dir)
project_root = os.path.dirname(src_dir)

if project_root not in sys.path:
    sys.path.insert(0, project_root)

print(f"🎫 Cargando módulo de tickets desde: {current_dir}")

try:
    import discord_bot.config.settings as settings
    print("✅ Configuración cargada correctamente")
except Exception as e:
    print(f"❌ Error cargando configuración: {e}")
    settings = None

def get_conf(key, default):
    """Obtener valor de configuración con fallback"""
    if settings and hasattr(settings, key):
        return getattr(settings, key)
    return os.getenv(key, default)

# Configuración de colores
COLOR_EMBED = get_conf('COLOR_EMBED', 0x3498DB)
COLOR_EXITO = get_conf('COLOR_EXITO', 0x2ECC71)
COLOR_ALERTA = get_conf('COLOR_ALERTA', 0xE74C3C)
COLOR_REASIGNADO = get_conf('COLOR_REASIGNADO', 0x9B59B6)
CANAL_GENERAL_ID = get_conf('CANAL_GENERAL_ID', 1457449842107220123)

# Importar módulos del proyecto
try:
    from discord_bot.core.database import db
    from discord_bot.core.locations import loc_manager
    from discord_bot.utils.catalogo_data import CATALOGO_SOPORTE
    from discord_bot.utils.texto import limpiar_texto
    print("✅ Módulos internos importados correctamente")
except ImportError as e:
    print(f"❌ Error importando módulos internos: {e}")
    traceback.print_exc()
    # Crear stubs para evitar errores
    db = None
    loc_manager = None
    CATALOGO_SOPORTE = {}
    limpiar_texto = lambda x: x

# ==============================================================================
# 📝 MODAL: CIERRE TÉCNICO
# ==============================================================================
class DetallesCierreModal(discord.ui.Modal, title="Detalles Técnicos de Cierre"):
    def __init__(self, view_instance, interaction_origin):
        super().__init__(timeout=300)
        self.view = view_instance
        self.interaction_origin = interaction_origin

        self.area_causante = discord.ui.TextInput(
            label="Área/Depto Causante",
            placeholder="Ej: Operaciones, TI, CFE, Vandalismo...",
            style=discord.TextStyle.short,
            required=True,
            max_length=100
        )
        self.detalles_equipo = discord.ui.TextInput(
            label="¿Qué se hizo al equipo?",
            placeholder="Ej: Cambio de NUC, reinicio físico...",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=500
        )
        self.materiales = discord.ui.TextInput(
            label="Materiales Utilizados",
            placeholder="Ej: Cable UTP, Cinta, Conectores...",
            style=discord.TextStyle.short,
            required=False,
            max_length=200
        )
        self.preventiva = discord.ui.TextInput(
            label="Acción Preventiva",
            placeholder="Ej: Se aseguró el anclaje...",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=500
        )
        self.id_tecnologia = discord.ui.TextInput(
            label="ID Tecnología / Código Equipo",
            placeholder="Ej: NUC-484849856",
            style=discord.TextStyle.short,
            required=False,
            max_length=50
        )

        self.add_item(self.area_causante)
        self.add_item(self.detalles_equipo)
        self.add_item(self.materiales)
        self.add_item(self.preventiva)
        self.add_item(self.id_tecnologia)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            self.view.datos_cierre = {
                "incidencia_causada_por": self.area_causante.value,
                "detalles_equipo": self.detalles_equipo.value,
                "materiales_utilizados": self.materiales.value,
                "accion_preventiva": self.preventiva.value,
                "id_tecnologia": self.id_tecnologia.value
            }
            
            await interaction.response.send_message(
                "📝 Datos guardados.\n📸 **ÚLTIMO PASO: Envía la FOTO DEL TESTIGO (Solución) a este chat ahora.**", 
                ephemeral=True
            )
            await self.view.esperar_foto(interaction)
            
        except Exception as e:
            print(f"❌ Error en DetallesCierreModal.on_submit: {e}")
            await interaction.response.send_message(
                "❌ Ocurrió un error al procesar los datos. Intenta nuevamente.",
                ephemeral=True
            )

# ==============================================================================
# 📝 MODALES Y VISTAS DE REPORTE
# ==============================================================================
class OtroMotivoModal(discord.ui.Modal, title="Detalles del Reporte"):
    def __init__(self, sitio, foto_url, cog_instance):
        super().__init__(timeout=300)
        self.sitio = sitio
        self.foto_url = foto_url
        self.cog = cog_instance
        
        self.descripcion = discord.ui.TextInput(
            label="Describe el problema", 
            style=discord.TextStyle.paragraph, 
            required=True, 
            max_length=500,
            placeholder="Describe detalladamente el problema encontrado..."
        )
        self.motivo_capturado = discord.ui.TextInput(
            label="Título breve", 
            style=discord.TextStyle.short, 
            required=True, 
            max_length=100,
            placeholder="Ej: Falla de energía, Pantalla dañada..."
        )
        
        self.add_item(self.descripcion)
        self.add_item(self.motivo_capturado)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
            
            unidad_detectada = loc_manager.detectar_unidad(self.sitio) if loc_manager else "ECOVALLAS"
            depto_asignado = get_conf('DEPTO_SOPORTE', "Soporte Remoto Digital")
            
            datos = {
                "sitio": self.sitio, 
                "foto_url": self.foto_url, 
                "unidad": unidad_detectada, 
                "depto": depto_asignado,
                "motivo": "Otro", 
                "motivo_capturado": self.motivo_capturado.value, 
                "detalles_extra": self.descripcion.value,
                "usuario": interaction.user.display_name, 
                "usuario_id": interaction.user.id
            }
            
            await self.cog.crear_ticket_final(interaction, datos)
            
        except Exception as e:
            print(f"❌ Error en OtroMotivoModal.on_submit: {e}")
            await interaction.followup.send("❌ Ocurrió un error al crear el ticket.", ephemeral=True)

class ReasignarMotivoModal(discord.ui.Modal, title="Motivo de Reasignación"):
    def __init__(self, ticket_id, datos_originales, nueva_area, cog_instance):
        super().__init__(timeout=300)
        self.ticket_id = ticket_id
        self.datos = datos_originales
        self.nueva_area = nueva_area 
        self.cog = cog_instance
        
        self.campo_motivo = discord.ui.TextInput(
            label=f"¿Por qué reasignas a {nueva_area}?", 
            style=discord.TextStyle.paragraph, 
            required=True,
            max_length=500,
            placeholder="Explica brevemente por qué se reasigna este ticket..."
        )
        self.add_item(self.campo_motivo)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()
            
            motivo_limpio = limpiar_texto(self.campo_motivo.value)
            
            if db:
                await db.registrar_reasignacion(self.ticket_id, self.nueva_area, motivo_limpio, interaction.user.display_name)
            
            depto_anterior = self.datos.get('depto', 'Desconocido')
            self.datos['depto'] = self.nueva_area
            
            embed = discord.Embed(
                title=f"🔄 TICKET REASIGNADO: {self.ticket_id}",
                color=COLOR_REASIGNADO
            )
            embed.description = "**El ticket cambia de responsable.**"
            embed.add_field(name="📤 De", value=f"~~{depto_anterior}~~", inline=True)
            embed.add_field(name="📥 A", value=f"**{self.nueva_area}**", inline=True)
            embed.add_field(name="📝 Motivo", value=motivo_limpio, inline=False)
            embed.add_field(name="👤 Por", value=interaction.user.display_name, inline=False)
            embed.set_footer(text=f"Ticket ID: {self.ticket_id}")
            
            await interaction.followup.send(embed=embed)
            
            if self.cog:
                await self.cog.notificar_nuevo_responsable(self.ticket_id, self.datos, motivo_limpio)
                
        except Exception as e:
            print(f"❌ Error en ReasignarMotivoModal.on_submit: {e}")
            await interaction.followup.send("❌ Error al reasignar el ticket.", ephemeral=True)

class ReasignarSeleccionView(discord.ui.View):
    def __init__(self, ticket_id, datos_ticket, cog_instance, timeout=60):
        super().__init__(timeout=timeout)
        self.ticket_id = ticket_id
        self.datos = datos_ticket
        self.cog = cog_instance
        
        # Obtener departamentos de la configuración
        deptos = get_conf('DEPARTAMENTOS', {})
        opciones = []
        
        for nombre_depto, config in deptos.items():
            if nombre_depto != datos_ticket.get('depto', ''):
                emoji = "➡️"
                if nombre_depto == get_conf('DEPTO_SOPORTE', ''):
                    emoji = "💻"
                elif nombre_depto == get_conf('DEPTO_PAUTA', ''):
                    emoji = "📺"
                elif nombre_depto == get_conf('DEPTO_CAMPO', ''):
                    emoji = "🔧"
                    
                opciones.append(discord.SelectOption(
                    label=nombre_depto[:100], 
                    value=nombre_depto[:100],
                    emoji=emoji
                ))
        
        if not opciones:
            opciones.append(discord.SelectOption(
                label="Sin departamentos disponibles", 
                value="N/A",
                emoji="⚠️"
            ))
        
        self.select_menu = discord.ui.Select(
            placeholder="Selecciona nuevo equipo...", 
            options=opciones,
            custom_id=f"reasignar_{ticket_id}"
        )
        self.select_menu.callback = self.callback_menu
        self.add_item(self.select_menu)

    async def callback_menu(self, interaction: discord.Interaction):
        area = self.select_menu.values[0]
        if area == "N/A":
            await interaction.response.send_message("❌ No hay departamentos disponibles para reasignar.", ephemeral=True)
            return
        
        await interaction.response.send_modal(
            ReasignarMotivoModal(self.ticket_id, self.datos, area, self.cog)
        )

# ==============================================================================
# 🧙‍♂️ WIZARD DE RESOLUCIÓN
# ==============================================================================
class ResolucionWizardView(discord.ui.View):
    def __init__(self, ticket_id, cog_instance, datos_ticket, mensaje_controles, timeout=600):
        super().__init__(timeout=timeout)
        self.ticket_id = ticket_id
        self.cog = cog_instance
        self.datos_ticket = datos_ticket
        self.mensaje_controles = mensaje_controles
        self.datos_cierre = {}
        self.seleccion = {
            "categoria": None, 
            "incidencia": None, 
            "causa": None, 
            "solucion": None, 
            "foto_solucion": None
        }
        
        # Crear opciones para categorías
        opciones_cat = []
        for cat in CATALOGO_SOPORTE.keys():
            emoji = "🔧"
            if "Conectividad" in cat:
                emoji = "🌐"
            elif "Hardware" in cat:
                emoji = "💻"
            elif "Eléctrica" in cat:
                emoji = "⚡"
            elif "Software" in cat:
                emoji = "📱"
            elif "Contenido" in cat:
                emoji = "🎨"
                
            opciones_cat.append(discord.SelectOption(
                label=cat[:100], 
                value=cat[:100],
                emoji=emoji
            ))
        
        self.sel_categoria = discord.ui.Select(
            placeholder="1️⃣ Selecciona Categoría Principal", 
            options=opciones_cat[:25], 
            custom_id=f"cat_{ticket_id}"
        )
        self.sel_categoria.callback = self.on_categoria_change
        self.add_item(self.sel_categoria)

    async def on_categoria_change(self, interaction: discord.Interaction):
        try:
            self.seleccion["categoria"] = self.sel_categoria.values[0]
            
            # Limpiar vista y mantener solo la categoría seleccionada
            self.clear_items()
            self.add_item(self.sel_categoria)
            
            # Obtener incidencias para la categoría seleccionada
            if self.seleccion["categoria"] in CATALOGO_SOPORTE:
                incidencias = list(CATALOGO_SOPORTE[self.seleccion["categoria"]].keys())
                opciones_inc = []
                
                for inc in incidencias[:25]:
                    emoji = "⚠️"
                    if "Pantalla" in inc:
                        emoji = "📺"
                    elif "Internet" in inc or "Red" in inc:
                        emoji = "🌐"
                    elif "Energía" in inc or "Eléctric" in inc:
                        emoji = "⚡"
                        
                    opciones_inc.append(discord.SelectOption(
                        label=inc[:100], 
                        value=inc[:100],
                        emoji=emoji
                    ))
                
                self.sel_incidencia = discord.ui.Select(
                    placeholder="2️⃣ Tipo de Incidencia", 
                    options=opciones_inc, 
                    custom_id=f"inc_{self.ticket_id}"
                )
                self.sel_incidencia.callback = self.on_incidencia_change
                self.add_item(self.sel_incidencia)
                
                await interaction.response.edit_message(
                    content=f"✅ **Categoría:** {self.seleccion['categoria']}\n\n📂 **Paso 2:** Selecciona la Incidencia:",
                    view=self
                )
            else:
                await interaction.response.send_message(
                    "❌ Categoría no encontrada en el catálogo.", 
                    ephemeral=True
                )
                
        except Exception as e:
            print(f"❌ Error en on_categoria_change: {e}")
            await interaction.response.send_message(
                "❌ Error al procesar la selección.", 
                ephemeral=True
            )

    async def on_incidencia_change(self, interaction: discord.Interaction):
        try:
            self.seleccion["incidencia"] = self.sel_incidencia.values[0]
            
            # Limpiar vista y mantener selecciones anteriores
            self.clear_items()
            self.add_item(self.sel_categoria)
            self.add_item(self.sel_incidencia)
            
            # Obtener causas para la incidencia seleccionada
            cat = self.seleccion["categoria"]
            inc = self.seleccion["incidencia"]
            
            if cat in CATALOGO_SOPORTE and inc in CATALOGO_SOPORTE[cat]:
                causas = list(CATALOGO_SOPORTE[cat][inc].keys())
                opciones_causa = []
                
                for c in causas[:25]:
                    emoji = "🔍"
                    if "Hardware" in c or "Física" in c:
                        emoji = "💻"
                    elif "Software" in c or "Configuración" in c:
                        emoji = "⚙️"
                    elif "Proveedor" in c or "Externo" in c:
                        emoji = "🏢"
                        
                    opciones_causa.append(discord.SelectOption(
                        label=c[:100], 
                        value=c[:100],
                        emoji=emoji
                    ))
                
                self.sel_causa = discord.ui.Select(
                    placeholder="3️⃣ Causa Raíz", 
                    options=opciones_causa, 
                    custom_id=f"causa_{self.ticket_id}"
                )
                self.sel_causa.callback = self.on_causa_change
                self.add_item(self.sel_causa)
                
                await interaction.response.edit_message(
                    content=f"✅ **Incidencia:** {self.seleccion['incidencia']}\n\n🔍 **Paso 3:** ¿Cuál fue la causa?",
                    view=self
                )
            else:
                await interaction.response.send_message(
                    "❌ Incidencia no encontrada en el catálogo.", 
                    ephemeral=True
                )
                
        except Exception as e:
            print(f"❌ Error en on_incidencia_change: {e}")
            await interaction.response.send_message(
                "❌ Error al procesar la selección.", 
                ephemeral=True
            )

    async def on_causa_change(self, interaction: discord.Interaction):
        try:
            self.seleccion["causa"] = self.sel_causa.values[0]
            
            # Limpiar vista y mantener selecciones anteriores
            self.clear_items()
            self.add_item(self.sel_categoria)
            self.add_item(self.sel_incidencia)
            self.add_item(self.sel_causa)
            
            # Obtener soluciones para la causa seleccionada
            cat = self.seleccion["categoria"]
            inc = self.seleccion["incidencia"]
            cau = self.seleccion["causa"]
            
            if (cat in CATALOGO_SOPORTE and 
                inc in CATALOGO_SOPORTE[cat] and 
                cau in CATALOGO_SOPORTE[cat][inc]):
                
                nodo_data = CATALOGO_SOPORTE[cat][inc][cau]
                
                # Determinar si es un dict con soluciones o una lista directa
                if isinstance(nodo_data, dict) and "soluciones" in nodo_data:
                    lista = nodo_data["soluciones"]
                elif isinstance(nodo_data, list):
                    lista = nodo_data
                else:
                    lista = []
                
                opciones_sol = []
                for s in lista[:25]:
                    emoji = "🛠️"
                    if "Reinicio" in s:
                        emoji = "🔁"
                    elif "Cambio" in s or "Reemplazo" in s:
                        emoji = "🔄"
                    elif "Configuración" in s or "Ajuste" in s:
                        emoji = "⚙️"
                    elif "Escalamiento" in s:
                        emoji = "📞"
                        
                    opciones_sol.append(discord.SelectOption(
                        label=s[:100], 
                        value=s[:100],
                        emoji=emoji
                    ))
                
                if opciones_sol:
                    self.sel_solucion = discord.ui.Select(
                        placeholder="4️⃣ Pasos de Solución", 
                        options=opciones_sol, 
                        custom_id=f"sol_{self.ticket_id}"
                    )
                    self.sel_solucion.callback = self.on_solucion_change
                    self.add_item(self.sel_solucion)
                    
                    await interaction.response.edit_message(
                        content=f"✅ **Causa:** {self.seleccion['causa']}\n\n🛠️ **Paso 4:** ¿Cómo se solucionó?",
                        view=self
                    )
                else:
                    await interaction.response.send_message(
                        "❌ No hay soluciones disponibles para esta causa.", 
                        ephemeral=True
                    )
            else:
                await interaction.response.send_message(
                    "❌ Causa no encontrada en el catálogo.", 
                    ephemeral=True
                )
                
        except Exception as e:
            print(f"❌ Error en on_causa_change: {e}")
            await interaction.response.send_message(
                "❌ Error al procesar la selección.", 
                ephemeral=True
            )

    async def on_solucion_change(self, interaction: discord.Interaction):
        try:
            self.seleccion["solucion"] = self.sel_solucion.values[0]
            await interaction.response.send_modal(
                DetallesCierreModal(self, interaction)
            )
        except Exception as e:
            print(f"❌ Error en on_solucion_change: {e}")
            await interaction.response.send_message(
                "❌ Error al abrir el formulario de cierre.", 
                ephemeral=True
            )

    async def esperar_foto(self, interaction: discord.Interaction):
        def check(m):
            return (
                m.author == interaction.user and 
                m.channel == interaction.channel and 
                len(m.attachments) > 0 and
                m.attachments[0].content_type.startswith("image/")
            )
        
        try:
            await interaction.followup.send(
                "⏳ Esperando foto de solución... (Tienes 2 minutos)",
                ephemeral=True
            )
            
            mensaje_foto = await self.cog.bot.wait_for('message', check=check, timeout=120.0)
            self.seleccion["foto_solucion"] = mensaje_foto.attachments[0].url
            
            # Intentar eliminar el mensaje de la foto para mantener el chat limpio
            try:
                await mensaje_foto.delete()
            except:
                pass
                
            await self.finalizar_ticket(interaction)
            
        except asyncio.TimeoutError:
            try:
                await interaction.followup.send(
                    "❌ Tiempo agotado. No se recibió la foto de solución.",
                    ephemeral=True
                )
            except:
                pass
        except Exception as e:
            print(f"❌ Error en esperar_foto: {e}")
            try:
                await interaction.followup.send(
                    "❌ Error al recibir la foto. Intenta nuevamente.",
                    ephemeral=True
                )
            except:
                pass

    async def finalizar_ticket(self, interaction: discord.Interaction):
        try:
            # Desactivar controles del mensaje original
            if self.mensaje_controles:
                try:
                    await self.mensaje_controles.edit(view=None, content="🔒 **Ticket Cerrado**")
                except:
                    pass

            # Preparar datos de resolución
            cat = self.seleccion["categoria"]
            inc = self.seleccion["incidencia"]
            cau = self.seleccion["causa"]
            
            # Obtener tiempos SLA del catálogo
            tiempos_sla = {"min": 24, "objetivo": 28, "max": 32}
            try:
                if (cat in CATALOGO_SOPORTE and 
                    inc in CATALOGO_SOPORTE[cat] and 
                    cau in CATALOGO_SOPORTE[cat][inc]):
                    
                    nodo_data = CATALOGO_SOPORTE[cat][inc][cau]
                    if isinstance(nodo_data, dict) and "slas" in nodo_data:
                        solucion_key = self.seleccion["solucion"]
                        if solucion_key in nodo_data["slas"]:
                            tiempos_sla = nodo_data["slas"][solucion_key]
            except:
                pass
            
            # Contar reincidencias
            reincidencias = 0
            if db and 'sitio' in self.datos_ticket and 'motivo_capturado' in self.datos_ticket:
                reincidencias = await db.contar_reincidencias(
                    self.datos_ticket['sitio'], 
                    self.datos_ticket.get('motivo_capturado', '')
                )
            
            # Determinar prioridad y urgencia
            prioridad = "Media"
            urgencia = "Media"
            if "Pantalla" in inc or "Apagada" in inc or "Dañada" in inc:
                prioridad = "Alta"
                urgencia = "Alta"
            elif "Internet" in inc or "Red" in inc:
                prioridad = "Media"
                urgencia = "Media"
            else:
                prioridad = "Baja"
                urgencia = "Baja"
            
            # Datos completos para la base de datos
            datos_resolucion = {
                "solucion_brindada": self.seleccion["solucion"],
                "causa_raiz": self.seleccion["causa"],
                "area_causante": self.datos_cierre.get("incidencia_causada_por", ""), 
                "incidencia_causada_por": self.seleccion["categoria"], 
                "categoria_principal": self.seleccion["categoria"],
                "incidencia": self.seleccion["incidencia"],
                "foto_solucion": self.seleccion["foto_solucion"], 
                "testigo_solucion": self.seleccion["foto_solucion"],
                "cerrado_por": interaction.user.display_name,
                "modificado_por": interaction.user.display_name,
                "quien_toma_incidencia": interaction.user.display_name,
                "descripcion_solucion": self.seleccion["solucion"],
                "tiempo_minimo_sla": tiempos_sla["min"],
                "tiempo_sla_objetivo": tiempos_sla["objetivo"],
                "tiempo_fuera_sla": tiempos_sla["max"],
                "id_tecnologia": self.datos_cierre.get("id_tecnologia", ""),
                "detalles_equipo": self.datos_cierre.get("detalles_equipo", ""),
                "materiales_utilizados": self.datos_cierre.get("materiales_utilizados", ""),
                "accion_preventiva": self.datos_cierre.get("accion_preventiva", ""),
                "reincidencias": reincidencias,
                "prioridad": prioridad,
                "urgencia": urgencia,
                "impacto": "Afectación de Servicio",
                "se_notifico_a": self.datos_ticket.get('depto', ''), 
            }
            
            # Actualizar en base de datos
            if db:
                await db.actualizar_estatus(self.ticket_id, "Resuelto", datos_resolucion)
            
            # Crear embed de resolución
            embed = discord.Embed(
                title="✅ TICKET RESUELTO Y CERRADO",
                description=f"Ticket **{self.ticket_id}** ha sido completado exitosamente.",
                color=COLOR_EXITO,
                timestamp=datetime.datetime.now()
            )
            
            embed.add_field(name="🆔 ID", value=self.ticket_id, inline=True)
            embed.add_field(name="📍 Sitio", value=self.datos_ticket.get('sitio', 'N/A'), inline=True)
            embed.add_field(name="🛠️ Solución", value=datos_resolucion['solucion_brindada'], inline=False)
            embed.add_field(name="🚨 Área Causante", value=datos_resolucion['area_causante'], inline=True)
            embed.add_field(name="📋 Detalles Equipo", value=datos_resolucion['detalles_equipo'][:100] + "..." if len(datos_resolucion['detalles_equipo']) > 100 else datos_resolucion['detalles_equipo'], inline=False)
            
            if datos_resolucion['materiales_utilizados']:
                embed.add_field(name="📦 Materiales", value=datos_resolucion['materiales_utilizados'], inline=True)
            
            embed.add_field(name="👷 Cerrado por", value=interaction.user.display_name, inline=True)
            
            if datos_resolucion['foto_solucion']:
                embed.set_image(url=datos_resolucion['foto_solucion'])
            
            embed.set_footer(text=f"Ticket ID: {self.ticket_id} • {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}")
            
            # Enviar embed al canal/hilo
            if isinstance(interaction.channel, discord.Thread):
                await interaction.channel.send(embed=embed)
            else:
                await interaction.followup.send(embed=embed)
            
            # Notificar cierre global
            if self.cog:
                await self.cog.notificar_cierre_global(self.ticket_id, self.datos_ticket, datos_resolucion)
            
            # Cerrar hilo después de un tiempo
            await self.cerrar_hilo_fisico(interaction, embed)
            
        except Exception as e:
            print(f"❌ Error en finalizar_ticket: {e}")
            traceback.print_exc()
            try:
                await interaction.followup.send(
                    "❌ Error al finalizar el ticket. Contacta al administrador.",
                    ephemeral=True
                )
            except:
                pass

    async def cerrar_hilo_fisico(self, interaction, embed_final):
        try:
            await asyncio.sleep(5)  # Esperar 5 segundos antes de archivar
            
            if isinstance(interaction.channel, discord.Thread):
                await interaction.channel.edit(
                    archived=True, 
                    locked=True,
                    reason=f"Ticket {self.ticket_id} resuelto por {interaction.user.display_name}"
                )
                print(f"✅ Hilo archivado: {interaction.channel.name}")
        except Exception as e:
            print(f"⚠️ No se pudo archivar el hilo: {e}")

# ==============================================================================
# 🔘 BOTONES Y VISTAS PRINCIPALES
# ==============================================================================
class AccionesTicketView(discord.ui.View):
    def __init__(self, ticket_id, datos_ticket, cog_instance, solo_reasignar=False, hilo_url=None, timeout=None):
        super().__init__(timeout=timeout)
        self.ticket_id = ticket_id
        self.datos = datos_ticket
        self.cog = cog_instance
        
        # 🟢 LÓGICA DINÁMICA DE BOTONES
        if solo_reasignar:
            # Eliminar botón "Resolver" (es el primero)
            for child in self.children[:]:
                if getattr(child, "custom_id", "") == f"btn_resolver_{ticket_id}":
                    self.remove_item(child)
                    break
            
            # Agregar botón de enlace al hilo si existe
            if hilo_url:
                self.add_item(discord.ui.Button(
                    label="🔗 Ir al Hilo del Ticket", 
                    style=discord.ButtonStyle.link, 
                    url=hilo_url,
                    emoji="🔗"
                ))

    @discord.ui.button(label="✅ Resolver", style=discord.ButtonStyle.success, custom_id="btn_resolver", emoji="✅")
    async def btn_resolver(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 🔒 RESTRICCIÓN DE HILOS
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.response.send_message(
                "❌ **ACCIÓN DENEGADA:** Los tickets solo pueden resolverse dentro de su hilo correspondiente.", 
                ephemeral=True
            )
            return
        
        # Verificar permisos (opcional)
        # if not interaction.user.guild_permissions.manage_messages:
        #     await interaction.response.send_message("❌ No tienes permisos para resolver tickets.", ephemeral=True)
        #     return
        
        try:
            # Actualizar estatus a "En Proceso"
            if db:
                await db.actualizar_estatus(
                    self.ticket_id, 
                    "En Proceso", 
                    {"quien_toma_incidencia": interaction.user.display_name}
                )
            
            # Crear vista del wizard de resolución
            view_wizard = ResolucionWizardView(
                self.ticket_id, 
                self.cog, 
                self.datos, 
                interaction.message
            )
            
            await interaction.response.send_message(
                "📂 **Asistente de Cierre:** Selecciona la categoría principal:", 
                view=view_wizard, 
                ephemeral=True
            )
            
        except Exception as e:
            print(f"❌ Error en btn_resolver: {e}")
            await interaction.response.send_message(
                "❌ Error al iniciar el proceso de resolución.", 
                ephemeral=True
            )

    @discord.ui.button(label="🔄 Reasignar", style=discord.ButtonStyle.secondary, custom_id="btn_reasignar", emoji="🔄")
    async def btn_reasignar(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            view_menu = ReasignarSeleccionView(self.ticket_id, self.datos, self.cog)
            await interaction.response.send_message(
                "📍 **Reasignación:** Elige el nuevo equipo responsable:", 
                view=view_menu, 
                ephemeral=True
            )
        except Exception as e:
            print(f"❌ Error en btn_reasignar: {e}")
            await interaction.response.send_message(
                "❌ Error al iniciar la reasignación.", 
                ephemeral=True
            )

class SeleccionMotivoView(discord.ui.View):
    def __init__(self, sitio, foto_url, cog_instance, timeout=300):
        super().__init__(timeout=timeout)
        self.sitio = sitio
        self.foto_url = foto_url
        self.cog = cog_instance

    @discord.ui.select(
        placeholder="Selecciona el Motivo del Reporte", 
        options=[
            discord.SelectOption(label="Pantalla Apagada", emoji="⚫", description="Pantalla sin imagen o apagada"),
            discord.SelectOption(label="Pantalla Dañada", emoji="🔨", description="Daño físico en la pantalla"),
            discord.SelectOption(label="Grafiti", emoji="🎨", description="Pintas o graffiti en la estructura"),
            discord.SelectOption(label="No se visualiza Pauta", emoji="🚫", description="Contenido no visible"),
            discord.SelectOption(label="Pauta Incorrecta", emoji="⚠️", description="Contenido incorrecto"),
            discord.SelectOption(label="Otro", emoji="❓", description="Otro tipo de problema")
        ],
        custom_id="select_motivo"
    )
    async def select_motivo(self, interaction: discord.Interaction, select: discord.ui.Select):
        motivo = select.values[0]
        
        if motivo == "Otro":
            await interaction.response.send_modal(
                OtroMotivoModal(self.sitio, self.foto_url, self.cog)
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            unidad_detectada = loc_manager.detectar_unidad(self.sitio) if loc_manager else "ECOVALLAS"
            
            # Obtener departamento asignado según el motivo
            mapa_motivos = get_conf('MAPA_MOTIVOS', {})
            depto_asignado = mapa_motivos.get(motivo, get_conf('DEPTO_SOPORTE', "Soporte Remoto Digital"))
            
            datos = {
                "sitio": self.sitio, 
                "foto_url": self.foto_url, 
                "unidad": unidad_detectada, 
                "depto": depto_asignado,
                "motivo": motivo, 
                "motivo_capturado": motivo, 
                "seccion": "Reporte Inicial",
                "usuario": interaction.user.display_name, 
                "usuario_id": interaction.user.id
            }
            
            await self.cog.crear_ticket_final(interaction, datos)
            
        except Exception as e:
            print(f"❌ Error en select_motivo: {e}")
            await interaction.followup.send("❌ Error al crear el ticket.", ephemeral=True)

# ==============================================================================
# ⚙️ COMANDO PRINCIPAL - SISTEMA DE TICKETS
# ==============================================================================
class SistemaTickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        print("✅ Cog SistemaTickets inicializado")

    # Autocompletado para sitios
    async def sitio_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        try:
            if not loc_manager:
                return []
            
            resultados = loc_manager.buscar(current, limite=10)
            return [
                app_commands.Choice(name=r[:100], value=r[:100]) 
                for r in resultados
            ]
        except Exception as e:
            print(f"❌ Error en autocomplete: {e}")
            return []

    @app_commands.command(name="reporte", description="Reportar una incidencia o problema")
    @app_commands.describe(
        sitio="Busca y selecciona la ubicación del problema",
        foto="Evidencia obligatoria (imagen)"
    )
    @app_commands.autocomplete(sitio=sitio_autocomplete)
    async def reporte(self, interaction: discord.Interaction, sitio: str, foto: discord.Attachment):
        """Comando principal para reportar incidencias"""
        try:
            # Validar que sea una imagen
            if not foto.content_type or not foto.content_type.startswith("image/"):
                await interaction.response.send_message(
                    "❌ Debes adjuntar una imagen como evidencia (JPEG, PNG, etc.).", 
                    ephemeral=True
                )
                return
            
            await interaction.response.defer(ephemeral=True)
            
            # Crear embed de confirmación
            embed = discord.Embed(
                title="📋 Nuevo Reporte",
                description=f"📍 **Sitio:** {sitio}\n📂 **Selecciona el problema:**",
                color=COLOR_EMBED,
                timestamp=datetime.datetime.now()
            )
            embed.set_thumbnail(url=foto.url)
            embed.set_footer(text=f"Reportado por {interaction.user.display_name}")
            
            await interaction.followup.send(
                embed=embed, 
                view=SeleccionMotivoView(sitio, foto.url, self), 
                ephemeral=True
            )
            
        except Exception as e:
            print(f"❌ Error en comando /reporte: {e}")
            traceback.print_exc()
            
            try:
                await interaction.followup.send(
                    "❌ Ocurrió un error al procesar el reporte. Intenta nuevamente.", 
                    ephemeral=True
                )
            except:
                pass

    async def crear_ticket_final(self, interaction, datos):
        """Crear ticket final en la base de datos"""
        try:
            depto = datos.get('depto', '')
            
            # Determinar SLA según departamento
            if depto in [get_conf('DEPTO_SOPORTE', ''), get_conf('DEPTO_PAUTA', '')]:
                sla_val = "4"  # Horas para soporte y pauta
            else:
                sla_val = "24"  # Horas para otros departamentos
            
            # Preparar datos para la base de datos
            datos_db = {
                "Sitio": datos.get('sitio', ''),
                "Unidad_de_negocio": datos.get('unidad', ''),
                "Departamento_Reporta": datos.get('depto', ''),
                "Quien_toma_la_incidencia": "",  # Se llena cuando alguien toma el ticket
                "Motivo_Capturado": datos.get('motivo_capturado', ''),
                "Detalles_Extra": datos.get('detalles_extra', ''),
                "Usuario_Reporta": datos.get('usuario', ''),
                "Usuario_ID": str(datos.get('usuario_id', '')),
                "Foto_URL": datos.get('foto_url', ''), 
                "Testigo_Incidencia": datos.get('foto_url', ''), 
                "Estatus": "Abierto",
                "SLA_Horas": sla_val
            }
            
            # Crear ticket en la base de datos
            nuevo_id = None
            if db:
                nuevo_id = await db.crear_ticket(datos_db)
            
            if nuevo_id:
                ahora = datetime.datetime.now()
                datos['ticket_id'] = nuevo_id
                
                await interaction.followup.send(
                    f"✅ **TICKET CREADO EXITOSAMENTE**\n"
                    f"**ID:** `{nuevo_id}`\n"
                    f"**Sitio:** {datos.get('sitio', 'N/A')}\n"
                    f"**Departamento:** {datos.get('depto', 'N/A')}\n"
                    f"**Hora:** {ahora.strftime('%H:%M')}",
                    ephemeral=True
                )
                
                # Crear hilo para el ticket
                await self.crear_hilo_inicial(nuevo_id, datos)
                
            else:
                await interaction.followup.send(
                    "❌ Error al crear el ticket en la base de datos.", 
                    ephemeral=True
                )
                
        except Exception as e:
            print(f"❌ Error en crear_ticket_final: {e}")
            traceback.print_exc()
            
            try:
                await interaction.followup.send(
                    "❌ Error crítico al crear el ticket. Contacta al administrador.", 
                    ephemeral=True
                )
            except:
                pass

    async def crear_hilo_inicial(self, ticket_id, datos):
        """Crear hilo de Discord para el ticket"""
        try:
            canal_general = self.bot.get_channel(CANAL_GENERAL_ID)
            if not canal_general:
                print(f"❌ No se encontró el canal general con ID: {CANAL_GENERAL_ID}")
                return
            
            # Crear embed para el hilo
            embed = discord.Embed(
                title=f"🚨 Incidencia: {datos.get('unidad', 'ECOVALLAS')}",
                description=f"Nuevo ticket creado",
                color=COLOR_ALERTA,
                timestamp=datetime.datetime.now()
            )
            
            embed.add_field(name="🆔 Ticket", value=f"`{ticket_id}`", inline=True)
            embed.add_field(name="⚠️ Motivo", value=datos.get('motivo_capturado', 'N/A'), inline=True)
            embed.add_field(name="👷 Depto", value=datos.get('depto', 'N/A'), inline=True)
            embed.add_field(name="📍 Sitio", value=datos.get('sitio', 'N/A'), inline=False)
            
            if datos.get('detalles_extra'):
                embed.add_field(name="📝 Descripción", value=datos.get('detalles_extra', '')[:500], inline=False)
            
            embed.add_field(name="👤 Reportó", value=datos.get('usuario', 'N/A'), inline=True)
            
            if datos.get('foto_url'):
                embed.set_image(url=datos.get('foto_url'))
            
            embed.set_footer(text=f"Ticket ID: {ticket_id}")
            
            # Crear nombre del hilo
            nombre_hilo = f"🔴 {ticket_id} | {datos.get('motivo_capturado', 'Incidencia')[:30]}"
            
            # Crear hilo en el canal general
            hilo = await canal_general.create_thread(
                name=nombre_hilo,
                type=discord.ChannelType.public_thread,
                reason=f"Nuevo ticket {ticket_id}"
            )
            
            # Enviar embed con botones de acción en el hilo
            await hilo.send(
                embed=embed, 
                view=AccionesTicketView(ticket_id, datos, self)
            )
            
            # Notificar al usuario que creó el ticket
            if 'usuario_id' in datos:
                try:
                    await hilo.send(f"<@{datos['usuario_id']}> se ha creado tu ticket.")
                except:
                    pass
            
            # Notificar al departamento responsable
            await self.notificar_nuevo_responsable(
                ticket_id, 
                datos, 
                hilo_url=hilo.jump_url
            )
            
            print(f"✅ Hilo creado: {hilo.name} (ID: {hilo.id})")
            
        except Exception as e:
            print(f"❌ Error en crear_hilo_inicial: {e}")
            traceback.print_exc()

    async def notificar_nuevo_responsable(self, ticket_id, datos, nota_extra="", hilo_url=None):
        """Notificar al departamento responsable del nuevo ticket"""
        try:
            deptos = get_conf('DEPARTAMENTOS', {})
            config_depto = deptos.get(datos.get('depto', ''))
            
            if config_depto:
                canal = self.bot.get_channel(config_depto.get('canal_id'))
                
                if canal:
                    embed = discord.Embed(
                        title=f"🔔 Nuevo Ticket Asignado: {ticket_id}",
                        description=f"Se te ha asignado un nuevo ticket.",
                        color=COLOR_EMBED,
                        timestamp=datetime.datetime.now()
                    )
                    
                    embed.add_field(name="Sitio", value=datos.get('sitio', 'N/A'), inline=True)
                    embed.add_field(name="Motivo", value=datos.get('motivo_capturado', 'N/A'), inline=True)
                    embed.add_field(name="Reportado por", value=datos.get('usuario', 'N/A'), inline=True)
                    
                    if nota_extra:
                        embed.add_field(name="Nota", value=nota_extra, inline=False)
                    
                    embed.set_footer(text=f"Ticket ID: {ticket_id}")
                    
                    # Vista para notificación al grupo (solo reasignar + link)
                    view_grupo = AccionesTicketView(
                        ticket_id, 
                        datos, 
                        self, 
                        solo_reasignar=True, 
                        hilo_url=hilo_url
                    )
                    
                    # Notificar con mención al rol
                    mensaje = f"<@&{config_depto.get('rol_id', '')}>"
                    await canal.send(mensaje, embed=embed, view=view_grupo)
                    
                    print(f"✅ Notificación enviada a {datos.get('depto')}")
                    
        except Exception as e:
            print(f"❌ Error en notificar_nuevo_responsable: {e}")

    async def notificar_cierre_global(self, ticket_id, datos_ticket, datos_res):
        """Notificar cierre del ticket a todos los canales relevantes"""
        try:
            embed = discord.Embed(
                title=f"🏁 Ticket Resuelto: {ticket_id}",
                description=f"El ticket ha sido cerrado exitosamente.",
                color=COLOR_EXITO,
                timestamp=datetime.datetime.now()
            )
            
            embed.add_field(name="Solución", value=datos_res.get('solucion_brindada', 'N/A'), inline=True)
            embed.add_field(name="Cerrado por", value=datos_res.get('cerrado_por', 'N/A'), inline=True)
            embed.add_field(name="Tiempo Total", value=datos_res.get('tiempo_solucion_total', 'N/A'), inline=True)
            
            if datos_res.get('foto_solucion'):
                embed.set_thumbnail(url=datos_res.get('foto_solucion'))
            
            embed.set_footer(text=f"Ticket ID: {ticket_id}")
            
            # Enviar al canal general
            canal_general = self.bot.get_channel(CANAL_GENERAL_ID)
            if canal_general:
                await canal_general.send(embed=embed)
            
            # Enviar al departamento responsable
            deptos = get_conf('DEPARTAMENTOS', {})
            config_depto = deptos.get(datos_ticket.get('depto', ''))
            
            if config_depto:
                canal = self.bot.get_channel(config_depto.get('canal_id'))
                if canal:
                    await canal.send(embed=embed)
            
            print(f"✅ Notificación de cierre enviada para ticket {ticket_id}")
            
        except Exception as e:
            print(f"❌ Error en notificar_cierre_global: {e}")

async def setup(bot):
    """Setup del cog"""
    try:
        await bot.add_cog(SistemaTickets(bot))
        print("✅ Cog SistemaTickets agregado al bot")
    except Exception as e:
        print(f"❌ Error agregando cog SistemaTickets: {e}")
        traceback.print_exc()
