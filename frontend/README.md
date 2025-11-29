# Frontend (Vite + React)

Minimal frontend for LegalOntoSystem.

Install and run:

```powershell
cd frontend
npm install
npm run dev
```

- Open `http://localhost:5173` (Vite default) and usa los botones para cargar leyes desde el backend.
- El frontend espera que la API Flask esté proxied o accesible en el mismo host; para desarrollo con CORS activo en backend se puede ajustar `axios` base URL.

Extensiones sugeridas:
- Añadir detalle al hacer clic en nodos, soporte para artículos y enlaces entre normas.
