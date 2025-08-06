# 🧠 Agent Routing Architecture

This folder defines the logic for routing user queries in the **GuajiraWindForecast multi-agent system**. The architecture is based on a dispatcher-superagent and municipality-specific sub-agents.

## 🔄 Message Flow

```plaintext
🧑 User
   |
   ▼
🧠 Dispatcher Agent
   ├── Analyzes the user question
   ├── Detects the municipality (via NLP or rules)
   └── Routes the query to the appropriate sub-agent

         ▼
      Sub-Agents
      ├── RiohachaAgent   → Queries climate API or vector database
      ├── MaicaoAgent     → Queries climate API or vector database
      └── UribiaAgent     → Queries climate API or vector database
