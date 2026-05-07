# Cloud Operational Agent 🚀

An LLM-powered chatbot that provides intelligent insights across **Kubernetes operations**, **cloud cost analysis**, and **uptime monitoring**. Built with LangChain, LangGraph, and Streamlit.

## Architecture

```
┌─────────────────────────────────────────────┐
│        Streamlit Chatbot Interface          │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│         LangGraph Router Agent              │
│  (Intent Classification + Routing)          │
└──┬────────────────┬──────────────┬──────────┘
   │                │              │
   │                │              │
┌──▼─────┐ ┌──────▼──────┐ ┌─────▼──────┐
│ PowerBI │ │   Uptime    │ │   Health   │
│ Agent   │ │   Robot     │ │ (Grafana)  │
│ (FinOps)│ │   Agent     │ │   Agent    │
└────┬────┘ └──────┬──────┘ └─────┬──────┘
     │             │              │
     │             │              │
┌────▼─┐      ┌───▼────┐     ┌───▼────┐
│ CSV/ │      │ Uptime │     │Prometheus
│Google│      │ Robot  │     │ Grafana
│Sheet │      │  API   │     │ Loki
└──────┘      └────────┘     └────────┘
```

## Features

- ✅ **Intent-based Routing**: Automatically routes queries to the correct agent
- ✅ **Kubernetes Monitoring**: Pod health, resources, and log retrieval via Prometheus/Grafana/Loki
- ✅ **Cost Analytics**: Cloud spend analysis (currently using mock data)
- ✅ **Uptime Monitoring**: SLA, incident history, and response times via Uptime Robot
- ✅ **Streamlit UI**: Interactive chat interface with streaming responses
- ✅ **Multi-tool Support**: MCP servers for extending functionality

## Project Structure

```
cloud-operation-agent/
├── src/
│   └── cloud_agent/
│       ├── __init__.py
│       ├── brain.py                 # Core LangGraph router & agent setup
│       ├── helper_function.py       # Tool implementations (Grafana, Uptime Robot, Power BI)
│       └── template_structure.py    # Prompt templates for each domain
├── static/
│   └── images/
│       └── coeLogo.jpg
├── tests/
│   └── (test files)
├── ui.py                            # Streamlit app entry point
├── pyproject.toml                   # Project configuration & dependencies
├── .env.example                     # Environment variables template
├── .gitignore
└── README.md
```

## Prerequisites

- **Python**: 3.10+
- **uv**: Package manager (install from https://github.com/astral-sh/uv)
- **API Keys**:
  - Azure OpenAI credentials (GITHUB_TOKEN, ENDPOINT)
  - Uptime Robot API key
  - Grafana API token
  - Optional: Power BI credentials (if using real Power BI)

## Setup Instructions

### 1. Clone or Initialize the Project

```bash
cd c:\Users\mansi\COA
```

### 2. Install uv (if not already installed)

On Windows:
```powershell
# Using pip
pip install uv

# Or download from: https://github.com/astral-sh/uv/releases
```

On macOS/Linux:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 3. Create Virtual Environment with uv

```bash
uv venv .venv
```

Activate the virtual environment:

**Windows (PowerShell)**:
```powershell
.\.venv\Scripts\Activate.ps1
```

**Windows (cmd)**:
```cmd
.\.venv\Scripts\activate.bat
```

**macOS/Linux**:
```bash
source .venv/bin/activate
```

### 4. Install Dependencies with uv

```bash
# Install all project dependencies
uv sync

# Install with dev dependencies
uv sync --all-extras
```

Or use pip with the lock file:
```bash
pip install -r requirements.txt
```

### 5. Configure Environment Variables

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env` with your actual values:
```
AZURE_OPENAI_API_KEY=your_key_here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
API_KEY_UPTIMEROBOT=your_key_here
MCP_GRAFANA_URL=https://grafana.example.com
MCP_GRAFANA_TOKEN=your_token_here
NAMESPACE=your_k8s_namespace
# ... etc
```

### 6. Run the Streamlit App

```bash
streamlit run ui.py
```

The app will be available at: `http://localhost:8501`

### 7. Login

Default credentials:
- **Username**: `admin`
- **Password**: `pass123`

Change these in [ui.py](ui.py) → `Login_info` dictionary.

## Usage Examples

### Kubernetes Operations
```
"List all pod names"
"What's the CPU usage for pod X?"
"Get logs for deployment Y"
"Which pod is using the most memory?"
```

### Uptime Monitoring
```
"What's the SLA this month?"
"List incidents in the last 7 days"
"What's the response time for mysoftware.dnv.com?"
"Is the service UP or DOWN?"
```

### Cost Analysis (FinOps)
```
"What was the cost in March 2025?"
"Compare costs between last month and this month"
"Which resource is using the most cost?"
"Show cost breakdown by resource type"
```

## File Descriptions

### Core Files

#### [src/cloud_agent/brain.py](src/cloud_agent/brain.py)
- **LangGraph Router**: Routes queries to appropriate agents based on intent
- **Agent Setup**: Initializes PowerBI, Uptime, Health, and Default agents
- **Tool Partitioning**: Assigns specific tools to each agent to reduce token usage
- **Chat Function**: Main entry point for processing user queries

#### [src/cloud_agent/helper_function.py](src/cloud_agent/helper_function.py)
- **Uptime Robot Tools**: `get_mysoftware_sla()`, `get_monitor_status()`, `get_monitor_incidents()`, `get_monitor_response_times()`
- **Grafana Tools**: `get_all_deployments_json()`, `get_all_pod_resources_json()`, `get_pod_logs_json()`, `list_datasources()`
- **Power BI Tools**: `execute_dax_query()`, `fetch_model_schema_compact()`, `fetch_model_schema()`

#### [src/cloud_agent/template_structure.py](src/cloud_agent/template_structure.py)
- **Prompt Templates**: System prompts for each agent domain
- `powerbi_template`: Financial agent instructions
- `uptime_template`: Monitoring agent instructions
- `grafana_template`: Health/Kubernetes agent instructions
- `default_template`: Fallback agent instructions

#### [ui.py](ui.py)
- **Streamlit Interface**: Chat UI with login, message history, and generation indicators
- **Session Management**: Handles user authentication and chat state
- **Background Execution**: Runs agent in separate thread for responsive UI

#### [pyproject.toml](pyproject.toml)
- **Project Metadata**: Package name, version, description
- **Dependencies**: All required packages (LangChain, Streamlit, Azure OpenAI, etc.)
- **Dev Dependencies**: Testing and linting tools
- **uv Configuration**: Tool-specific settings

## Development

### Running Tests

```bash
pytest tests/
```

### Code Formatting

```bash
black src/ ui.py
```

### Linting

```bash
ruff check src/ ui.py
```

### Type Checking

```bash
mypy src/
```

## Environment Variables Reference

| Variable | Description | Required |
|----------|-------------|----------|
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API key | Yes |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint URL | Yes |
| `API_KEY_UPTIMEROBOT` | Uptime Robot API key | Yes |
| `MONITOR_ID` | Uptime Robot monitor ID | Yes |
| `MCP_GRAFANA_URL` | Grafana API endpoint | Yes |
| `MCP_GRAFANA_TOKEN` | Grafana bearer token | Yes |
| `NAMESPACE` | Kubernetes namespace | Yes |
| `POWERBI_DATASET_ID` | Power BI dataset ID | Optional |
| `POWERBI_WORKSPACE_ID` | Power BI workspace ID | Optional |
| `DEBUG_TOOL_NAMES` | Enable tool name debugging | No |

## Troubleshooting

### Issue: "No Prometheus datasource found"
- Ensure Grafana URL and token are correct in `.env`
- Verify Prometheus datasource exists in Grafana

### Issue: "Invalid Uptime Robot API key"
- Check `API_KEY_UPTIMEROBOT` and `MONITOR_ID` in `.env`
- Verify at https://uptimerobot.com/dashboard

### Issue: Streamlit app won't start
- Ensure virtual environment is activated
- Check `.env` file exists and has valid values
- Run `uv sync` again to ensure all dependencies are installed

### Issue: Import errors in Python
- Verify you're in the correct directory: `c:\Users\mansi\COA`
- Check virtual environment is activated
- Run `uv sync` to install missing packages

## Next Steps

### Immediate
1. ✅ Set up the project structure (Done!)
2. → Configure `.env` with your credentials
3. → Run Streamlit app: `streamlit run ui.py`
4. → Test with sample queries

### Short-term
- Add unit tests for helper functions
- Implement caching for API responses
- Add cost data integration with Google Sheets
- Improve prompt templates based on user feedback

### Long-term
- Add more monitoring integrations (Datadog, New Relic, etc.)
- Implement conversation persistence (database)
- Add admin dashboard for configuration management
- Deploy to production (Docker, Kubernetes, Cloud Run)

## Tech Stack

| Component | Technology |
|-----------|------------|
| **LLM Framework** | LangChain, LangGraph |
| **LLM Model** | Azure OpenAI (gpt-4.1-mini) |
| **UI** | Streamlit |
| **Monitoring** | Prometheus, Grafana, Loki |
| **Uptime** | Uptime Robot API |
| **Cost** | Power BI / Google Sheets (mock data) |
| **Package Manager** | uv |
| **Python** | 3.10+ |

## License

MIT License - See LICENSE file for details

## Support

For issues or questions:
1. Check the Troubleshooting section above
2. Review the code comments in the relevant files
3. Check `.env.example` for missing configuration

---

