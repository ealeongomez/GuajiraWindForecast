# GuajiraWindForecast 🌬️

## Descripción del Proyecto

Sistema de pronóstico de viento para La Guajira utilizando inteligencia artificial y un chatbot conversacional. El proyecto integra datos climáticos de múltiples fuentes para proporcionar predicciones precisas y accesibles a través de una interfaz conversacional.

## Estructura del Proyecto

```
GuajiraWindForecast/
│
├── 📁 data/                         # Datos crudos y procesados
│   ├── raw/                         # Datos sin procesar desde la API
│   ├── processed/                   # Datos limpios, transformados
│   └── external/                    # Datasets adicionales (IDEAM, NASA, etc.)
│
├── 📁 notebooks/                    # Análisis exploratorio y prototipos
│
├── 📁 src/                          # Código fuente del proyecto
│   ├── __init__.py
│   ├── 📁 api/                      # Módulos para consumir API climática
│   ├── 📁 preprocessing/            # Limpieza y transformación de datos
│   ├── 📁 forecasting/              # Modelos de predicción
│   ├── 📁 chatbot/                  # ChatBot conversacional (LangChain, RAG, etc.)
│   ├── 📁 visualization/            # Gráficos y estadísticas
│   ├── 📁 server/                   # Backend para interacción local
│   └── 📁 config/                   # Configuración y parámetros
│
├── 📁 tests/                        # Pruebas unitarias
│
├── .env                             # Variables de entorno (API keys, rutas)
├── requirements.txt                 # Dependencias del proyecto
├── Dockerfile                       # (opcional) Para contenerización local
├── README.md                        # Descripción del proyecto
└── main.py 
```

## Características Principales

- **Predicción de Viento**: Modelos de machine learning para pronosticar velocidades y direcciones del viento
- **Chatbot Inteligente**: Interfaz conversacional usando LangChain y RAG
- **Integración Multi-Fuente**: Datos de IDEAM, NASA, OpenWeather y otras APIs
- **Visualización Avanzada**: Gráficos interactivos y reportes automáticos
- **API REST**: Backend para integración con aplicaciones externas

## Tecnologías Utilizadas

- **Python 3.11+**
- **LangChain** para el chatbot
- **FastAPI** para el servidor backend
- **Pandas/NumPy** para procesamiento de datos
- **Scikit-learn/Prophet** para modelos de predicción
- **Plotly/Matplotlib** para visualización
- **Docker** para contenerización

## Instalación

1. Clonar el repositorio:
```bash
git clone <url-del-repositorio>
cd GuajiraWindForecast
```

2. Crear entorno virtual:
```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

3. Instalar dependencias:
```bash
pip install -r requirements.txt
```

4. Configurar variables de entorno:
```bash
cp .env.example .env
# Editar .env con tus API keys
```

## Uso

### Ejecutar el servidor local:
```bash
python main.py
```

### Ejecutar con Docker:
```bash
docker build -t guajira-wind-forecast .
docker run -p 8000:8000 guajira-wind-forecast
```

## Desarrollo

### Estructura de Pruebas
- **Carpeta `tests/`**: Contiene todas las pruebas unitarias del proyecto
- **Pruebas por módulo**: Cada módulo tiene sus correspondientes pruebas
- **Documentación de pruebas**: Los tests están documentados en el README

### Flujo de Trabajo
1. Desarrollo en notebooks para prototipos
2. Implementación en módulos src/
3. Pruebas unitarias en tests/
4. Integración y despliegue

## Contribución

1. Fork el proyecto
2. Crear una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abrir un Pull Request

## Licencia

Este proyecto está bajo la Licencia MIT - ver el archivo [LICENSE](LICENSE) para detalles.

## Contacto

- **Autor**: [Tu Nombre]
- **Email**: [tu.email@ejemplo.com]
- **Proyecto**: [https://github.com/usuario/GuajiraWindForecast]

---

**Nota**: Este proyecto está en desarrollo activo. La estructura puede evolucionar según las necesidades del proyecto. 