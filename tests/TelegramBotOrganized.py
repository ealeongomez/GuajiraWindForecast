# Bot de Telegram con análisis de datos y gráficos - Versión Organizada
import os, sys, re, warnings
from pathlib import Path
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from dotenv import load_dotenv
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler as TelegramMessageHandler, ContextTypes, filters
from langchain_openai import ChatOpenAI
from langchain_experimental.agents.agent_toolkits.pandas.base import create_pandas_dataframe_agent

warnings.filterwarnings("ignore")

# ==============================================================================
# 🔗 Configuración
# ==============================================================================
PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
CSV_PATH = os.getenv("CSV_PATH", "data/raw/open_meteo_riohacha.csv")

if not BOT_TOKEN or not OPENAI_API_KEY:
    raise RuntimeError("Faltan TELEGRAM_BOT_TOKEN u OPENAI_API_KEY en .env")

# ==============================================================================
# 🔗 Clase para manejo de gráficos
# ==============================================================================
class PlotHandler:
    def __init__(self, charts_dir: Path, project_root: Path):
        self.charts_dir = charts_dir
        self.project_root = project_root
        self.charts_dir.mkdir(parents=True, exist_ok=True)
        
        # Configurar matplotlib sin GUI
        import matplotlib
        matplotlib.use('Agg')
        plt.ioff()
    
    def is_plot_request(self, text: str) -> bool:
        """Detecta si la consulta solicita un gráfico"""
        plot_keywords = ["gráfica", "grafica", "gráfico", "grafico", "plot", "chart", 
            "diagrama", "histograma", "boxplot", "scatter", "línea", "linea", "barras", 
            "pie", "visualizar", "mostrar", "ver", "dibujar"]
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
            code = code.replace('plt.show()', '')
            filepath = self.charts_dir / f"plot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            if 'plt.savefig' not in code:
                code += f'\nplt.savefig("{filepath}", dpi=300, bbox_inches="tight")'
            exec(code, {'df': df, 'plt': plt, 'sns': sns, 'pd': pd, 'np': __import__('numpy'), 'datetime': datetime})
            if 'plt.savefig' not in code:
                plt.savefig(filepath, dpi=300, bbox_inches='tight')
            plt.close()
            return str(filepath)
        except Exception as e:
            plt.close()
            raise Exception(f"Error ejecutando código: {str(e)}")
    
    async def send_plot(self, update: Update, filepath: str):
        """Envía gráfico por Telegram"""
        try:
            with open(filepath, 'rb') as photo:
                await update.message.reply_photo(photo=InputFile(photo), caption="📊 Gráfico generado")
        except Exception as e:
            await update.message.reply_text(f"❌ Error enviando imagen: {str(e)}")
    
    def find_recent_plots(self) -> list:
        """Busca archivos de gráfico generados recientemente"""
        current_time = datetime.now()
        plot_files = []
        for directory in [self.charts_dir, self.project_root]:
            for file_path in directory.glob("*.png"):
                if (current_time - datetime.fromtimestamp(file_path.stat().st_mtime)).seconds < 30:
                    plot_files.append(file_path)
        return plot_files

# ==============================================================================
# 🔗 Clase para manejo de mensajes
# ==============================================================================
class MessageHandler:
    def __init__(self, agent, plot_handler: PlotHandler, df: pd.DataFrame):
        self.agent = agent
        self.plot_handler = plot_handler
        self.df = df
        self.chat_state = {}
        self.greetings = {"hola", "hello", "hi", "hey", "buenas", "buenos dias", 
                         "buenos días", "buenas tardes", "buenas noches"}
    
    def get_state(self, chat_id: int):
        """Obtiene el estado del chat"""
        return self.chat_state.setdefault(chat_id, {"welcomed": False})
    
    def normalize_text(self, text: str) -> str:
        """Normaliza texto para comparación"""
        return " ".join(text.lower().strip().translate(str.maketrans("", "", "¡!?,.;:()[]{}")).split())
    
    async def handle_start(self, update: Update, _: ContextTypes.DEFAULT_TYPE):
        """Maneja el comando /start"""
        state = self.get_state(update.effective_chat.id)
        if not state["welcomed"]:
            state["welcomed"] = True
            await update.message.reply_text(
                "¡Hola! Soy tu asistente de análisis de datos meteorológicos.\n\n"
                "📊 Puedo ayudarte con análisis y gráficos.\n"
                "Ejemplos: 'Dame una gráfica de la velocidad del viento'"
            )
    
    async def handle_message(self, update: Update, _: ContextTypes.DEFAULT_TYPE):
        """Maneja mensajes de texto"""
        text = (update.message.text or "").strip()
        if not text:
            return

        # Manejar saludos
        if self.normalize_text(text) in self.greetings:
            state = self.get_state(update.effective_chat.id)
            if not state["welcomed"]:
                state["welcomed"] = True
                await update.message.reply_text(
                    "¡Hola! Soy tu asistente de análisis de datos meteorológicos.\n\n"
                    "📊 Puedo ayudarte con análisis y gráficos.\n"
                    "¿Qué te gustaría que haga?"
                )
            else:
                await update.message.reply_text("¿Qué análisis o gráfico te gustaría que haga?")
            return

        # Procesar consulta con el agente
        try:
            result = await self.agent.ainvoke({"input": text}, handle_parsing_errors=True)
            answer = result["output"] if isinstance(result, dict) and "output" in result else str(result)
            
            # Detectar si se generó un gráfico
            if any(indicator in answer.lower() for indicator in ["plt.savefig", "guardado", "ruta del gráfico"]):
                plot_files = self.plot_handler.find_recent_plots()
                if plot_files:
                    latest_plot = max(plot_files, key=lambda x: x.stat().st_mtime)
                    try:
                        await self.plot_handler.send_plot(update, str(latest_plot))
                        return  # Solo enviar la imagen, no el texto
                    except Exception as e:
                        await update.message.reply_text(f"❌ Error enviando gráfico: {str(e)}")
                        return
            
            # Si es solicitud de gráfico pero no se detectó, procesar manualmente
            elif self.plot_handler.is_plot_request(text):
                plot_code = self.plot_handler.extract_code(answer)
                if plot_code:
                    try:
                        plot_path = self.plot_handler.execute_plot_code(plot_code, self.df)
                        await self.plot_handler.send_plot(update, plot_path)
                        return  # Solo enviar la imagen, no el texto
                    except Exception as e:
                        await update.message.reply_text(f"❌ Error generando gráfico: {str(e)}")
                        return
                else:
                    plot_prompt = f"{text}\n\nGenera código Python con matplotlib/seaborn entre ```python y ```."
                    try:
                        plot_result = await self.agent.ainvoke({"input": plot_prompt}, handle_parsing_errors=True)
                        plot_answer = plot_result["output"] if isinstance(plot_result, dict) and "output" in plot_result else str(plot_result)
                        plot_code = self.plot_handler.extract_code(plot_answer)
                        if plot_code:
                            plot_path = self.plot_handler.execute_plot_code(plot_code, self.df)
                            await self.plot_handler.send_plot(update, plot_path)
                            return  # Solo enviar la imagen, no el texto
                        else:
                            answer = plot_answer
                    except Exception as e:
                        answer = f"❌ Error: {str(e)}"
            
        except Exception as e:
            answer = f"❌ Error: {e}"

        await update.message.reply_text(answer)

# ==============================================================================
# 🔗 Clase principal del bot
# ==============================================================================
class TelegramBot:
    def __init__(self):
        self.setup_environment()
        self.setup_data()
        self.setup_agent()
        self.setup_handlers()
    
    def setup_environment(self):
        """Configura el entorno y variables"""
        self.charts_dir = PROJECT_ROOT / "data" / "plots"
        self.plot_handler = PlotHandler(self.charts_dir, PROJECT_ROOT)
    
    def setup_data(self):
        """Carga y prepara los datos"""
        self.df = pd.read_csv(CSV_PATH)
        for col in self.df.columns:
            if col.lower() in {"datetime", "date", "fecha"}:
                self.df[col] = pd.to_datetime(self.df[col], errors="coerce")
    
    def setup_agent(self):
        """Configura el agente de IA"""
        sys.path.append(str(PROJECT_ROOT / "src"))
        from prompts.pandas_agent_prompt import SYSTEM_PROMPT
        
        llm = ChatOpenAI(model=OPENAI_MODEL, temperature=0, max_retries=2, api_key=OPENAI_API_KEY)
        try:
            self.agent = create_pandas_dataframe_agent(
                llm, self.df, verbose=True, allow_dangerous_code=True,
                prefix=SYSTEM_PROMPT, agent_type="openai-tools",
                agent_executor_kwargs={"handle_parsing_errors": True}
            )
        except TypeError:
            self.agent = create_pandas_dataframe_agent(
                llm, self.df, verbose=True, allow_dangerous_code=True, prefix=SYSTEM_PROMPT
            )
    
    def setup_handlers(self):
        """Configura los manejadores de mensajes"""
        self.message_handler = MessageHandler(self.agent, self.plot_handler, self.df)
    
    def run(self):
        """Ejecuta el bot"""
        print("🚀 Iniciando bot de Telegram...")
        app = ApplicationBuilder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", self.message_handler.handle_start))
        app.add_handler(TelegramMessageHandler(filters.TEXT & ~filters.COMMAND, self.message_handler.handle_message))
        print("✅ Bot iniciado. Presiona Ctrl+C para detener.")
        app.run_polling(close_loop=False)

# ==============================================================================
# 🔗 Funciones de utilidad para ejecución individual
# ==============================================================================
def create_bot_instance():
    """Crea una instancia del bot para uso programático"""
    return TelegramBot()

def run_bot():
    """Ejecuta el bot"""
    bot = TelegramBot()
    bot.run()

def test_plot_handler():
    """Prueba la funcionalidad del PlotHandler"""
    charts_dir = PROJECT_ROOT / "data" / "plots"
    plot_handler = PlotHandler(charts_dir, PROJECT_ROOT)
    
    # Cargar datos de prueba
    df = pd.read_csv(CSV_PATH)
    for col in df.columns:
        if col.lower() in {"datetime", "date", "fecha"}:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    
    # Probar detección de gráficos
    test_texts = [
        "Dame una gráfica de velocidad",
        "¿Cuál es la velocidad promedio?",
        "Muestra un histograma"
    ]
    
    for text in test_texts:
        is_plot = plot_handler.is_plot_request(text)
        print(f"'{text}' -> Es gráfico: {is_plot}")
    
    return plot_handler

def test_message_handler():
    """Prueba la funcionalidad del MessageHandler"""
    # Crear instancias necesarias
    charts_dir = PROJECT_ROOT / "data" / "plots"
    plot_handler = PlotHandler(charts_dir, PROJECT_ROOT)
    
    # Cargar datos
    df = pd.read_csv(CSV_PATH)
    for col in df.columns:
        if col.lower() in {"datetime", "date", "fecha"}:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    
    # Crear agente
    sys.path.append(str(PROJECT_ROOT / "src"))
    from prompts.pandas_agent_prompt import SYSTEM_PROMPT
    
    llm = ChatOpenAI(model=OPENAI_MODEL, temperature=0, max_retries=2, api_key=OPENAI_API_KEY)
    try:
        agent = create_pandas_dataframe_agent(
            llm, df, verbose=True, allow_dangerous_code=True,
            prefix=SYSTEM_PROMPT, agent_type="openai-tools",
            agent_executor_kwargs={"handle_parsing_errors": True}
        )
    except TypeError:
        agent = create_pandas_dataframe_agent(
            llm, df, verbose=True, allow_dangerous_code=True, prefix=SYSTEM_PROMPT
        )
    
    # Crear message handler
    message_handler = MessageHandler(agent, plot_handler, df)
    
    # Probar normalización de texto
    test_texts = ["¡Hola!", "¿Cómo estás?", "Buenos días!"]
    for text in test_texts:
        normalized = message_handler.normalize_text(text)
        print(f"'{text}' -> '{normalized}'")
    
    return message_handler

# ==============================================================================
# 🔗 Función principal
# ==============================================================================
def main():
    """Función principal para ejecutar el bot"""
    bot = TelegramBot()
    bot.run()

if __name__ == "__main__":
    main()
