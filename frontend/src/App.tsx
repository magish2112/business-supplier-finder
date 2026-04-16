import { useState } from "react";
import OrchestrationApp from "@/OrchestrationApp";
import ComponentShowcase from "@/ComponentShowcase";
import { Button } from "@/components/ui/button";

/**
 * Корневое приложение: рабочий экран оркестрации + демо UI из исходного App.tsx.
 */
export default function App() {
  const [view, setView] = useState<"orch" | "showcase">("orch");

  return (
    <div className="min-h-screen">
      <nav className="border-border bg-card/80 supports-[backdrop-filter]:bg-card/60 sticky top-0 z-10 flex flex-wrap items-center gap-2 border-b px-4 py-3 backdrop-blur">
        <span className="text-muted-foreground mr-2 text-sm font-medium">Режим:</span>
        <Button variant={view === "orch" ? "default" : "outline"} size="sm" onClick={() => setView("orch")}>
          Оркестрация
        </Button>
        <Button variant={view === "showcase" ? "default" : "outline"} size="sm" onClick={() => setView("showcase")}>
          UI-демо
        </Button>
        <a
          href="/flow"
          className="text-muted-foreground hover:text-foreground ml-auto text-xs underline-offset-4 hover:underline"
        >
          Классический /flow
        </a>
      </nav>
      {view === "orch" ? <OrchestrationApp /> : <ComponentShowcase />}
    </div>
  );
}
