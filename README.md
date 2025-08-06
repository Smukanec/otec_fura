# Otec Fura

A simple FastAPI service providing contextual information from memory and knowledge base.

## Endpoints

- `POST /get_context` – returns memory, knowledge and embedding context for a query.
- `POST /crawl` – crawls a URL, stores its embedding and returns the character count.

## Authentication

Register via `POST /auth/register` using a JSON body with `username`, `password`
and `email`. The account must be approved by an administrator before an API key is
issued. Once approved, obtain the API key with `POST /auth/token` by providing the
same `username` and `password`.

## Client communication requirements

All requests (except those under `/auth`) require an API key and use JSON payloads.

1. **Registration** – send `POST /auth/register` with the user's credentials and
   wait for administrator approval.
2. **Login** – after approval, call `POST /auth/token` with the login credentials
   to receive an `api_key`.
3. **Authenticated calls** – include the API key in the header of every other
   request:

   ```bash
   Authorization: Bearer <api_key>
   ```

   Example: fetching context for a query

   ```bash
   curl -X POST https://<host>/get_context \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"query": "Hello"}'
   ```

   Without a valid and approved API key the service returns `401` or `403` errors.

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
