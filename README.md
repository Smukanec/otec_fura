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

## License

Otec Fura is released under the [MIT License](LICENSE).
