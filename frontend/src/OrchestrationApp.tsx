import { useCallback, useMemo, useState } from "react";
import { apiErrorMessage, bizsfApiFetch } from "@/api/bizsfFetch";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Stepper, type StepDef } from "@/components/Stepper";
import type { RequestState, SupplierCard } from "@/types/orchestration";
import { cn } from "@/lib/utils";

const FLOW_STEPS: StepDef[] = [
  { id: 1, title: "Уточнение", description: "Ответы на вопросы модели" },
  { id: 2, title: "Получатели", description: "Выбор e-mail для рассылки" },
  { id: 3, title: "Подтверждение", description: "Согласие с локальным списком" },
  { id: 4, title: "Отправка", description: "SMTP / пропуск" },
];

function backendStepToIndex(step: string): number {
  if (step === "AWAIT_CLARIFICATION") return 0;
  if (step === "AWAIT_RECIPIENT_SELECTION") return 1;
  if (step === "AWAIT_USER_LOCAL_CONFIRM") return 2;
  if (step === "AWAIT_SEND_CONFIRM") return 3;
  if (step === "DONE") return 4;
  if (step === "PROPOSE") return 1;
  return 0;
}

export default function OrchestrationApp() {
  const [query, setQuery] = useState("");
  const [message, setMessage] = useState("");
  const [city, setCity] = useState("");
  const [activityDirection, setActivityDirection] = useState("");
  const [state, setState] = useState<RequestState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [clarifyAnswers, setClarifyAnswers] = useState<Record<string, string>>({});
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const stepIndex = useMemo(() => (state ? backendStepToIndex(state.step) : 0), [state]);

  const applyFromResponse = useCallback(async (res: Response) => {
    const j = (await res.json()) as RequestState & { error?: unknown };
    if (!res.ok) {
      throw new Error(apiErrorMessage(j) || `HTTP ${res.status}`);
    }
    if ((j as { _error?: boolean })._error) {
      throw new Error((j as { message?: string }).message || "Ошибка состояния");
    }
    setState(j as RequestState);
    setClarifyAnswers({});
    setSelectedIds(new Set());
  }, []);

  const createRequest = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const q = query.trim();
    const m = message.trim();
    if (!q && !m) {
      setError("Укажите query и/или message.");
      return;
    }
    try {
      const body: Record<string, string> = {
        query: q,
        city: city.trim(),
        activity_direction: activityDirection.trim(),
      };
      if (m) body.message = m;
      const res = await bizsfApiFetch("/api/v2/requests", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      await applyFromResponse(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const postAction = async (url: string, body: object) => {
    setError(null);
    try {
      const res = await bizsfApiFetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      await applyFromResponse(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const submitClarify = () => {
    if (!state?.request_id) return;
    postAction(`/api/v2/requests/${encodeURIComponent(state.request_id)}/clarify`, { answers: clarifyAnswers });
  };

  const submitRecipients = () => {
    if (!state?.request_id || selectedIds.size === 0) {
      setError("Выберите хотя бы одного получателя.");
      return;
    }
    postAction(`/api/v2/requests/${encodeURIComponent(state.request_id)}/recipients`, {
      supplier_ids: [...selectedIds],
    });
  };

  const supplierList: SupplierCard[] = useMemo(() => {
    if (!state) return [];
    if (state.step === "AWAIT_RECIPIENT_SELECTION" && state.recipient_candidates?.length) {
      return state.recipient_candidates;
    }
    return state.suppliers || [];
  }, [state]);

  const toggleRecipient = (id: string) => {
    setSelectedIds((prev) => {
      const n = new Set(prev);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50/30 to-indigo-50/40 p-4 md:p-8 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950">
      <div className="mx-auto max-w-3xl space-y-6">
        <header className="space-y-2 text-center md:text-left">
          <h1 className="text-3xl font-bold tracking-tight">Оркестрация заявки</h1>
          <p className="text-muted-foreground text-sm">
            React + Vite + Tailwind v4. API: <code className="rounded bg-muted px-1">/api/v2/*</code>
          </p>
        </header>

        <Card>
          <CardHeader>
            <CardTitle>Новая заявка</CardTitle>
            <CardDescription>Хотя бы одно из полей: запрос (query) или свободное сообщение (message).</CardDescription>
          </CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={createRequest}>
              <div className="space-y-2">
                <label className="text-sm font-medium" htmlFor="q">
                  Query
                </label>
                <input
                  id="q"
                  className="border-input bg-background ring-offset-background focus-visible:ring-ring flex h-10 w-full rounded-md border px-3 text-sm focus-visible:outline-none focus-visible:ring-2"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Например: сантехника оптом"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium" htmlFor="msg">
                  Message
                </label>
                <textarea
                  id="msg"
                  rows={3}
                  className="border-input bg-background focus-visible:ring-ring flex w-full rounded-md border px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2"
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder="Свободный текст — извлечёт LLM"
                />
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <label className="text-sm font-medium" htmlFor="city">
                    Город
                  </label>
                  <input
                    id="city"
                    className="border-input bg-background h-10 w-full rounded-md border px-3 text-sm"
                    value={city}
                    onChange={(e) => setCity(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium" htmlFor="dir">
                    Направление
                  </label>
                  <input
                    id="dir"
                    className="border-input bg-background h-10 w-full rounded-md border px-3 text-sm"
                    value={activityDirection}
                    onChange={(e) => setActivityDirection(e.target.value)}
                  />
                </div>
              </div>
              <Button type="submit">Запустить</Button>
            </form>
          </CardContent>
        </Card>

        {error && (
          <div className="border-destructive/50 bg-destructive/10 text-destructive rounded-lg border px-4 py-3 text-sm">{error}</div>
        )}

        {state && (
          <Card>
            <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-2">
              <div>
                <CardTitle className="text-lg">Заявка</CardTitle>
                <CardDescription className="font-mono text-xs">{state.request_id}</CardDescription>
              </div>
              <Badge variant="secondary">{state.step}</Badge>
            </CardHeader>
            <CardContent className="space-y-6">
              <p className="text-muted-foreground text-sm">{state.message}</p>

              <div className="overflow-x-auto pb-2">
                <Stepper
                  steps={FLOW_STEPS}
                  currentStep={Math.min(stepIndex, FLOW_STEPS.length - 1)}
                  onStepChange={() => undefined}
                />
              </div>

              {state.step === "AWAIT_CLARIFICATION" && state.clarification_questions && state.clarification_questions.length > 0 && (
                <div className="space-y-3 rounded-lg border border-border bg-muted/20 p-4">
                  <h3 className="font-semibold">Уточнения</h3>
                  {state.clarification_questions.map((q, idx) => {
                    const key = `q${idx}`;
                    return (
                      <div key={key} className="space-y-1">
                        <label className="text-sm">{q}</label>
                        <input
                          className="border-input h-9 w-full rounded-md border bg-background px-2 text-sm"
                          value={clarifyAnswers[key] || ""}
                          onChange={(e) => setClarifyAnswers((a) => ({ ...a, [key]: e.target.value }))}
                        />
                      </div>
                    );
                  })}
                  <Button onClick={submitClarify}>Отправить ответы</Button>
                </div>
              )}

              {supplierList.length > 0 && (
                <div>
                  <h3 className="mb-2 font-semibold">Поставщики</h3>
                  <ul className="space-y-2">
                    {supplierList.map((s, i) => {
                      const name = s.name || s.title || `Поставщик ${i + 1}`;
                      const id = s.id ? String(s.id) : "";
                      const pick = state.step === "AWAIT_RECIPIENT_SELECTION" && id;
                      return (
                        <li
                          key={id || `${name}-${i}`}
                          className={cn(
                            "rounded-lg border border-border bg-card/50 p-3 text-sm",
                            pick && "cursor-pointer hover:bg-accent/30",
                            pick && id && selectedIds.has(id) && "ring-2 ring-primary"
                          )}
                          onClick={() => pick && id && toggleRecipient(id)}
                        >
                          <div className="font-medium">{name}</div>
                          <div className="text-muted-foreground mt-1 space-x-2 text-xs">
                            {s.email && <span>email: {s.email}</span>}
                            {s.city && <span>город: {s.city}</span>}
                            {s.website && <span>сайт: {s.website}</span>}
                          </div>
                          {pick && <p className="text-muted-foreground mt-2 text-xs">Нажмите карточку, чтобы отметить</p>}
                        </li>
                      );
                    })}
                  </ul>
                </div>
              )}

              {state.step === "AWAIT_RECIPIENT_SELECTION" && (
                <Button disabled={selectedIds.size === 0} onClick={submitRecipients}>
                  Подтвердить выбранных получателей
                </Button>
              )}

              {state.step === "AWAIT_SEND_CONFIRM" && state.email_draft && (
                <div className="space-y-2 rounded-lg border bg-muted/10 p-4">
                  <h3 className="font-semibold">Черновик письма</h3>
                  <p className="text-sm">
                    <span className="text-muted-foreground">Тема: </span>
                    {state.email_draft.subject}
                  </p>
                  <pre className="bg-background max-h-48 overflow-auto rounded border p-3 text-xs whitespace-pre-wrap">
                    {state.email_draft.body_preview ?? state.email_draft.body ?? ""}
                  </pre>
                  <ul className="text-muted-foreground text-xs">
                    {(state.email_draft.recipients || []).map((r) => (
                      <li key={r}>{r}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="flex flex-wrap gap-2">
                <Button
                  variant="default"
                  disabled={state.step !== "AWAIT_USER_LOCAL_CONFIRM"}
                  onClick={() =>
                    state.request_id &&
                    postAction(`/api/v2/requests/${encodeURIComponent(state.request_id)}/confirm-local`, { send: true })
                  }
                >
                  Подтвердить отправку (локально)
                </Button>
                <Button
                  variant="outline"
                  disabled={state.step !== "AWAIT_USER_LOCAL_CONFIRM"}
                  onClick={() =>
                    state.request_id &&
                    postAction(`/api/v2/requests/${encodeURIComponent(state.request_id)}/confirm-local`, { send: false })
                  }
                >
                  Отказаться
                </Button>
              </div>

              <div className="flex flex-wrap gap-2">
                <Button
                  disabled={state.step !== "AWAIT_SEND_CONFIRM"}
                  onClick={() =>
                    state.request_id &&
                    postAction(`/api/v2/requests/${encodeURIComponent(state.request_id)}/send-emails`, { execute: true })
                  }
                >
                  Выполнить SMTP
                </Button>
                <Button
                  variant="secondary"
                  disabled={state.step !== "AWAIT_SEND_CONFIRM"}
                  onClick={() =>
                    state.request_id &&
                    postAction(`/api/v2/requests/${encodeURIComponent(state.request_id)}/send-emails`, { execute: false })
                  }
                >
                  Не отправлять
                </Button>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
