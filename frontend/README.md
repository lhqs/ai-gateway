# LHQS AI Gateway Frontend

## Local configuration

If the backend runs on port `8004`, use:

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

The default `.env.example` already sets:

```env
VITE_API_BASE=http://localhost:8004
```

`VITE_API_BASE` is the backend URL used by the admin UI. API key usage snippets
show the current site origin plus `/v1`, so production nginx should expose the
gateway under the same domain, for example `https://gateway.example.com/v1`.

Login uses the backend `ADMIN_TOKEN`; the frontend verifies it by calling `/admin/dashboard`.
