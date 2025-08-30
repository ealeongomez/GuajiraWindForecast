"""
Constantes y configuraciones para el sistema multiagente de La Guajira
"""

# Municipios soportados
MUNICIPIOS = [
    "riohacha",
    "maicao",
    "uribia",
    "manaure",
    "fonseca",
    "san juan del cesar",
    "albania",
    "barrancas",
    "distraccion",
    "el molino",
    "hatonuevo",
    "la jagua del pilar",
    "mingueo",
]

# Temas climáticos disponibles
TEMAS = [
        "viento (velocidad/dirección/ráfagas)",
        "pronóstico de viento (1h/24)"
]

# Patrones de despedida
FAREWELL_PATTERNS = {
    "gracias", 
    "muchas gracias", 
    "adios", 
    "adiós", 
    "hasta luego", 
    "bye", 
    "chao"
}

# Palabras clave para identificar consultas climáticas
CLIMATE_KEYWORDS = [
    r"clima", r"meteorolog", r"tiempo", r"pron[oó]stico", r"viento", r"racha",
    r"velocidad.*viento", r"direcci[oó]n.*viento", r"temperatura", r"t[eé]rmica",
    r"humedad", r"precipitaci[oó]n", r"lluvia", r"pluviosidad", r"nubosidad",
    r"radiaci[oó]n", r"solar", r"uv", r"tormenta", r"hurac[aá]n", r"fen[oó]meno",
    r"enso", r"alerta.*climat", r"ola.*calor", r"sequ[ií]a"
]
