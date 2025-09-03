import os, sys
import pandas as pd
import warnings
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from colorama import Fore, init

from langchain_openai import ChatOpenAI
from langchain_experimental.agents.agent_toolkits.pandas.base import create_pandas_dataframe_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# ==============================================================================
# ⚙️ Environment Configuration
# ==============================================================================
warnings.filterwarnings("ignore")
init(autoreset=True)

project_root = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=project_root / ".env")

api_key = os.getenv("OPENAI_API_KEY")
openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from prompts.pandas_agent_prompt import SYSTEM_PROMPT

# ==============================================================================

# 🔗 Dataframe
# ==============================================================================
file_path = "data/raw/wind_data_riohacha_2024-08-30_2025-08-30.csv"
df = pd.read_csv(file_path)

# (opcional) parseo de fechas si deseas trabajar series temporales
for c in df.columns:
    if c.lower() in {"datetime", "date", "fecha"}:
        df[c] = pd.to_datetime(df[c], errors="coerce")

print(df.head())

# ==============================================================================
# 📝 Prompt personalizado
# ==============================================================================

SYSTEM_PREFIX = SYSTEM_PROMPT

# ==============================================================================
# 🔗 LangChain Components
# ==============================================================================
llm = ChatOpenAI(model=openai_model, temperature=0, max_retries=2, api_key=api_key)

agent = create_pandas_dataframe_agent(llm, df, verbose=True, allow_dangerous_code=True, prefix=SYSTEM_PREFIX)

# ==============================================================================
# 🚀 Main Execution
# ==============================================================================
question = "Dame una grafica de la velocidad del viento"

response = agent.invoke({"input": question})["output"]
print(Fore.YELLOW + "🤖 Bot:", response)



