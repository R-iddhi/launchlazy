from pathlib import Path
import ast
import json
import re
import os
import requests

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


app = FastAPI(
    title="LaunchLazy API",
    description="AI-assisted software launch-readiness analyzer",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ProjectRequest(BaseModel):
    path: str


class AIRequest(BaseModel):
    project_name: str
    project_types: list
    components: list
    important_files: list
    launch_readiness_score: int
    priority: str
    risks: list


IGNORED_FOLDERS = {
    "node_modules",
    ".git",
    "dist",
    "build",
    ".venv",
    "venv",
    "__pycache__",
    ".idea",
    ".vscode",
    "coverage",
    ".next",
    ".cache",
    ".pytest_cache",
    ".mypy_cache",
}


IMPORTANT_NAMES = {
    "README.md",
    "package.json",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "requirements.txt",
    "pyproject.toml",
    "Dockerfile",
    "docker-compose.yml",
    "vercel.json",
    "netlify.toml",
    "render.yaml",
    "railway.json",
    "Procfile",
    ".env",
    ".env.example",
    ".gitignore",
}


FRONTEND_EXTENSIONS = {
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
}


TEXT_EXTENSIONS = {
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".py",
    ".json",
    ".md",
    ".txt",
    ".toml",
    ".yaml",
    ".yml",
}


def relative_path(path: Path, project_path: Path):
    try:
        return str(path.relative_to(project_path))
    except ValueError:
        return str(path)


def read_text(file_path: Path):
    try:
        return file_path.read_text(
            encoding="utf-8",
            errors="ignore",
        )
    except OSError:
        return ""


# =========================================================
# ONE PROJECT SCAN
# =========================================================

def collect_project_files(project_path: Path):
    files = []

    for root, dirs, filenames in os.walk(project_path):

        # Prevent Python from even entering heavy folders
        dirs[:] = [
            directory
            for directory in dirs
            if directory not in IGNORED_FOLDERS
        ]

        root_path = Path(root)

        for filename in filenames:
            files.append(
                root_path / filename
            )

    return files


# =========================================================
# PYTHON HELPERS
# =========================================================

def read_python_ast(file_path: Path):
    try:
        return ast.parse(
            read_text(file_path)
        )
    except (
        SyntaxError,
        ValueError,
    ):
        return None


def get_python_imports(file_path: Path):
    tree = read_python_ast(
        file_path
    )

    if tree is None:
        return set()

    imports = set()

    for node in ast.walk(tree):

        if isinstance(
            node,
            ast.Import,
        ):
            for alias in node.names:
                imports.add(
                    alias.name.split(".")[0]
                )

        elif isinstance(
            node,
            ast.ImportFrom,
        ):
            if node.module:
                imports.add(
                    node.module.split(".")[0]
                )

    return imports


def has_wildcard_cors_origin(
    python_file: Path
):
    tree = read_python_ast(
        python_file
    )

    if tree is None:
        return False

    for node in ast.walk(tree):

        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        for keyword in node.keywords:

            if keyword.arg != "allow_origins":
                continue

            value = keyword.value

            if isinstance(
                value,
                (
                    ast.List,
                    ast.Tuple,
                    ast.Set,
                ),
            ):

                for item in value.elts:

                    if (
                        isinstance(
                            item,
                            ast.Constant,
                        )
                        and item.value == "*"
                    ):
                        return True

    return False


# =========================================================
# IMPORTANT FILES
# =========================================================

def find_important_files(
    files,
    project_path,
):
    important = []

    for file_path in files:

        if file_path.name in IMPORTANT_NAMES:
            important.append(
                relative_path(
                    file_path,
                    project_path,
                )
            )

    return sorted(important)


# =========================================================
# STACK / COMPONENT DETECTION
# =========================================================

def detect_project_types(
    files,
    project_path,
):
    detected = []
    components = []

    package_files = [
        file
        for file in files
        if file.name == "package.json"
    ]

    python_files = [
        file
        for file in files
        if file.suffix == ".py"
    ]

    # -----------------------------------------------------
    # Node components
    # -----------------------------------------------------

    for package_json in package_files:

        try:
            package_data = json.loads(
                read_text(package_json)
            )

        except json.JSONDecodeError:
            continue

        dependencies = {
            **package_data.get(
                "dependencies",
                {},
            ),
            **package_data.get(
                "devDependencies",
                {},
            ),
        }

        component_types = [
            "Node / JavaScript"
        ]

        if "react" in dependencies:
            component_types.append(
                "React"
            )

        if "vite" in dependencies:
            component_types.append(
                "Vite"
            )

        if "next" in dependencies:
            component_types.append(
                "Next.js"
            )

        if "vue" in dependencies:
            component_types.append(
                "Vue"
            )

        if "@angular/core" in dependencies:
            component_types.append(
                "Angular"
            )

        for technology in component_types:

            if technology not in detected:
                detected.append(
                    technology
                )

        component_path = (
            package_json.parent
        )

        display_path = (
            "."
            if component_path == project_path
            else relative_path(
                component_path,
                project_path,
            )
        )

        components.append({
            "path": display_path,
            "types": component_types,
        })

    # -----------------------------------------------------
    # Python components
    # -----------------------------------------------------

    python_components = {}

    for python_file in python_files:

        component_path = (
            python_file.parent
        )

        display_path = (
            "."
            if component_path == project_path
            else relative_path(
                component_path,
                project_path,
            )
        )

        if (
            display_path
            not in python_components
        ):
            python_components[
                display_path
            ] = {"Python"}

        imports = get_python_imports(
            python_file
        )

        if "fastapi" in imports:
            python_components[
                display_path
            ].add("FastAPI")

        if "flask" in imports:
            python_components[
                display_path
            ].add("Flask")

        if "django" in imports:
            python_components[
                display_path
            ].add("Django")

    order = [
        "Python",
        "FastAPI",
        "Flask",
        "Django",
    ]

    for (
        component_path,
        types,
    ) in python_components.items():

        component_types = [
            item
            for item in order
            if item in types
        ]

        for technology in component_types:

            if technology not in detected:
                detected.append(
                    technology
                )

        components.append({
            "path": component_path,
            "types": component_types,
        })

    # -----------------------------------------------------
    # Docker
    # -----------------------------------------------------

    if any(
        file.name == "Dockerfile"
        for file in files
    ):
        if "Docker" not in detected:
            detected.append(
                "Docker"
            )

    return detected, components


# =========================================================
# GITIGNORE
# =========================================================

def read_gitignore_entries(
    gitignore_path: Path
):
    entries = set()

    content = read_text(
        gitignore_path
    )

    for line in content.splitlines():

        line = line.strip()

        if not line:
            continue

        if line.startswith("#"):
            continue

        entries.add(line)

    return entries


# =========================================================
# SECRET SCAN
# =========================================================

def detect_secret_patterns(
    files,
    project_path,
):
    findings = []

    patterns = [
        (
            "Possible API key assignment",
            re.compile(
                r"""(?i)\b(api[_-]?key|secret[_-]?key|access[_-]?token)\b\s*[:=]\s*["'][^"']{8,}["']"""
            ),
        ),
        (
            "Possible password assignment",
            re.compile(
                r"""(?i)\b(password|passwd)\b\s*[:=]\s*["'][^"']{4,}["']"""
            ),
        ),
    ]

    for file_path in files:

        if (
            file_path.suffix
            not in TEXT_EXTENSIONS
        ):
            continue

        if (
            file_path.name
            == ".env.example"
        ):
            continue

        # Avoid scanning huge text files
        try:
            if (
                file_path.stat().st_size
                > 1_000_000
            ):
                continue
        except OSError:
            continue

        content = read_text(
            file_path
        )

        if not content:
            continue

        for label, pattern in patterns:

            if pattern.search(content):

                findings.append({
                    "file":
                        relative_path(
                            file_path,
                            project_path,
                        ),
                    "type": label,
                })

                break

    return findings


# =========================================================
# README
# =========================================================

def get_primary_readme(
    files,
    project_path,
):
    root_readme = (
        project_path /
        "README.md"
    )

    if root_readme in files:
        return root_readme

    readmes = [
        file
        for file in files
        if file.name == "README.md"
    ]

    if readmes:
        return readmes[0]

    return None


# =========================================================
# RISKS
# =========================================================

def detect_risks(
    files,
    project_path,
):
    risks = []

    package_files = [
        file
        for file in files
        if file.name == "package.json"
    ]

    python_files = [
        file
        for file in files
        if file.suffix == ".py"
    ]

    gitignore_files = [
        file
        for file in files
        if file.name == ".gitignore"
    ]

    env_files = [
        file
        for file in files
        if file.name == ".env"
    ]

    env_examples = [
        file
        for file in files
        if file.name == ".env.example"
    ]

    requirements_files = [
        file
        for file in files
        if file.name == "requirements.txt"
    ]

    pyproject_files = [
        file
        for file in files
        if file.name == "pyproject.toml"
    ]

    # =====================================================
    # README
    # =====================================================

    main_readme = get_primary_readme(
        files,
        project_path,
    )

    if main_readme is None:

        risks.append({
            "severity": "high",
            "title": "README missing",
            "reason":
                "No README.md was detected.",
            "fix":
                "Add setup, run, configuration and deployment instructions.",
        })

    else:

        readme_content = read_text(
            main_readme
        ).lower()

        if (
            len(
                readme_content.strip()
            )
            < 300
        ):
            risks.append({
                "severity": "medium",
                "title":
                    "README appears too short",
                "reason":
                    "The README contains limited project documentation.",
                "fix":
                    "Add project purpose, setup, run commands, architecture and deployment guidance.",
                "files": [
                    relative_path(
                        main_readme,
                        project_path,
                    )
                ],
            })

        setup_words = [
            "install",
            "installation",
            "setup",
            "getting started",
        ]

        if not any(
            word in readme_content
            for word in setup_words
        ):
            risks.append({
                "severity": "medium",
                "title":
                    "README lacks setup instructions",
                "reason":
                    "No clear installation or setup guidance was detected.",
                "fix":
                    "Add installation and setup instructions.",
                "files": [
                    relative_path(
                        main_readme,
                        project_path,
                    )
                ],
            })

        run_words = [
            "npm run",
            "uvicorn",
            "python ",
            "run the",
            "start the",
        ]

        if not any(
            word in readme_content
            for word in run_words
        ):
            risks.append({
                "severity": "medium",
                "title":
                    "README lacks run instructions",
                "reason":
                    "No clear command for running the application was detected.",
                "fix":
                    "Add exact frontend and backend run commands.",
                "files": [
                    relative_path(
                        main_readme,
                        project_path,
                    )
                ],
            })

    # =====================================================
    # ENVIRONMENT FILES
    # =====================================================

    if (
        env_files
        and not env_examples
    ):
        risks.append({
            "severity": "high",
            "title":
                ".env exists but .env.example is missing",
            "reason":
                "Environment variables are in use but no safe template was found.",
            "fix":
                "Create .env.example with variable names and placeholder values.",
        })

    # =====================================================
    # GITIGNORE
    # =====================================================

    if not gitignore_files:

        risks.append({
            "severity": "high",
            "title":
                ".gitignore missing",
            "reason":
                "Generated files or sensitive configuration could be committed.",
            "fix":
                "Add an appropriate .gitignore.",
        })

    else:

        combined_entries = set()

        for gitignore in gitignore_files:

            combined_entries.update(
                read_gitignore_entries(
                    gitignore
                )
            )

        if package_files:

            if (
                "node_modules"
                not in combined_entries
                and
                "node_modules/"
                not in combined_entries
            ):
                risks.append({
                    "severity": "medium",
                    "title":
                        "node_modules not ignored",
                    "reason":
                        "A Node.js project was found but node_modules is not clearly ignored.",
                    "fix":
                        "Add node_modules/ to .gitignore.",
                })

        if python_files:

            virtual_env_entries = {
                ".venv",
                ".venv/",
                "venv",
                "venv/",
            }

            if not any(
                entry
                in combined_entries
                for entry
                in virtual_env_entries
            ):
                risks.append({
                    "severity": "medium",
                    "title":
                        "Python virtual environment not ignored",
                    "reason":
                        "Python code was detected but no virtual environment ignore rule was found.",
                    "fix":
                        "Add .venv/ or venv/ to .gitignore.",
                })

        if env_files:

            if (
                ".env"
                not in combined_entries
            ):
                risks.append({
                    "severity": "high",
                    "title":
                        ".env is not ignored",
                    "reason":
                        "A real .env file exists but .gitignore does not exclude it.",
                    "fix":
                        "Add .env to .gitignore.",
                })

    # =====================================================
    # NODE
    # =====================================================

    for package_json in package_files:

        display_path = (
            relative_path(
                package_json,
                project_path,
            )
        )

        try:

            package_data = json.loads(
                read_text(
                    package_json
                )
            )

        except json.JSONDecodeError:

            risks.append({
                "severity": "high",
                "title":
                    "Invalid package.json",
                "reason":
                    f"{display_path} could not be parsed.",
                "fix":
                    "Fix the JSON syntax.",
                "files": [
                    display_path
                ],
            })

            continue

        scripts = package_data.get(
            "scripts",
            {},
        )

        if "build" not in scripts:

            risks.append({
                "severity": "high",
                "title":
                    "Production build script missing",
                "reason":
                    f"{display_path} does not define a build script.",
                "fix":
                    "Add a production build command.",
                "files": [
                    display_path
                ],
            })

        if "test" not in scripts:

            risks.append({
                "severity": "medium",
                "title":
                    "Automated test script missing",
                "reason":
                    f"{display_path} does not define a test script.",
                "fix":
                    "Add automated tests and a test script.",
                "files": [
                    display_path
                ],
            })

        component_folder = (
            package_json.parent
        )

        lock_names = {
            "package-lock.json",
            "yarn.lock",
            "pnpm-lock.yaml",
        }

        has_lockfile = any(
            file.parent
            == component_folder
            and file.name
            in lock_names
            for file in files
        )

        if not has_lockfile:

            risks.append({
                "severity": "medium",
                "title":
                    "Node lockfile missing",
                "reason":
                    f"No package manager lockfile was found beside {display_path}.",
                "fix":
                    "Commit package-lock.json, yarn.lock or pnpm-lock.yaml.",
                "files": [
                    display_path
                ],
            })

    # =====================================================
    # PYTHON DEPENDENCIES
    # =====================================================

    if (
        python_files
        and
        not requirements_files
        and
        not pyproject_files
    ):
        risks.append({
            "severity": "high",
            "title":
                "Python dependencies are not documented",
            "reason":
                "Python source files were detected but no requirements.txt or pyproject.toml was found.",
            "fix":
                "Add requirements.txt or pyproject.toml.",
        })

    # =====================================================
    # LOCALHOST
    # =====================================================

    localhost_files = []

    for file_path in files:

        if (
            file_path.suffix
            not in FRONTEND_EXTENSIONS
        ):
            continue

        content = read_text(
            file_path
        )

        has_localhost = (
            "localhost" in content
            or
            "127.0.0.1"
            in content
        )

        uses_environment_config = (
            "import.meta.env"
            in content
            or
            "process.env"
            in content
        )

        if (
            has_localhost
            and
            not uses_environment_config
        ):
            localhost_files.append(
                relative_path(
                    file_path,
                    project_path,
                )
            )

    if localhost_files:

        risks.append({
            "severity": "high",
            "title":
                "Hard-coded localhost URL detected",
            "reason":
                "Frontend code uses a development-only address without environment configuration.",
            "fix":
                "Move API URLs into environment variables.",
            "files":
                localhost_files[:10],
        })

    # =====================================================
    # CORS
    # =====================================================

    cors_files = []

    for python_file in python_files:

        if has_wildcard_cors_origin(
            python_file
        ):
            cors_files.append(
                relative_path(
                    python_file,
                    project_path,
                )
            )

    if cors_files:

        risks.append({
            "severity": "high",
            "title":
                "Wildcard CORS origin detected",
            "reason":
                "The backend accepts browser requests from every origin.",
            "fix":
                "Restrict CORS to known frontend origins.",
            "files":
                cors_files,
        })

    # =====================================================
    # SECRETS
    # =====================================================

    secret_findings = (
        detect_secret_patterns(
            files,
            project_path,
        )
    )

    if secret_findings:

        risks.append({
            "severity": "high",
            "title":
                "Possible hard-coded secret detected",
            "reason":
                "LaunchLazy found source text that resembles a hard-coded API key, token or password.",
            "fix":
                "Review the flagged files and move real secrets into environment variables.",
            "files": [
                item["file"]
                for item
                in secret_findings[:10]
            ],
        })

    # =====================================================
    # DEPLOYMENT
    # =====================================================

    deployment_markers = {
        "Dockerfile",
        "docker-compose.yml",
        "vercel.json",
        "netlify.toml",
        "render.yaml",
        "railway.json",
        "Procfile",
    }

    deployment_found = any(
        file.name
        in deployment_markers
        for file in files
    )

    if not deployment_found:

        risks.append({
            "severity": "low",
            "title":
                "No deployment configuration detected",
            "reason":
                "No common deployment configuration file was found.",
            "fix":
                "Add deployment configuration or document the deployment process clearly in README.md.",
        })

    return risks


# =========================================================
# SCORE
# =========================================================

def calculate_score(risks):
    score = 100

    weights = {
        "high": 15,
        "medium": 8,
        "low": 3,
    }

    for risk in risks:

        score -= weights.get(
            risk.get("severity"),
            0,
        )

    return max(
        score,
        0,
    )


def calculate_priority(score):

    if score >= 90:
        return "Low"

    if score >= 70:
        return "Medium"

    return "High"


# =========================================================
# AI
# =========================================================

def get_ai_analysis(
    project_name,
    project_types,
    components,
    important_files,
    score,
    priority,
    risks,
):

    evidence = {
        "project_name":
            project_name,
        "project_types":
            project_types,
        "components":
            components,
        "important_files":
            important_files,
        "readiness_score":
            score,
        "priority":
            priority,
        "risks":
            risks,
    }

    prompt = f"""
You are the reasoning layer inside LaunchLazy,
an AI-assisted software launch-readiness auditor.

Use ONLY this verified evidence:

{json.dumps(evidence, indent=2)}

Rules:

- Do not invent infrastructure.
- Do not invent databases.
- Do not invent authentication.
- Do not invent cloud providers.
- Do not invent teams.
- Do not change the supplied priority.
- Never claim the software is guaranteed production-ready.
- Focus on the highest-severity verified findings first.
- Refer to concrete files and technologies.
- Keep the response concise.

Return exactly:

OVERALL ASSESSMENT:
<2 or 3 sentences>

PRIORITY:
{priority}

WHY THIS SCORE:
<evidence-based explanation>

REMAINING MANUAL CHECKS:
- <check 1>
- <check 2>
- <check 3>

NEXT ACTIONS:
1. <highest-priority action>
2. <second action>
3. <third action>
"""

    try:

        response = requests.post(
            "http://127.0.0.1:11434/api/generate",
            json={
                "model":
                    "qwen2.5:3b",
                "prompt":
                    prompt,
                "stream":
                    False,
                "options": {
                    "temperature":
                        0.0,
                    "num_predict":
                        280,
                },
            },
            timeout=90,
        )

        response.raise_for_status()

        model_text = (
            response
            .json()
            .get(
                "response",
                "",
            )
            .strip()
        )

        if not model_text:
            return (
                "AI analysis returned no readable content."
            )

        disclaimer = (
            "AUTOMATED CHECK STATUS:\n"
            f"LaunchLazy score: {score}/100. "
            "This score measures only the currently "
            "implemented automated checks and is not "
            "a guarantee of production readiness.\n\n"
        )

        return (
            disclaimer
            + model_text
        )

    except requests.exceptions.ConnectionError:

        return (
            "AI analysis unavailable. "
            "Ollama is not running."
        )

    except requests.exceptions.Timeout:

        return (
            "AI analysis timed out."
        )

    except requests.exceptions.RequestException as error:

        return (
            f"AI analysis failed: {error}"
        )


# =========================================================
# ROUTES
# =========================================================

@app.get("/")
def root():

    return {
        "message":
            "LaunchLazy backend is running"
    }


@app.post("/inspect")
def inspect_project(
    request: ProjectRequest
):

    project_path = Path(
        request.path
    ).expanduser()

    if not project_path.exists():

        raise HTTPException(
            status_code=404,
            detail=
                "Project folder not found",
        )

    if not project_path.is_dir():

        raise HTTPException(
            status_code=400,
            detail=
                "Path must be a folder",
        )

    # ONE filesystem traversal
    files = collect_project_files(
        project_path
    )

    important_files = (
        find_important_files(
            files,
            project_path,
        )
    )

    (
        project_types,
        components,
    ) = detect_project_types(
        files,
        project_path,
    )

    risks = detect_risks(
        files,
        project_path,
    )

    score = calculate_score(
        risks
    )

    priority = (
        calculate_priority(
            score
        )
    )

    return {
        "project_name":
            project_path.name,

        "project_path":
            str(project_path),

        "important_files":
            important_files,

        "files_found":
            len(important_files),

        "project_types":
            project_types,

        "components":
            components,

        "launch_readiness_score":
            score,

        "priority":
            priority,

        "risks_found":
            len(risks),

        "risks":
            risks,
    }


@app.post("/analyze-ai")
def analyze_ai(
    request: AIRequest
):

    ai_analysis = (
        get_ai_analysis(
            project_name=
                request.project_name,

            project_types=
                request.project_types,

            components=
                request.components,

            important_files=
                request.important_files,

            score=
                request.launch_readiness_score,

            priority=
                request.priority,

            risks=
                request.risks,
        )
    )

    return {
        "ai_analysis":
            ai_analysis
    }