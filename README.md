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
Run the script and follow the prompts:

```bash
./create_user.sh
```

You will be asked for a username, email and password. Pass `--approve` to mark
the user as approved immediately; otherwise the account will remain pending and
you must edit `data/users.json` to set `"approved": true` when ready to activate
the user.

## Running tests

Install dependencies and execute:

```bash
pytest -q
```

## License

Otec Fura is released under the [MIT License](LICENSE).
