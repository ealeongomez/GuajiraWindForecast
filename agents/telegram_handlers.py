# ==============================================================================
# Project: GuajiraClimateAgents
# File: telegram_handlers.py
# Description:
#   Handlers de Telegram organizados en clases para mejor estructura y mantenibilidad
# Author: Eder Arley León Gómez (con ayuda de ChatGPT)
# Created on: 2025-01-09
# ==============================================================================

import os
import re
import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, List
from abc import ABC, abstractmethod

import pandas as pd
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import ContextTypes

from langchain_openai import ChatOpenAI
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain_experimental.agents.agent_toolkits.pandas.base import create_pandas_dataframe_agent

# Agregar el directorio src al path
sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from prompts import (
    router_prompt_template,
    subagent_prompt_template,
    MUNICIPIOS,
    TEMAS,
    FAREWELL_PATTERNS,
    CLIMATE_KEYWORDS
)
from prompts.pandas_agent_prompt import SYSTEM_PROMPT
from api.dataDownload import ClimateDataDownloader

logger = logging.getLogger(__name__)

# ==============================================================================
# 📱 Estado del usuario en Telegram
# ==============================================================================
class UserState:
    def __init__(self):
        self.current_municipio: Optional[str] = None
        self.current_data_summary: Optional[str] = None
        self.current_file_path: Optional[str] = None
        self.current_dataframe: Optional[pd.DataFrame] = None
        self.pandas_agent: Optional[object] = None
        self.last_activity: datetime = datetime.now()

# Almacenar estado por usuario
user_states: Dict[int, UserState] = {}

def get_user_state(user_id: int) -> UserState:
    """Obtiene o crea el estado del usuario"""
    if user_id not in user_states:
        user_states[user_id] = UserState()
    return user_states[user_id]

# ==============================================================================
# 📊 PlotHandler - Manejo de gráficos
# ==============================================================================
class PlotHandler:
    def __init__(self, charts_dir: Path, project_root: Path):
        self.charts_dir = charts_dir
        self.project_root = project_root
        self.charts_dir.mkdir(parents=True, exist_ok=True)
        
        # Configurar matplotlib sin GUI
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        plt.ioff()
    
    def is_plot_request(self, text: str) -> bool:
        """Detecta si la consulta solicita un gráfico"""
        plot_keywords = ["gráfica", "grafica", "gráfico", "grafico", "plot", "chart", 
            "diagrama", "histograma", "boxplot", "scatter", "línea", "linea", "barras", 
            "pie", "visualizar", "visualiza", "mostrar", "ver", "dibujar", "graficar",
            "graficar", "plotear", "diagramar"]
        return any(kw in text.lower() for kw in plot_keywords)
    
    def extract_code(self, response: str) -> str:
        """Extrae código Python de la respuesta del agente"""
        for pattern in [r'```python\s*(.*?)\s*```', r'```\s*(.*?)\s*```']:
            match = re.search(pattern, response, re.DOTALL)
            if match:
                code = match.group(1).strip()
                if any(lib in code for lib in ['plt.', 'sns.', 'matplotlib', 'seaborn']):
                    return code
        return ""
    
    def execute_plot_code(self, code: str, df: pd.DataFrame) -> str:
        """Ejecuta código de gráfico y guarda la imagen"""
        try:
            import matplotlib.pyplot as plt
            import seaborn as sns
            import numpy as np
            
            code = code.replace('plt.show()', '')
            filepath = self.charts_dir / f"plot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            if 'plt.savefig' not in code:
                code += f'\nplt.savefig("{filepath}", dpi=300, bbox_inches="tight")'
            exec(code, {'df': df, 'plt': plt, 'sns': sns, 'pd': pd, 'np': np, 'datetime': datetime})
            if 'plt.savefig' not in code:
                plt.savefig(filepath, dpi=300, bbox_inches='tight')
            plt.close()
            return str(filepath)
        except Exception as e:
            import matplotlib.pyplot as plt
            plt.close()
            raise Exception(f"Error ejecutando código: {str(e)}")
    
    async def send_plot(self, update: Update, filepath: str):
        """Envía gráfico por Telegram"""
        try:
            with open(filepath, 'rb') as photo:
                await update.message.reply_photo(photo=InputFile(photo), caption="📊 Gráfico generado")
        except Exception as e:
            await update.message.reply_text(f"❌ Error enviando imagen: {str(e)}")
    
    def find_recent_plots(self) -> List[Path]:
        """Busca archivos de gráfico generados recientemente"""
        current_time = datetime.now()
        plot_files = []
        for directory in [self.charts_dir, self.project_root]:
            for file_path in directory.glob("*.png"):
                if (current_time - datetime.fromtimestamp(file_path.stat().st_mtime)).seconds < 30:
                    plot_files.append(file_path)
        return plot_files

# ==============================================================================
# 🏗️ Clase Base para Handlers
# ==============================================================================
class BaseHandler(ABC):
    """Clase base para todos los handlers de Telegram"""
    
    def __init__(self, api_key: str, openai_model: str, project_root: Path):
        self.api_key = api_key
        self.openai_model = openai_model
        self.project_root = project_root
        self.base_llm = ChatOpenAI(model=openai_model, temperature=0, max_retries=2, api_key=api_key)
        
        # Configurar PlotHandler
        self.charts_dir = project_root / "data" / "plots"
        self.plot_handler = PlotHandler(self.charts_dir, project_root)
    
    def create_pandas_agent_for_user(self, user_state: UserState) -> object:
        """Crea un agente de pandas para el usuario si tiene datos"""
        if user_state.current_dataframe is not None and user_state.pandas_agent is None:
            try:
                user_state.pandas_agent = create_pandas_dataframe_agent(
                    self.base_llm, user_state.current_dataframe, verbose=True, allow_dangerous_code=True,
                    prefix=SYSTEM_PROMPT, agent_type="openai-tools",
                    agent_executor_kwargs={"handle_parsing_errors": True}
                )
            except TypeError:
                user_state.pandas_agent = create_pandas_dataframe_agent(
                    self.base_llm, user_state.current_dataframe, verbose=True, allow_dangerous_code=True, 
                    prefix=SYSTEM_PROMPT
                )
        return user_state.pandas_agent
    
    def create_municipios_keyboard(self) -> List[List[InlineKeyboardButton]]:
        """Crea el teclado con los municipios disponibles"""
        keyboard = []
        for i in range(0, len(MUNICIPIOS), 2):
            row = []
            for j in range(2):
                if i + j < len(MUNICIPIOS):
                    municipio = MUNICIPIOS[i + j]
                    row.append(InlineKeyboardButton(
                        municipio.title(), 
                        callback_data=f"municipio_{municipio}"
                    ))
            keyboard.append(row)
        return keyboard
    
    def read_climate_data(self, file_path: str) -> str:
        """Lee los datos climáticos descargados y retorna un resumen"""
        try:
            if not os.path.exists(file_path):
                return "❌ Archivo de datos no encontrado"
            
            df = pd.read_csv(file_path)
            summary = f"📊 Resumen de datos climáticos:\n- Total de registros: {len(df)}\n"
            
            if 'datetime' in df.columns:
                summary += f"- Período: {df['datetime'].min()} a {df['datetime'].max()}\n"
            if 'wind_speed_10m' in df.columns:
                summary += f"- Velocidad del viento: {df['wind_speed_10m'].mean():.2f} km/h (promedio)\n- Máxima velocidad: {df['wind_speed_10m'].max():.2f} km/h\n"
            if 'temperature_2m' in df.columns:
                summary += f"- Temperatura: {df['temperature_2m'].mean():.1f}°C (promedio)\n"
            
            return summary
        except Exception as e:
            return f"❌ Error leyendo datos: {str(e)}"

# ==============================================================================
# 🎯 Command Handlers
# ==============================================================================
class CommandHandler(BaseHandler):
    """Maneja todos los comandos de Telegram"""
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Maneja el comando /start"""
        user = update.effective_user
        welcome_message = (
            f"🤖 ¡Hola {user.first_name}! 😊\n\n"
            f"Soy tu asistente de predicción de viento para La Guajira.\n"
            f"Puedo ayudarte con: {', '.join(TEMAS)}\n\n"
            f"¿De qué municipio deseas saber el clima?\n\n"
            f"Ejemplos: {', '.join(MUNICIPIOS[:5])}"
        )
        
        # Crear teclado con municipios
        keyboard = self.create_municipios_keyboard()
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(welcome_message, reply_markup=reply_markup)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Maneja el comando /help"""
        help_text = (
            "🆘 **Comandos disponibles:**\n\n"
            "• `/start` - Iniciar el bot\n"
            "• `/help` - Mostrar esta ayuda\n"
            "• `/municipios` - Ver lista de municipios\n"
            "• `/cambiar` - Cambiar de municipio\n"
            "• `/estado` - Ver estado actual\n\n"
            "**Municipios disponibles:**\n"
            f"{', '.join(MUNICIPIOS)}\n\n"
            "**Temas:**\n"
            f"{', '.join(TEMAS)}\n\n"
        "📊 **Análisis avanzado de datos:**\n"
        "Una vez seleccionado un municipio, puedes solicitar:\n"
        "• Análisis estadísticos complejos\n"
        "• Cálculos matemáticos avanzados\n"
        "• Gráficos y visualizaciones\n"
        "• Correlaciones y tendencias\n"
        "• Análisis de series temporales\n"
        "• Predicciones y modelos\n\n"
        "**Ejemplos de consultas:**\n"
        "• '¿Cuál es la velocidad promedio del viento en enero?'\n"
        "• 'Calcula la correlación entre temperatura y viento'\n"
        "• 'Dame una gráfica de la velocidad del viento'\n"
        "• 'Encuentra los días con mayor velocidad de viento'\n"
        "• 'Analiza la tendencia de temperatura'\n"
        "• '¿Cuál es el patrón de viento por hora del día?'"
        )
        
        await update.message.reply_text(help_text, parse_mode='Markdown')

    async def municipios_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Maneja el comando /municipios"""
        keyboard = self.create_municipios_keyboard()
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "📍 **Selecciona un municipio:**", 
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    async def cambiar_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Maneja el comando /cambiar"""
        user_id = update.effective_user.id
        user_state = get_user_state(user_id)
        
        # Resetear estado
        user_state.current_municipio = None
        user_state.current_data_summary = None
        user_state.current_file_path = None
        user_state.current_dataframe = None
        user_state.pandas_agent = None
        
        keyboard = self.create_municipios_keyboard()
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🔄 **Cambiando de municipio...**\n\nSelecciona un nuevo municipio:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    async def estado_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Maneja el comando /estado"""
        user_id = update.effective_user.id
        user_state = get_user_state(user_id)
        
        if user_state.current_municipio:
            estado_text = (
                f"📊 **Estado actual:**\n\n"
                f"🏘️ Municipio: {user_state.current_municipio.title()}\n"
                f"📅 Última actividad: {user_state.last_activity.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"📁 Datos: {'✅ Disponibles' if user_state.current_file_path else '❌ No disponibles'}"
            )
        else:
            estado_text = (
                "📊 **Estado actual:**\n\n"
                "🏘️ Municipio: Ninguno seleccionado\n"
                f"📅 Última actividad: {user_state.last_activity.strftime('%Y-%m-%d %H:%M:%S')}\n"
                "📁 Datos: ❌ No disponibles"
            )
        
        await update.message.reply_text(estado_text, parse_mode='Markdown')

# ==============================================================================
# 🔄 Callback Handlers
# ==============================================================================
class CallbackHandler(BaseHandler):
    """Maneja los callbacks de los teclados inline"""
    
    async def municipio_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Maneja la selección de municipio desde el teclado"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        user_state = get_user_state(user_id)
        
        # Extraer municipio del callback_data
        municipio = query.data.replace("municipio_", "")
        
        if municipio not in MUNICIPIOS:
            await query.edit_message_text("❌ Municipio no válido")
            return
        
        # Actualizar estado
        user_state.current_municipio = municipio
        user_state.last_activity = datetime.now()
        
        # Descargar datos
        await query.edit_message_text(f"📊 Descargando datos para {municipio.title()}...")
        
        try:
            # Calcular rango de fechas
            current_datetime = datetime.now()
            end_datetime, start_datetime = current_datetime, current_datetime - timedelta(days=365)
            end_date, start_date = end_datetime.strftime("%Y-%m-%d"), start_datetime.strftime("%Y-%m-%d")
            start_hour, end_hour = start_datetime.hour, end_datetime.hour
            
            # Descargar datos
            result = ClimateDataDownloader(
                start_date=start_date, 
                end_date=end_date, 
                start_hour=start_hour, 
                end_hour=end_hour
            ).download_single_city(municipio)
            
            if result and result.get('success') and result.get('file_path'):
                user_state.current_file_path = result.get('file_path')
                user_state.current_data_summary = self.read_climate_data(user_state.current_file_path)
                
                # Cargar datos en DataFrame para análisis y gráficos
                try:
                    user_state.current_dataframe = pd.read_csv(user_state.current_file_path)
                    # Convertir columna datetime si existe
                    for col in user_state.current_dataframe.columns:
                        if col.lower() in {"datetime", "date", "fecha"}:
                            user_state.current_dataframe[col] = pd.to_datetime(user_state.current_dataframe[col], errors="coerce")
                    # Crear agente de pandas
                    self.create_pandas_agent_for_user(user_state)
                except Exception as e:
                    logger.error(f"Error cargando DataFrame para {municipio}: {e}")
                
                success_message = (
                    f"✅ **{municipio.title()} seleccionado**\n\n"
                    f"📅 Período: {start_date} a {end_date}\n"
                    f"⏰ Rango exacto: {start_datetime.strftime('%Y-%m-%d %H:%M')} a {end_datetime.strftime('%Y-%m-%d %H:%M')}\n\n"
                    f"{user_state.current_data_summary}\n\n"
                    f"🤖 Ahora puedes hacer preguntas sobre el clima de {municipio.title()}\n"
                    f"📊 También puedes solicitar gráficos y análisis de datos"
                )
            else:
                success_message = (
                    f"⚠️ **{municipio.title()} seleccionado**\n\n"
                    f"❌ No se pudieron descargar los datos climáticos.\n"
                    f"Puedes hacer preguntas generales sobre el clima de {municipio.title()}"
                )
            
            await query.edit_message_text(success_message, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error descargando datos para {municipio}: {e}")
            await query.edit_message_text(
                f"❌ Error descargando datos para {municipio.title()}: {str(e)}"
            )

# ==============================================================================
# 💬 Message Handlers
# ==============================================================================
class MessageHandler(BaseHandler):
    """Maneja los mensajes de texto del usuario"""
    
    def __init__(self, api_key: str, openai_model: str, project_root: Path):
        super().__init__(api_key, openai_model, project_root)
        
        # Configurar router y subagentes
        self.router_memory = ConversationBufferMemory(input_key="question", memory_key="history")
        self.router_chain = LLMChain(llm=self.base_llm, prompt=router_prompt_template, memory=self.router_memory)
        
        # Memoria independiente por municipio
        self.municipio_memories = {m: ConversationBufferMemory(input_key="question", memory_key="history") for m in MUNICIPIOS}
        self.subagents = {m: self._build_subagent(m) for m in MUNICIPIOS}
    
    def _build_subagent(self, municipio: str) -> LLMChain:
        """Construye un subagente para un municipio específico"""
        return LLMChain(llm=self.base_llm, prompt=subagent_prompt_template, memory=self.municipio_memories[municipio])
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Maneja los mensajes de texto del usuario"""
        user_id = update.effective_user.id
        user_state = get_user_state(user_id)
        user_q = update.message.text.strip()
        
        if not user_q:
            return
        
        # Actualizar última actividad
        user_state.last_activity = datetime.now()
        
        try:
            # Verificar cambio de municipio
            if user_state.current_municipio and any(
                m.lower() in user_q.lower() for m in MUNICIPIOS 
                if m.lower() != user_state.current_municipio.lower()
            ):
                await update.message.reply_text(
                    "🔄 Detectado cambio de municipio. Redirigiendo al orquestador...",
                    reply_markup=InlineKeyboardMarkup(self.create_municipios_keyboard())
                )
                self._reset_user_state(user_state)
                return
            
            # Si no hay municipio activo, usar el router
            if not user_state.current_municipio:
                await self._handle_router_request(update, user_state, user_q)
            else:
                await self._handle_municipio_request(update, user_state, user_q)
        
        except Exception as e:
            logger.error(f"Error procesando mensaje: {e}")
            await update.message.reply_text(f"❌ Error procesando tu consulta: {str(e)}")
    
    def _reset_user_state(self, user_state: UserState) -> None:
        """Resetea el estado del usuario"""
        user_state.current_municipio = None
        user_state.current_data_summary = None
        user_state.current_file_path = None
        user_state.current_dataframe = None
        user_state.pandas_agent = None
    
    async def _handle_router_request(self, update: Update, user_state: UserState, user_q: str) -> None:
        """Maneja solicitudes cuando no hay municipio activo"""
        route = self.router_chain.run({
            "question": user_q,
            "municipios": ", ".join(MUNICIPIOS),
            "temas": ", ".join(TEMAS)
        }).strip().lower()
        
        if route in MUNICIPIOS:
            user_state.current_municipio = route
            
            # Descargar datos
            await update.message.reply_text(f"📊 Descargando datos para {route.title()}...")
            
            # Calcular rango de fechas
            current_datetime = datetime.now()
            end_datetime, start_datetime = current_datetime, current_datetime - timedelta(days=365)
            end_date, start_date = end_datetime.strftime("%Y-%m-%d"), start_datetime.strftime("%Y-%m-%d")
            start_hour, end_hour = start_datetime.hour, end_datetime.hour
            
            result = ClimateDataDownloader(
                start_date=start_date, 
                end_date=end_date, 
                start_hour=start_hour, 
                end_hour=end_hour
            ).download_single_city(route)
            
            if result and result.get('success') and result.get('file_path'):
                user_state.current_file_path = result.get('file_path')
                user_state.current_data_summary = self.read_climate_data(user_state.current_file_path)
                
                # Cargar datos en DataFrame para análisis y gráficos
                try:
                    user_state.current_dataframe = pd.read_csv(user_state.current_file_path)
                    # Convertir columna datetime si existe
                    for col in user_state.current_dataframe.columns:
                        if col.lower() in {"datetime", "date", "fecha"}:
                            user_state.current_dataframe[col] = pd.to_datetime(user_state.current_dataframe[col], errors="coerce")
                    # Crear agente de pandas
                    self.create_pandas_agent_for_user(user_state)
                except Exception as e:
                    logger.error(f"Error cargando DataFrame para {route}: {e}")
            
            # Continuar con el subagente
            if route in self.subagents:
                enhanced_question = f"{user_q}\n\n[Contexto: Datos climáticos descargados para {route} del {start_date} al {end_date}. Hora actual: {current_datetime.strftime('%Y-%m-%d %H:%M:%S')}]\n\n{user_state.current_data_summary}"
                subagent_response = self.subagents[route].run({"municipio": route, "question": enhanced_question})
                await update.message.reply_text(f"🤖 **{route.title()}:** {subagent_response}", parse_mode='Markdown')
            else:
                await update.message.reply_text(f"❌ Subagente no encontrado para {route}")
        else:
            await update.message.reply_text(f"🤖 Bot: {route}")
    
    async def _handle_municipio_request(self, update: Update, user_state: UserState, user_q: str) -> None:
        """Maneja solicitudes cuando hay un municipio activo"""
        # Si tenemos datos del municipio, usar PandasAgent para análisis avanzado
        if (user_state.current_dataframe is not None and 
            user_state.pandas_agent is not None):
            
            # Verificar si es solicitud de gráfico
            if self.plot_handler.is_plot_request(user_q):
                await self._handle_plot_request(update, user_state, user_q)
            else:
                # Usar PandasAgent para análisis text-to-Python
                await self._handle_pandas_analysis(update, user_state, user_q)
        else:
            # Usar el subagente normal si no hay datos
            if user_state.current_municipio in self.subagents:
                current_datetime = datetime.now()
                end_datetime, start_datetime = current_datetime, current_datetime - timedelta(days=365)
                end_date, start_date = end_datetime.strftime("%Y-%m-%d"), start_datetime.strftime("%Y-%m-%d")
                
                enhanced_question = f"{user_q}\n\n[Contexto: Datos climáticos descargados para {user_state.current_municipio} del {start_date} al {end_date}. Hora actual: {current_datetime.strftime('%Y-%m-%d %H:%M:%S')}]\n\n{user_state.current_data_summary}"
                subagent_response = self.subagents[user_state.current_municipio].run({
                    "municipio": user_state.current_municipio, 
                    "question": enhanced_question
                })
                await update.message.reply_text(f"🤖 **{user_state.current_municipio.title()}:** {subagent_response}", parse_mode='Markdown')
            else:
                await update.message.reply_text(f"❌ Subagente no encontrado para {user_state.current_municipio}")
    
    async def _handle_plot_request(self, update: Update, user_state: UserState, user_q: str) -> None:
        """Maneja solicitudes de gráficos"""
        await update.message.reply_text("📊 Generando gráfico...")
        
        try:
            # Usar el agente de pandas para generar el gráfico
            result = await user_state.pandas_agent.ainvoke({"input": user_q}, handle_parsing_errors=True)
            answer = result["output"] if isinstance(result, dict) and "output" in result else str(result)
            
            # Detectar si se generó un gráfico
            if any(indicator in answer.lower() for indicator in ["plt.savefig", "guardado", "ruta del gráfico"]):
                plot_files = self.plot_handler.find_recent_plots()
                if plot_files:
                    latest_plot = max(plot_files, key=lambda x: x.stat().st_mtime)
                    await self.plot_handler.send_plot(update, str(latest_plot))
                    return
            
            # Si es solicitud de gráfico pero no se detectó, procesar manualmente
            plot_code = self.plot_handler.extract_code(answer)
            if plot_code:
                plot_path = self.plot_handler.execute_plot_code(plot_code, user_state.current_dataframe)
                await self.plot_handler.send_plot(update, plot_path)
                return
            else:
                # Solicitar código de gráfico específico
                plot_prompt = f"{user_q}\n\nGenera código Python con matplotlib/seaborn entre ```python y ```."
                plot_result = await user_state.pandas_agent.ainvoke({"input": plot_prompt}, handle_parsing_errors=True)
                plot_answer = plot_result["output"] if isinstance(plot_result, dict) and "output" in plot_result else str(plot_result)
                plot_code = self.plot_handler.extract_code(plot_answer)
                if plot_code:
                    plot_path = self.plot_handler.execute_plot_code(plot_code, user_state.current_dataframe)
                    await self.plot_handler.send_plot(update, plot_path)
                    return
                else:
                    await update.message.reply_text(f"🤖 **{user_state.current_municipio.title()}:** {plot_answer}", parse_mode='Markdown')
                    return
                    
        except Exception as e:
            logger.error(f"Error generando gráfico: {e}")
            await update.message.reply_text(f"❌ Error generando gráfico: {str(e)}")
    
    async def _handle_pandas_analysis(self, update: Update, user_state: UserState, user_q: str) -> None:
        """Maneja análisis de datos usando PandasAgent (text-to-Python)"""
        await update.message.reply_text("🔍 Analizando datos...")
        
        try:
            # Crear contexto enriquecido para el análisis
            current_datetime = datetime.now()
            end_datetime, start_datetime = current_datetime, current_datetime - timedelta(days=365)
            end_date, start_date = end_datetime.strftime("%Y-%m-%d"), start_datetime.strftime("%Y-%m-%d")
            
            # Contexto enriquecido para el PandasAgent
            enhanced_question = f"""
Consulta: {user_q}

Contexto del municipio: {user_state.current_municipio.title()}
Período de datos: {start_date} a {end_date}
Hora actual: {current_datetime.strftime('%Y-%m-%d %H:%M:%S')}

Resumen de datos disponibles:
{user_state.current_data_summary}

Instrucciones:
- Analiza los datos del DataFrame 'df' para responder la consulta
- Si necesitas hacer cálculos, usa código Python
- Si la consulta requiere visualización, incluye código de gráfico
- Proporciona análisis detallado y conclusiones prácticas
- Responde en español de forma clara y profesional
"""
            
            # Usar el agente de pandas para análisis avanzado
            result = await user_state.pandas_agent.ainvoke({"input": enhanced_question}, handle_parsing_errors=True)
            answer = result["output"] if isinstance(result, dict) and "output" in result else str(result)
            
            # Verificar si se generó un gráfico en el análisis
            if any(indicator in answer.lower() for indicator in ["plt.savefig", "guardado", "ruta del gráfico"]):
                plot_files = self.plot_handler.find_recent_plots()
                if plot_files:
                    latest_plot = max(plot_files, key=lambda x: x.stat().st_mtime)
                    await self.plot_handler.send_plot(update, str(latest_plot))
                    # También enviar el análisis textual
                    await update.message.reply_text(f"🤖 **{user_state.current_municipio.title()}:** {answer}", parse_mode='Markdown')
                    return
            
            # Verificar si hay código de gráfico en la respuesta
            plot_code = self.plot_handler.extract_code(answer)
            if plot_code:
                try:
                    plot_path = self.plot_handler.execute_plot_code(plot_code, user_state.current_dataframe)
                    await self.plot_handler.send_plot(update, plot_path)
                    # Enviar análisis sin el código
                    clean_answer = answer.replace(f"```python\n{plot_code}\n```", "").strip()
                    if clean_answer:
                        await update.message.reply_text(f"🤖 **{user_state.current_municipio.title()}:** {clean_answer}", parse_mode='Markdown')
                    return
                except Exception as plot_error:
                    logger.error(f"Error ejecutando código de gráfico: {plot_error}")
                    # Continuar con respuesta textual si falla el gráfico
            
            # Enviar respuesta textual
            await update.message.reply_text(f"🤖 **{user_state.current_municipio.title()}:** {answer}", parse_mode='Markdown')
                    
        except Exception as e:
            logger.error(f"Error en análisis de pandas: {e}")
            await update.message.reply_text(f"❌ Error analizando datos: {str(e)}")

# ==============================================================================
# 🏭 Factory para crear handlers
# ==============================================================================
class HandlerFactory:
    """Factory para crear instancias de handlers"""
    
    @staticmethod
    def create_handlers(api_key: str, openai_model: str, project_root: Path) -> Dict[str, BaseHandler]:
        """Crea todas las instancias de handlers necesarias"""
        return {
            'command': CommandHandler(api_key, openai_model, project_root),
            'callback': CallbackHandler(api_key, openai_model, project_root),
            'message': MessageHandler(api_key, openai_model, project_root)
        }
