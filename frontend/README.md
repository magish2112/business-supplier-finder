# React UI (Vite + TypeScript + Tailwind v4)

Сборка попадает в `static/orch-app/` — страница Flask: **`/flow-react`**.

## Разработка

Терминал 1 — бэкенд:

```bash
cd ..
python web_app.py
```

Терминал 2 — Vite (прокси `/api` → `http://127.0.0.1:5000`):

```bash
npm install
npm run dev
```

Откройте `http://localhost:5173`.

## Продакшен-сборка

```bash
npm install
npm run build
```

Затем в корне проекта запустите Flask и откройте `http://localhost:5000/flow-react`.

## Зависимости

Соответствуют интеграции shadcn-подобных примитивов: `lucide-react`, `@radix-ui/react-slot`, `class-variance-authority`, `clsx`, `tailwind-merge`.
