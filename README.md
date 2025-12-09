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

## Package Management with UV

### Adding New Dependencies

Add a new package to your project:
```bash
# Add a regular dependency
uv add package-name

# Add a specific version
uv add package-name==1.2.3

# Add a dev dependency
uv add --dev package-name

# Example: Add numpy
uv add numpy
```

### Removing Dependencies

Remove a package:
```bash
uv remove package-name
```

### Updating Dependencies

Update all dependencies:
```bash
uv sync --upgrade
```

Update a specific package:
```bash
uv add package-name --upgrade
```

### Syncing Dependencies

Sync your environment with the lock file (do this after pulling changes):
```bash
uv sync
```

### Running Scripts

Run Python scripts using the UV-managed environment:
```bash
# Run a script
uv run python script.py

# Run with arguments
uv run python sync_items.py all

# Activate the virtual environment (alternative approach)
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows
```

### Viewing Dependencies

See all installed packages:
```bash
uv pip list
```

See dependency tree:
```bash
uv pip tree
```

### Lock File

The `uv.lock` file pins exact versions of all dependencies for reproducibility:
- **Always commit** `uv.lock` to version control
- Run `uv sync` after pulling changes that modify `pyproject.toml` or `uv.lock`
- UV automatically updates `uv.lock` when you add/remove dependencies