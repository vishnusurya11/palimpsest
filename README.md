# palimpsest
AI-driven Palimpsest engine for turning public domain books into structured codices, videos, and new mythologies.

## Setup

### Prerequisites
- Python 3.10 or higher
- [uv](https://github.com/astral-sh/uv) - Fast Python package installer and resolver

### Installation

1. Install uv (if not already installed):
```bash
# On macOS and Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# On Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

2. Clone the repository and sync dependencies:
```bash
git clone https://github.com/vishnusurya11/palimpsest.git
cd palimpsest
uv sync
```

3. Set up your GitHub token:
```bash
cp .env.example .env
# Edit .env and add your GitHub personal access token
```

## Usage

### GitHub Issue Management

Sync GitHub issues from the YAML configuration:

```bash
# Sync specific issue types
uv run python sync_items.py epic
uv run python sync_items.py story
uv run python sync_items.py task
uv run python sync_items.py subtask

# Or sync everything at once
uv run python sync_items.py all
```

### Development

Install dev dependencies:
```bash
uv sync --extra dev
```

Run tests:
```bash
uv run pytest
```

Format code:
```bash
uv run black .
uv run ruff check .
```