# Contributing to Local Research & Synthesis Desk

Thank you for your interest in contributing! This project demonstrates multi-agent orchestration using Microsoft Agent Framework and Foundry Local.

## First-Time Contributors

New to this project? Here are some good starting points:

- **Read the README** — understand what the demo does and how to run it.
- **Run the demo** — try `python -m src.app "Hello" --docs ./data` and explore the output.
- **Run the web UI** — launch `python -m src.app.web` and explore the browser interface.
- **Look at the tests** — `tests/test_smoke.py` shows how the components work in isolation.
- **Browse open issues** — look for issues tagged `good first issue` or `help wanted`.

## Getting Started

1. Fork this repository
2. Clone your fork locally
3. Create a virtual environment and install dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
# or: source .venv/bin/activate  # macOS/Linux

pip install -r requirements.txt
```

4. Ensure [Foundry Local](https://github.com/microsoft/Foundry-Local) is installed
5. Verify the setup:

```bash
# Run smoke tests (no Foundry Local service required)
python -m pytest tests/ -v

# Run the tool demo (requires Foundry Local)
python -m src.app.tool_demo
```

## Development Workflow

### Branch Naming

Use descriptive branch names:

| Prefix | Purpose | Example |
|--------|---------|---------|
| `feature/` | New functionality | `feature/group-chat-pattern` |
| `fix/` | Bug fixes | `fix/tool-agent-timeout` |
| `docs/` | Documentation only | `docs/improve-readme` |
| `test/` | New or improved tests | `test/orchestrator-coverage` |

### Running Tests

```bash
python -m pytest tests/ -v
```

All tests should pass before submitting a pull request.

### Code Style

- Follow [PEP 8](https://peps.python.org/pep-0008/) style guidelines
- Use type hints for all function signatures
- Add docstrings to new functions and classes
- Keep lines under 100 characters
- Use `from __future__ import annotations` for modern type-hint syntax
- Format imports: stdlib → third-party → local (see existing files for examples)

### Making Changes

1. Create a new branch for your feature or fix:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes and add tests if applicable

3. Run tests to ensure nothing is broken:
   ```bash
   python -m pytest tests/ -v
   ```

4. If you changed any agent logic, run the full demo to verify:
   ```bash
   python -m src.app "test question" --docs ./data --mode full
   ```

5. Commit your changes with a clear message:
   ```bash
   git commit -m "Add feature: description of your change"
   ```

6. Push to your fork and open a Pull Request

### Pull Request Guidelines

- Reference any related issues (`Fixes #123`)
- Include a brief description of what changed and why
- Add screenshots or terminal output for UI changes
- Keep PRs focused — one feature or fix per PR
- Ensure all tests pass and no new warnings are introduced

## What to Contribute

We welcome contributions in the following areas:

- **New agents**: Add specialised agents for different use cases
- **Orchestration patterns**: Implement additional patterns (Handoff, Group Chat, Magentic)
- **Web UI enhancements**: Improve the browser-based interface, add visualisations
- **Documentation**: Improve README, add tutorials, fix typos
- **Bug fixes**: Report and fix issues
- **Tests**: Increase test coverage (especially for orchestrator and web UI)
- **Sample documents**: Add example data files for different domains
- **Model support**: Test and document additional Foundry Local model aliases

## Reporting Issues

- Use GitHub Issues to report bugs or request features
- Include steps to reproduce any bugs
- Provide your Python version, OS, and Foundry Local version
- For model-related issues, include the output of `foundry model list`

## Code of Conduct

This project follows the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).

## Questions?

- Open a GitHub Discussion for general questions
- Check existing issues before creating new ones

Thank you for contributing!
