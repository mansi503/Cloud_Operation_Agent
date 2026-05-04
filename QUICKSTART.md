# Quick Start Guide - Cloud Operation Agent

## 🚀 5-Minute Setup

### Step 1: Activate Virtual Environment

```powershell
# PowerShell
.\.venv\Scripts\Activate.ps1

# CMD
.\.venv\Scripts\activate.bat
```

### Step 2: Install Dependencies

```bash
uv sync
```

Or with pip:
```bash
pip install -r requirements.txt
```

### Step 3: Configure Environment

1. Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

2. Edit `.env` and add your credentials:
```
AZURE_OPENAI_API_KEY=your_key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
API_KEY_UPTIMEROBOT=your_key
MONITOR_ID=your_monitor_id
MCP_GRAFANA_URL=https://grafana.example.com
MCP_GRAFANA_TOKEN=your_token
NAMESPACE=your_namespace
GITHUB_TOKEN=same_as_azure_key
ENDPOINT=same_as_azure_endpoint
```

### Step 4: Run the App

```bash
streamlit run ui.py
```

App opens at: `http://localhost:8501`

### Step 5: Login

- **Username**: `admin`
- **Password**: `pass123`

---

## 📁 Project Layout After Setup

```
COA/
├── .venv/                    # Virtual environment (auto-created)
├── src/cloud_agent/          # Main package
│   ├── __init__.py
│   ├── brain.py              # Router & agent setup
│   ├── helper_function.py    # All API tools
│   └── template_structure.py # System prompts
├── static/images/            # Logo files
├── tests/                     # Test files
├── ui.py                      # Streamlit app
├── pyproject.toml            # Project config
├── .env                      # Your credentials (DO NOT COMMIT)
├── .env.example              # Template
├── .gitignore                # Git ignore rules
├── requirements.txt          # Pip dependencies
└── README.md                 # Full documentation
```

---

## 🧪 Test Your Setup

### Test 1: Python Import
```python
python -c "from src.cloud_agent.brain import setup; print('✅ Imports OK')"
```

### Test 2: Environment Variables
```python
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print(f'✅ Env loaded: NAMESPACE={os.getenv(\"NAMESPACE\")}')"
```

### Test 3: Run CLI Test (without Streamlit)
```python
python -c "
import asyncio
from src.cloud_agent.brain import setup

async def test():
    print('Setting up agent...')
    app = await setup()
    print('✅ Agent ready!')

asyncio.run(test())
"
```

---

## 🎯 Example Queries to Try

### Kubernetes (Health Agent)
```
"List all pods"
"What's the CPU usage?"
"Get logs for pod xyz"
```

### Uptime (Monitoring Agent)
```
"What's the SLA?"
"List recent incidents"
"Is mysoftware.dnv.com up?"
```

### Cost (FinOps Agent)
```
"What was March cost?"
"Compare costs"
"Most expensive resource?"
```

---

## 🔧 Useful Commands

### Update Dependencies
```bash
uv sync --upgrade
```

### Add New Package
```bash
uv pip install package_name
```

### Check Installed Packages
```bash
uv pip list
```

### Run Linting
```bash
black src/ ui.py
ruff check src/ ui.py
```

### Run Tests
```bash
pytest tests/ -v
```

---

## ❌ Common Issues & Fixes

| Issue | Fix |
|-------|-----|
| `ModuleNotFoundError: No module named 'streamlit'` | Run `uv sync` again |
| `.env` file not found | Copy `.env.example` to `.env` |
| Grafana connection error | Check `MCP_GRAFANA_URL` and token |
| Uptime Robot API error | Verify `API_KEY_UPTIMEROBOT` and `MONITOR_ID` |
| Port 8501 already in use | `streamlit run ui.py --server.port 8502` |
| Azure OpenAI auth failed | Check `AZURE_OPENAI_API_KEY` and `ENDPOINT` |

---

## 📚 Next Steps

1. **Customize Login**: Edit `Login_info` in `ui.py`
2. **Add More Queries**: Modify prompt templates in `template_structure.py`
3. **Extend Tools**: Add more functions to `helper_function.py`
4. **Deploy**: Use Docker or Cloud Run for production

---

## 📖 Documentation

- Full setup: See [README.md](README.md)
- Architecture: See [README.md#Architecture](README.md#architecture)
- API reference: See docstrings in `helper_function.py`

---

**Ready to chat?** Run `streamlit run ui.py` and start asking questions! 🎉
