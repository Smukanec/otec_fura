# Otec Fura

A simple FastAPI service providing contextual information from memory and knowledge base.

## Endpoints

- `POST /get_context` – returns memory, knowledge and embedding context for a query.
- `POST /crawl` – crawls a URL, stores its embedding and returns the character count.

## Authentication

Register via `POST /auth/register`. The account must be approved by an administrator
before an API key is issued. Once approved, obtain the API key using
`POST /auth/token`.

## Running tests

Install dependencies and execute:

```bash
pytest -q
```

## Dependency management

Project dependencies are declared in `pyproject.toml`. To keep
`requirements.txt` in sync, regenerate it whenever the dependency list
changes:

```bash
python scripts/sync_requirements.py
```

Tools such as [pip-tools](https://github.com/jazzband/pip-tools) can also
be used to compile a fully pinned `requirements.txt` if desired.

## License

Otec Fura is released under the [MIT License](LICENSE).
