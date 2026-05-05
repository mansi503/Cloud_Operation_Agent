@echo off
echo Starting GCP Mock Exporter...
start "GCP Mock Exporter" cmd /k "cd /d C:\Users\mansi\COA && python gcp_mock_exporter.py"

echo Starting Prometheus...
start "Prometheus" cmd /k "cd /d C:\prometheus\prometheus-3.11.3.windows-amd64 && prometheus.exe"

timeout /t 3

echo Starting Streamlit...
start "Streamlit" cmd /k "cd /d C:\Users\mansi\COA && streamlit run ui.py"

echo All services started!