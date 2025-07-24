# Otec Fura

A simple FastAPI service providing contextual information from memory and knowledge base.

## Endpoints

- `POST /get_context` – returns memory, knowledge and embedding context for a query.
- `POST /crawl` – crawls a URL, stores its embedding and returns the character count.

## Running tests

Install dependencies and execute:

```bash
pytest -q
```

## License

Otec Fura is released under the [MIT License](LICENSE).
