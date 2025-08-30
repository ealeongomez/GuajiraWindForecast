# ==============================================================================
# Project: GuajiraClimateAgents
# File: multiagent_guajira_organized.py
# Description:
#   Multiagente simple para consultas climáticas en municipios de La Guajira.
#   Versión reorganizada que importa prompts desde src/prompts/
# Author: Eder Arley León Gómez (con ayuda de ChatGPT)
# Created on: 2025-08-13
# ==============================================================================

# ==============================================================================
# 📚 Libraries
# ==============================================================================
import os, re, unicodedata, warnings, sys, time
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
from colorama import Fore, init
import pandas as pd

from langchain_openai import ChatOpenAI
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory

# Agregar el directorio src al path para importar los prompts
sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

# Importar prompts y constantes desde el módulo organizado
from prompts import (
    router_prompt_template,
    subagent_prompt_template,
    MUNICIPIOS,
    TEMAS,
    FAREWELL_PATTERNS,
    CLIMATE_KEYWORDS
)

from api.dataDownload import ClimateDataDownloader

# ==============================================================================
# ⚙️ Environment Configuration
# ==============================================================================
warnings.filterwarnings("ignore")
init(autoreset=True)

project_root = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=project_root / ".env")

api_key = os.getenv("OPENAI_API_KEY")
openai_model = os.getenv("OPENAI_MODEL")

# ==============================================================================
# 🔎 Utilidades
# ==============================================================================
CLIMATE_REGEX = re.compile("|".join(CLIMATE_KEYWORDS), re.IGNORECASE)

def read_climate_data(file_path: str) -> str:
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
# 🤖 LLM base y memorias
# ==============================================================================
base_llm = ChatOpenAI(model=openai_model, temperature=0, max_retries=2, api_key=api_key)
router_memory = ConversationBufferMemory(input_key="question", memory_key="history")

# ==============================================================================
# 🧭 Orquestador (Router) - Usando prompt importado
# ==============================================================================
router_chain = LLMChain(llm=base_llm, prompt=router_prompt_template, memory=router_memory)

# ==============================================================================
# 🧩 Subagentes municipales - Usando prompt importado
# ==============================================================================
# Memoria independiente por municipio para permitir follow-ups locales
municipio_memories = {m: ConversationBufferMemory(input_key="question", memory_key="history") for m in MUNICIPIOS}

def build_subagent(municipio: str) -> LLMChain:
    """Construye un subagente para un municipio específico"""
    return LLMChain(llm=base_llm, prompt=subagent_prompt_template, memory=municipio_memories[municipio])

# Mantener subagentes en caché
SUBAGENTS = {m: build_subagent(m) for m in MUNICIPIOS}

# ==============================================================================
# 🚦 Lógica principal (CLI)
# ==============================================================================

ejemplos = ", ".join(MUNICIPIOS[:5])
temas_txt = ", ".join(TEMAS)
municipios_lista = ", ".join(MUNICIPIOS)
temas_lista = ", ".join(TEMAS)

def main():
    
    print(Fore.YELLOW + "\n🤖 Bot: ¡Hola! 😊 Soy tu asistente de predicción de viento para La Guajira. "  
          f"Puedo ayudarte con: {temas_txt}. ¿De qué municipio deseas saber el clima? (Ej.: {ejemplos})")
    
    # Variables para el chat continuo
    current_municipio = current_data_summary = current_file_path = None
    
    # Principal loop
    try:
        while True:
        
            # Get current date and time
            current_datetime = datetime.now()
            date_time = current_datetime.strftime("%Y-%m-%d %H:%M:%S")
            
            # Calculate exact time range: from 1 year ago to current hour
            end_datetime, start_datetime = current_datetime, current_datetime - timedelta(days=365)
            end_date, start_date = end_datetime.strftime("%Y-%m-%d"), start_datetime.strftime("%Y-%m-%d")
            start_hour, end_hour = start_datetime.hour, end_datetime.hour
        
            # User question
            if current_municipio:
                user_q = input(Fore.GREEN + f"👤 User ({current_municipio}): ").strip()
            else:
                user_q = input(Fore.GREEN + "👤 User: ").strip()

            try:
                # Verificar cambio de municipio
                if current_municipio and any(m.lower() in user_q.lower() for m in MUNICIPIOS if m.lower() != current_municipio.lower()):
                    print(Fore.YELLOW + "🔄 Detectado cambio de municipio. Redirigiendo al orquestador...")
                    current_municipio = current_data_summary = current_file_path = None
                
                # Comando especial para cambiar de municipio
                if user_q.lower().startswith(("/cambiar", "/change")):
                    print(Fore.YELLOW + "🔄 Cambiando de municipio...")
                    current_municipio = current_data_summary = current_file_path = None
                    continue
                
                # Si no hay municipio activo, usar el router
                if not current_municipio:
                    route = router_chain.run({
                        "question": user_q,
                        "municipios": municipios_lista,
                        "temas": temas_lista
                    }).strip().lower()

                    if route in MUNICIPIOS:
                        current_municipio = route
                        print(Fore.CYAN + f"-------------------------------- {route}" + Fore.RESET)
                        print(f"📊 Downloading data for {route}...")
                        print(f"📅 Period: {start_date} to {end_date}")
                        print(f"⏰ Exact range: {start_datetime.strftime('%Y-%m-%d %H:%M')} to {end_datetime.strftime('%Y-%m-%d %H:%M')}")
                        
                        result = ClimateDataDownloader(start_date=start_date, end_date=end_date, start_hour=start_hour, end_hour=end_hour).download_single_city(route)
                        
                        # Guardar datos para el chat continuo
                        if result and result.get('success') and result.get('file_path'):
                            current_file_path = result.get('file_path')
                            print(Fore.BLUE + "📖 Analizando datos descargados...")
                            current_data_summary = read_climate_data(current_file_path)
                            print(current_data_summary)
                        
                        # Continuar con el subagente
                        if route in SUBAGENTS:
                            print(Fore.GREEN + f"🤖 Activando subagente para {route}...")
                            enhanced_question = f"{user_q}\n\n[Contexto: Datos climáticos descargados para {route} del {start_date} al {end_date}. Hora actual: {date_time}]\n\n{current_data_summary}"
                            subagent_response = SUBAGENTS[route].run({"municipio": route, "question": enhanced_question})
                            print(Fore.CYAN + f"🤖 {route}: " + Fore.RESET + subagent_response)
                        else:
                            print(Fore.RED + f"❌ Subagente no encontrado para {route}")
                    else:
                        print(Fore.YELLOW + f"🤖 Bot: {route}")
                
                # Si hay municipio activo, usar directamente el subagente
                else:
                    if current_municipio in SUBAGENTS:
                        enhanced_question = f"{user_q}\n\n[Contexto: Datos climáticos descargados para {current_municipio} del {start_date} al {end_date}. Hora actual: {date_time}]\n\n{current_data_summary}"
                        subagent_response = SUBAGENTS[current_municipio].run({"municipio": current_municipio, "question": enhanced_question})
                        print(Fore.CYAN + f"🤖 {current_municipio}: " + Fore.RESET + subagent_response)
                    else:
                        print(Fore.RED + f"❌ Subagente no encontrado para {current_municipio}")

            except Exception as e:
                print(Fore.RED + f"❌ Error del orquestador: {e}" + Fore.RESET)
                continue
            
            if not user_q:
                continue

    except KeyboardInterrupt:
        print(Fore.RED + "\n🔴 Interrumpido por el usuario." + Fore.RESET)
    except Exception as e:
        print(Fore.RED + f"❌ Error inesperado: {e}" + Fore.RESET)
    finally:
        print(Fore.BLUE + "🔵 Sesión finalizada." + Fore.RESET)
    



# ==============================================================================
# ▶️ Entrypoint
# ==============================================================================
if __name__ == "__main__":
    main()
