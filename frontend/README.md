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

You can also change the backend URL on the login page. The value is saved in browser `localStorage` as `apiBase`.

Login uses the backend `ADMIN_TOKEN`; the frontend verifies it by calling `/admin/dashboard`.
