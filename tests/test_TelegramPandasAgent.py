# file: bots/telegram_pandas_agent_simple.py
import os, sys, warnings
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

from langchain_openai import ChatOpenAI
from langchain_experimental.agents.agent_toolkits.pandas.base import create_pandas_dataframe_agent

warnings.filterwarnings("ignore")

# ==============================================================================
# ⚙️ Env
# ==============================================================================
PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
CSV_PATH = os.getenv("CSV_PATH", "data/raw/wind_data_riohacha_2024-08-30_2025-08-30.csv")

if not BOT_TOKEN or not OPENAI_API_KEY:
    raise RuntimeError("Faltan TELEGRAM_BOT_TOKEN u OPENAI_API_KEY en .env")

# Prompt externo
sys.path.append(str(PROJECT_ROOT / "src"))
from prompts.pandas_agent_prompt import SYSTEM_PROMPT

# ==============================================================================
# 🔗 DataFrame
# ==============================================================================
df = pd.read_csv(CSV_PATH)
for c in df.columns:
    if c.lower() in {"datetime", "date", "fecha"}:
        df[c] = pd.to_datetime(df[c], errors="coerce")

# ==============================================================================
# 📝 Prompt
# ==============================================================================
SYSTEM_PREFIX = SYSTEM_PROMPT  # 👈 como pediste

# ==============================================================================
# 🤖 LLM + Agent
# ==============================================================================
llm = ChatOpenAI(model=OPENAI_MODEL, temperature=0, max_retries=2, api_key=OPENAI_API_KEY)

try:
    agent = create_pandas_dataframe_agent(
        llm,
        df,
        verbose=True,
        allow_dangerous_code=True,
        prefix=SYSTEM_PREFIX,
        agent_type="openai-tools",
        agent_executor_kwargs={"handle_parsing_errors": True},
    )
except TypeError:
    # Compatibilidad con versiones más antiguas
    agent = create_pandas_dataframe_agent(
        llm,
        df,
        verbose=True,
        allow_dangerous_code=True,
        prefix=SYSTEM_PREFIX,
    )

# ==============================================================================
# 🧠 Estado mínimo por chat
# ==============================================================================
CHAT_STATE = {}  # chat_id -> {"welcomed": bool}

def get_state(chat_id: int):
    s = CHAT_STATE.setdefault(chat_id, {"welcomed": False})
    return s

_GREETINGS = {
    "hola", "hello", "hi", "hey", "buenas", "buenos dias", "buenos días",
    "buenas tardes", "buenas noches"
}

def _normalize(text: str) -> str:
    t = text.lower().strip()
    # quita signos comunes
    for ch in "¡!?,.;:()[]{}":
        t = t.replace(ch, " ")
    return " ".join(t.split())

# ==============================================================================
# 🚀 Handlers
# ==============================================================================
async def start(update: Update, _: ContextTypes.DEFAULT_TYPE):
    s = get_state(update.effective_chat.id)
    if not s["welcomed"]:
        s["welcomed"] = True
        await update.message.reply_text(
            "¡Hola! Soy tu asistente sobre el CSV cargado.\n"
            "Escribe tu pregunta (p. ej. 'Dame una gráfica de la velocidad del viento')."
        )
    # Si ya estaba bienvenido, no mandamos un segundo saludo.

async def on_message(update: Update, _: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    s = get_state(chat_id)
    text = (update.message.text or "").strip()
    if not text:
        return

    # Controla saludos para evitar duplicados
    text_norm = _normalize(text)
    if text_norm in _GREETINGS:
        if not s["welcomed"]:
            s["welcomed"] = True
            return await update.message.reply_text(
                "¡Hola! Soy tu asistente sobre el CSV cargado.\n"
                "Cuéntame qué cálculo o análisis quieres que haga con el CSV."
            )
        else:
            # Ya saludamos antes → respuesta breve sin “segundo saludo”
            return await update.message.reply_text(
                "¿Qué cálculo o análisis quieres que haga con el CSV?"
            )

    # Consulta normal → agente de Pandas
    try:
        result = await agent.ainvoke({"input": text}, handle_parsing_errors=True)
        answer = result["output"] if isinstance(result, dict) and "output" in result else str(result)
    except Exception as e:
        answer = f"❌ Ocurrió un error: {e}"

    await update.message.reply_text(answer)

# ==============================================================================
# 🧭 Main
# ==============================================================================
def main():

    print(f"Initializing Telegram bot...")
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    # Asegura que /start no llegue al handler de texto:
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
