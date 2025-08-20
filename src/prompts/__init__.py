"""
Módulo de prompts para el sistema de ChatBot de La Guajira
"""

from .router_prompt import router_prompt_template
from .subagent_prompt import subagent_prompt_template
from .constants import MUNICIPIOS, TEMAS, FAREWELL_PATTERNS, CLIMATE_KEYWORDS

__all__ = [
    'router_prompt_template',
    'subagent_prompt_template',
    'MUNICIPIOS',
    'TEMAS', 
    'FAREWELL_PATTERNS',
    'CLIMATE_KEYWORDS'
]
