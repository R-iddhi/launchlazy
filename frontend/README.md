# LaunchLazy

LaunchLazy is an AI-assisted software launch-readiness auditor.

It scans a local software project, detects common launch risks, calculates a readiness score, and uses a local open-weight model through Ollama to explain what should be fixed next.

## What LaunchLazy Does

LaunchLazy checks project structure and configuration for issues such as:

- missing README documentation
- missing environment variable templates
- missing or weak `.gitignore`
- missing build scripts
- missing test scripts
- missing Node lockfiles
- undocumented Python dependencies
- hard-coded localhost URLs
- risky wildcard CORS configuration
- possible hard-coded secrets
- missing deployment configuration

It then generates:

- detected technology stack
- frontend/backend component breakdown
- launch-readiness score
- prioritized risk list
- AI-assisted explanation
- downloadable Markdown launch report

## Tech Stack

### Frontend

- React
- Vite
- Axios

### Backend

- Python
- FastAPI
- Uvicorn
- Requests

### Local AI

- Ollama
- Qwen 2.5 3B

## Project Structure

```text
launchlazy/
├── backend/
│   ├── main.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   ├── package.json
│   ├── package-lock.json
│   ├── .env.example
│   └── .gitignore
└── README.md