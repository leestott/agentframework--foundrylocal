# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please report it responsibly.

### How to Report

1. **Do NOT** open a public GitHub issue for security vulnerabilities
2. Email the maintainers directly or use GitHub's private vulnerability reporting feature
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Any suggested fixes (optional)

### What to Expect

- Acknowledgment of your report within 48 hours
- Regular updates on the progress of the fix
- Credit in the security advisory (unless you prefer to remain anonymous)

## Security Considerations for This Project

### Local-First Design

This demo is designed to run entirely on your local machine:

- **No cloud API keys required** — All inference happens via Foundry Local
- **Data stays on-device** — Documents in the `data/` folder are never sent to external services
- **No network calls during inference** — After initial model download, the app works offline
- **Web UI binds to localhost** — The Flask web server runs on `127.0.0.1` by default and is not exposed to the network

### Model Supply Chain Security

- Models are downloaded exclusively from Microsoft's official Foundry Local catalog
- Verify model provenance using `foundry model list` to see official model IDs and sources
- Models are cached locally in the Foundry Local cache directory
- Do not load models from untrusted sources or manually override model paths with unverified files
- You can use trusted Hugging Face models using custom models see https://techcommunity.microsoft.com/blog/educatordeveloperblog/how-to-use-custom-models-with-foundry-local-a-beginners-guide/4428857 

### Web UI Security

- The web UI (`web.py`) is intended for **local development only** — do not deploy it to production it current has NO authentication, CSRF protection, and rate limiting
- The `/api/run` endpoint executes agent workflows — ensure it is not exposed to untrusted networks
- Input sanitisation is applied but the application is not hardened for adversarial use this is a demo only.

### Environment Variables NOT INCLUDED OR REQUIRED

- The `.env` file may contain configuration settings
- Never commit `.env` files with sensitive data to version control
- Use `.env.example` as a template

### Dependencies

- Keep dependencies updated: `pip install --upgrade -r requirements.txt`
- Review `pyproject.toml` for pinned versions
- Run `pip audit` periodically to check for known vulnerabilities

## Third-Party Dependencies

This project depends on:

- [foundry-local-sdk](https://pypi.org/project/foundry-local-sdk/) — Microsoft Foundry Local SDK
- [agent-framework-core](https://pypi.org/project/agent-framework-core/) — Microsoft Agent Framework
- [openai](https://pypi.org/project/openai/) — OpenAI Python SDK (used for the OpenAI-compatible API)

Report vulnerabilities in these dependencies to their respective maintainers.

## References

- [Foundry Local Security](https://github.com/microsoft/Foundry-Local/security)
