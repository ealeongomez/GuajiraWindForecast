"""
==============================================================================
Project: GuajiraWindForecast
File: testChatbot.py
Description:
    ChatBot to predict wind energy in the Guajira Peninsula.
Author: Eder Arley León Gómez
Created on: 2025-08-06
==============================================================================
"""

# ==============================================================================================
# Libraries
# ==============================================================================================

import os, sys, warnings, requests
from colorama import Fore, init
from pathlib import Path
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain.chains import LLMChain
from langchain_core.prompts import PromptTemplate
from langchain.memory import ConversationBufferMemory

warnings.filterwarnings("ignore")
init(autoreset=True)  # Reinicia colorama después de cada print


# ==============================================================================================
# Environment configuration
# ==============================================================================================

project_root = Path(__file__).resolve().parents[1]
env_path = project_root / ".env"
load_dotenv(dotenv_path=env_path)

api_key = os.getenv("OPENAI_API_KEY")
openAI_model = os.getenv("OPENAI_MODEL")

# ==============================================================================================
# ChatBot
# ==============================================================================================

llm = ChatOpenAI(model=openAI_model, api_key=api_key)

# ==============================================================================================
# ChatBot
# ==============================================================================================

memory = ConversationBufferMemory(input_key="question", memory_key="history")

LLM = ChatOpenAI(
    model=openAI_model,
    temperature=0,
    max_retries=2,
    api_key=api_key
)

# ==============================================================================================
# Prompt
# ==============================================================================================

prompt_template = PromptTemplate(
    template="""
    Eres un asistente experto y confiable en temas relacionados con la Península de La Guajira, Colombia.
    Respondes de manera clara, precisa y basada en información verificada. 
    Tu objetivo es ayudar al usuario a comprender aspectos geográficos, culturales, climáticos, históricos o sociales de esta región.
    
    Pregunta: {question}""",  
    input_variables=["question"]
)

prompt = LLMChain(
    llm=LLM,
    prompt=prompt_template,
    memory=memory
)

# ==============================================================================================
# Main
# ==============================================================================================

def main():
    try:
        print(Fore.CYAN + "🟢 ChatBot iniciado. Escribe 'exit' para salir.\n")
        while True:
            question = input(Fore.GREEN + "Pregunta: " + Fore.RESET)
            if question.lower() == "salir":
                break
            response = prompt.invoke({"question": question})
            print(Fore.YELLOW + "Respuesta: " + Fore.RESET + response["text"])
    except KeyboardInterrupt:   
        print(Fore.RED + "Interrupción del usuario." + Fore.RESET)
    except Exception as e:
        print(Fore.RED + f"Error: {e}" + Fore.RESET)
    finally:
        print(Fore.BLUE + "Fin del programa." + Fore.RESET) 

if __name__ == "__main__":
    main()