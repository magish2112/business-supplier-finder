const STORAGE_KEY = "bizsf_api_key";

export function getApiKey(): string {
  return sessionStorage.getItem(STORAGE_KEY) || "";
}

export function setApiKey(k: string | null): void {
  if (k && String(k).trim()) {
    sessionStorage.setItem(STORAGE_KEY, String(k).trim());
  } else {
    sessionStorage.removeItem(STORAGE_KEY);
  }
}

export async function bizsfApiFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const options: RequestInit = { ...init };
  const headers = new Headers(options.headers);
  const key = getApiKey();
  if (key) {
    headers.set("X-API-Key", key);
  }
  options.headers = headers;

  let res = await fetch(input, options);
  if (res.status !== 401) {
    return res;
  }
  const msg =
    "Сервер требует API-ключ (переменная API_KEY). Введите ключ — он сохранится в sessionStorage этой вкладки:";
  const inputPrompt = typeof prompt === "function" ? prompt(msg) : null;
  if (inputPrompt && String(inputPrompt).trim()) {
    setApiKey(String(inputPrompt).trim());
    headers.set("X-API-Key", String(inputPrompt).trim());
    options.headers = headers;
    res = await fetch(input, options);
  }
  return res;
}

export function apiErrorMessage(j: unknown): string {
  if (!j || typeof j !== "object") return "";
  const err = (j as { error?: unknown }).error;
  if (typeof err === "string") return err;
  if (err && typeof err === "object" && "message" in err && typeof (err as { message: string }).message === "string") {
    return (err as { message: string }).message;
  }
  return "";
}
