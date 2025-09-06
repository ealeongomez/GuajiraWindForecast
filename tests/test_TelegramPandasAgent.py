
# Bot de Telegram con análisis de datos y gráficos
import os, sys, re, warnings
from pathlib import Path
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from dotenv import load_dotenv
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
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
CSV_PATH = os.getenv("CSV_PATH", "data/raw/wind_data_riohacha_2024-08-30_2025-08-30.csv")

CHARTS_DIR = PROJECT_ROOT / "data" / "plots"
CHARTS_DIR.mkdir(parents=True, exist_ok=True)

# Cargar datos y configurar matplotlib
sys.path.append(str(PROJECT_ROOT / "src"))
from prompts.pandas_agent_prompt import SYSTEM_PROMPT

import matplotlib
matplotlib.use('Agg')
plt.ioff()

# ==============================================================================
# 🔗 Load data
# ==============================================================================

df = pd.read_csv(CSV_PATH)
for col in df.columns:
    if col.lower() in {"datetime", "date", "fecha"}:
        df[col] = pd.to_datetime(df[col], errors="coerce")

# ==============================================================================
# 🔗 Agent
# ==============================================================================

llm = ChatOpenAI(model=OPENAI_MODEL, temperature=0, max_retries=2, api_key=OPENAI_API_KEY)
try:
    agent = create_pandas_dataframe_agent(llm, df, verbose=True, allow_dangerous_code=True,
        prefix=SYSTEM_PROMPT, agent_type="openai-tools", agent_executor_kwargs={"handle_parsing_errors": True})
except TypeError:
    agent = create_pandas_dataframe_agent(llm, df, verbose=True, allow_dangerous_code=True, prefix=SYSTEM_PROMPT)

# ==============================================================================
# 🔗 Utilities
# ==============================================================================

CHAT_STATE = {}
GREETINGS = {"hola", "hello", "hi", "hey", "buenas", "buenos dias", "buenos días", "buenas tardes", "buenas noches"}

# ==============================================================================
# 🔗 Utilities
# ==============================================================================

def get_state(chat_id: int):
    return CHAT_STATE.setdefault(chat_id, {"welcomed": False})

def normalize_text(text: str) -> str:
    return " ".join(text.lower().strip().translate(str.maketrans("", "", "¡!?,.;:()[]{}")).split())

# Funciones para gráficos
def is_plot_request(text: str) -> bool:
    return any(kw in text.lower() for kw in ["gráfica", "grafica", "gráfico", "grafico", "plot", "chart", 
        "diagrama", "histograma", "boxplot", "scatter", "línea", "linea", "barras", "pie", "visualizar", "mostrar", "ver", "dibujar"])

def extract_code(response: str) -> str:
    for pattern in [r'```python\s*(.*?)\s*```', r'```\s*(.*?)\s*```']:
        match = re.search(pattern, response, re.DOTALL)
        if match:
            code = match.group(1).strip()
            if any(lib in code for lib in ['plt.', 'sns.', 'matplotlib', 'seaborn']):
                return code
    return ""

def execute_plot_code(code: str, df: pd.DataFrame) -> str:
    try:
        code = code.replace('plt.show()', '')
        filepath = CHARTS_DIR / f"plot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
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

async def send_plot(update: Update, filepath: str):
    try:
        with open(filepath, 'rb') as photo:
            await update.message.reply_photo(photo=InputFile(photo), caption="📊 Gráfico generado")
    except Exception as e:
        await update.message.reply_text(f"❌ Error enviando imagen: {str(e)}")

# Handlers de Telegram
async def start(update: Update, _: ContextTypes.DEFAULT_TYPE):
    state = get_state(update.effective_chat.id)
    if not state["welcomed"]:
        state["welcomed"] = True
        await update.message.reply_text("¡Hola! Soy tu asistente de análisis de datos meteorológicos.\n\n📊 Puedo ayudarte con análisis y gráficos.\nEjemplos: 'Dame una gráfica de la velocidad del viento'")

async def on_message(update: Update, _: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if not text:
        return

    # Manejar saludos
    if normalize_text(text) in GREETINGS:
        state = get_state(update.effective_chat.id)
        if not state["welcomed"]:
            state["welcomed"] = True
            await update.message.reply_text("¡Hola! Soy tu asistente de análisis de datos meteorológicos.\n\n📊 Puedo ayudarte con análisis y gráficos.\n¿Qué te gustaría que haga?")
        else:
            await update.message.reply_text("¿Qué análisis o gráfico te gustaría que haga?")
        return

    # Procesar consulta con el agente
    try:
        result = await agent.ainvoke({"input": text}, handle_parsing_errors=True)
        answer = result["output"] if isinstance(result, dict) and "output" in result else str(result)
        
        # Detectar si se generó un gráfico
        if any(indicator in answer.lower() for indicator in ["plt.savefig", "guardado", "ruta del gráfico"]):
            current_time = datetime.now()
            plot_files = [f for d in [CHARTS_DIR, PROJECT_ROOT] for f in d.glob("*.png") 
                         if (current_time - datetime.fromtimestamp(f.stat().st_mtime)).seconds < 30]
            if plot_files:
                latest_plot = max(plot_files, key=lambda x: x.stat().st_mtime)
                try:
                    await send_plot(update, str(latest_plot))
                    return  # Solo enviar la imagen, no el texto
                except Exception as e:
                    await update.message.reply_text(f"❌ Error enviando gráfico: {str(e)}")
                    return
        
        # Si es solicitud de gráfico pero no se detectó, procesar manualmente
        elif is_plot_request(text):
            plot_code = extract_code(answer)
            if plot_code:
                try:
                    plot_path = execute_plot_code(plot_code, df)
                    await send_plot(update, plot_path)
                    return  # Solo enviar la imagen, no el texto
                except Exception as e:
                    await update.message.reply_text(f"❌ Error generando gráfico: {str(e)}")
                    return
            else:
                plot_prompt = f"{text}\n\nGenera código Python con matplotlib/seaborn entre ```python y ```."
                try:
                    plot_result = await agent.ainvoke({"input": plot_prompt}, handle_parsing_errors=True)
                    plot_answer = plot_result["output"] if isinstance(plot_result, dict) and "output" in plot_result else str(plot_result)
                    plot_code = extract_code(plot_answer)
                    if plot_code:
                        plot_path = execute_plot_code(plot_code, df)
                        await send_plot(update, plot_path)
                        return  # Solo enviar la imagen, no el texto
                    else:
                        answer = plot_answer
                except Exception as e:
                    answer = f"❌ Error: {str(e)}"
        
    except Exception as e:
        answer = f"❌ Error: {e}"

    await update.message.reply_text(answer)

# ==============================================================================
# 🔗 Main
# ==============================================================================
def main():
    print("🚀 Iniciando bot de Telegram...")
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    print("✅ Bot iniciado. Presiona Ctrl+C para detener.")
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
