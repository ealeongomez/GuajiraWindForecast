# ==============================================================================
# Project: GuajiraClimateAgents
# File: telegram_multiagent_bot_refactored.py
# Description:
#   Bot de Telegram con multiagente para consultas climáticas - Versión refactorizada con clases
#   Versión organizada que usa handlers en clases para mejor estructura y mantenibilidad
# Author: Eder Arley León Gómez 
# Created on: 2025-01-09
# ==============================================================================

# ==============================================================================
# 📚 Libraries
# ==============================================================================
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler,
    filters
)

# Importar handlers organizados en clases
from telegram_handlers import HandlerFactory

# ==============================================================================
# ⚙️ Environment Configuration
# ==============================================================================
project_root = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=project_root / ".env")

# Configuración de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Variables de entorno
api_key = os.getenv("OPENAI_API_KEY")
openai_model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")

if not telegram_token:
    raise ValueError("TELEGRAM_BOT_TOKEN no encontrado en las variables de entorno")

# ==============================================================================
# 🤖 Bot Principal con Handlers Organizados
# ==============================================================================
class TelegramMultiAgentBot:
    """Bot principal de Telegram con arquitectura de handlers organizados"""
    
    def __init__(self, token: str, api_key: str, openai_model: str, project_root: Path):
        self.token = token
        self.api_key = api_key
        self.openai_model = openai_model
        self.project_root = project_root
        
        # Crear aplicación de Telegram
        self.application = Application.builder().token(token).build()
        
        # Crear handlers usando factory
        self.handlers = HandlerFactory.create_handlers(api_key, openai_model, project_root)
        
        # Configurar handlers
        self._setup_handlers()
    
    def _setup_handlers(self) -> None:
        """Configura todos los handlers del bot"""
        command_handler = self.handlers['command']
        callback_handler = self.handlers['callback']
        message_handler = self.handlers['message']
        
        # Command handlers
        self.application.add_handler(CommandHandler("start", command_handler.start_command))
        self.application.add_handler(CommandHandler("help", command_handler.help_command))
        self.application.add_handler(CommandHandler("municipios", command_handler.municipios_command))
        self.application.add_handler(CommandHandler("cambiar", command_handler.cambiar_command))
        self.application.add_handler(CommandHandler("estado", command_handler.estado_command))
        
        # Callback handlers
        self.application.add_handler(CallbackQueryHandler(callback_handler.municipio_callback, pattern="^municipio_"))
        
        # Message handlers
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler.handle_message))
    
    def run(self) -> None:
        """Ejecuta el bot"""
        logger.info("🤖 Iniciando bot de Telegram con arquitectura de clases...")
        self.application.run_polling(allowed_updates=None)

# ==============================================================================
# 🚀 Función principal
# ==============================================================================
def main() -> None:
    """Función principal para ejecutar el bot"""
    if not telegram_token:
        logger.error("TELEGRAM_BOT_TOKEN no configurado")
        return
    
    # Crear y ejecutar bot
    bot = TelegramMultiAgentBot(
        token=telegram_token,
        api_key=api_key,
        openai_model=openai_model,
        project_root=project_root
    )
    
    bot.run()

# ==============================================================================
# ▶️ Entrypoint
# ==============================================================================
if __name__ == "__main__":
    main()
