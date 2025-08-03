# Otec Fura

A simple FastAPI service providing contextual information from memory and knowledge base.

## Endpoints

- `POST /get_context` – returns memory, knowledge and embedding context for a query.
- `POST /crawl` – crawls a URL, stores its embedding and returns the character count.

## Authentication

Register via `POST /auth/register`. The account must be approved by an administrator
before an API key is issued. Once approved, obtain the API key using
`POST /auth/token`.

## Creating users via script

Administrators can create accounts directly using the provided helper script.
A typical invocation looks like:

```bash
./create_user.sh alice alice@example.com --approve
```

The final `--approve` flag is optional. When included, the user is marked as
approved immediately and can use the returned API key. Omit the flag to create
an unapproved account; in that case, set `"approved": true` manually in
`data/users.json` when ready to activate the user.

## Running tests

Install dependencies and execute:

```bash
pytest -q
```

## License

Otec Fura is released under the [MIT License](LICENSE).
