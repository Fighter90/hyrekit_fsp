# HyreKit — фронтенд

React 19 + Vite + TypeScript, react-router 6, lucide-react, чистый CSS (`src/styles/*`).
Фирменный стиль ФСП: JetBrains Mono (основной) и TDAText (акцентный), оба под SIL OFL — см. `public/fonts/OFL-*.txt`.

```bash
npm install
npm run dev      # http://localhost:5173, /api и /health проксируются на http://localhost:8000
npm run build    # tsc -b && vite build
npm test         # vitest
npm run lint
```

Структура:

- `src/api/types.ts` — типы контракта `docs/spec/api.md`; `src/api/client.ts` — клиент (метод на каждый эндпоинт, Bearer + авто-refresh).
- `src/pages/public|auth|candidate|employer` — страницы; кабинет выбирается по роли пользователя.
- `src/components/ui` — общие компоненты; `components/assessment` — опрос, прохождение теста, результат; `components/employer` — подборка, приглашение, тест под вакансию.
- `src/lib` — чистая логика (форматирование, тест, валидация вакансии), покрыта тестами в `src/test`.

В проде статику отдаёт nginx (`nginx.conf`): SPA-fallback и прокси `/api` → `app:8000`.
