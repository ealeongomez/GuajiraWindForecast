# GuajiraWindForecast 🌬️

## Project Description

Wind forecasting system for La Guajira using artificial intelligence and a conversational chatbot. The project integrates climate data from multiple sources to provide accurate and accessible predictions through a conversational interface.

## Project Structure

```
GuajiraWindForecast/
│
├── 📁 data/                         # Raw and processed data
│   ├── raw/                         # Unprocessed data from API
│   ├── processed/                   # Clean, transformed data
│   └── external/                    # Additional datasets (IDEAM, NASA, etc.)
│
├── 📁 notebooks/                    # Exploratory analysis and prototypes
│
├── 📁 src/                          # Project source code
│   ├── __init__.py
│   ├── 📁 api/                      # Modules for consuming climate API
│   ├── 📁 preprocessing/            # Data cleaning and transformation
│   ├── 📁 forecasting/              # Prediction models
│   ├── 📁 chatbot/                  # Conversational ChatBot (LangChain, RAG, etc.)
│   ├── 📁 prompts/                  # Prompt templates and constants
│   ├── 📁 visualization/            # Charts and statistics
│   ├── 📁 server/                   # Backend for local interaction
│   └── 📁 config/                   # Configuration and parameters
│
├── 📁 tests/                        # Unit tests
│
├── .env                             # Environment variables (API keys, paths)
├── requirements.txt                 # Project dependencies
├── Dockerfile                       # (optional) For local containerization
├── README.md                        # Project description
└── main.py 
```

## Main Features

- **Wind Prediction**: Machine learning models to forecast wind speeds and directions
- **Intelligent Chatbot**: Conversational interface using LangChain and RAG
- **Multi-Source Integration**: Data from IDEAM, NASA, OpenWeather and other APIs
- **Advanced Visualization**: Interactive charts and automatic reports
- **REST API**: Backend for integration with external applications

## Technologies Used

- **Python 3.11+**
- **LangChain** for the chatbot
- **FastAPI** for the backend server
- **Pandas/NumPy** for data processing
- **Scikit-learn/Prophet** for prediction models
- **Plotly/Matplotlib** for visualization
- **Docker** for containerization

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd GuajiraWindForecast
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your API keys
```

## Usage

### Run local server:
```bash
python main.py
```

### Run with Docker:
```bash
docker build -t guajira-wind-forecast .
docker run -p 8000:8000 guajira-wind-forecast
```

## Development

### Project Organization
- **`src/prompts/` folder**: Contains all prompt templates and constants
- **Modular prompts**: Each prompt type has its own file
- **Centralized constants**: All system constants in one place
- **Easy imports**: Simple import structure for all prompts

### Test Structure
- **`tests/` folder**: Contains all unit tests for the project
- **Tests by module**: Each module has its corresponding tests
- **Test documentation**: Tests are documented in the README

### Prompt Management
- **Organized prompts**: All prompts stored in `src/prompts/`
- **Reusable templates**: Prompts can be imported and reused
- **Version control**: Easy to track changes in prompts
- **Documentation**: Complete documentation for each prompt

### Workflow
1. Development in notebooks for prototypes
2. Implementation in src/ modules
3. Unit tests in tests/
4. Integration and deployment

## Contributing

1. Fork the project
2. Create a branch for your feature (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contact

- **Author**: [Your Name]
- **Email**: [ealeongomez@unal.edu.co]
- **Project**: [https://github.com/user/GuajiraWindForecast]

---

**Note**: This project is under active development. The structure may evolve according to project needs. 