/**
 * Демонстрация компонентов из исходного App.tsx (степпер, карточки, градиенты).
 * Не используется в прод-потоке — для проверки дизайн-системы.
 */
import React, { useState } from "react";
import { ChevronRight, ChevronLeft, Sparkles, Zap, Shield, Rocket } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Stepper, type StepDef } from "@/components/Stepper";

interface ModernCardProps {
  title: string;
  description: string;
  icon: React.ReactNode;
  variant: "default" | "elevated" | "glass";
  gradient?: string;
}

const ModernCard: React.FC<ModernCardProps> = ({ title, description, icon, variant, gradient }) => {
  const baseClasses = "group relative cursor-pointer overflow-hidden transition-all duration-300";
  const variantClasses = {
    default: "border-border hover:-translate-y-1 hover:shadow-lg",
    elevated: "border-0 shadow-xl hover:-translate-y-2 hover:shadow-2xl",
    glass: "border-white/20 bg-background/40 backdrop-blur-xl hover:border-white/40 hover:bg-background/60",
  };
  return (
    <Card className={`${baseClasses} ${variantClasses[variant]}`}>
      {gradient && (
        <div className={`absolute inset-0 opacity-0 transition-opacity duration-300 group-hover:opacity-10 ${gradient}`} />
      )}
      <CardHeader>
        <div className="flex items-start justify-between">
          <div className="rounded-xl bg-gradient-to-br from-blue-500/10 to-indigo-600/10 p-3 transition-all duration-300 group-hover:from-blue-500/20 group-hover:to-indigo-600/20">
            {icon}
          </div>
          <Badge variant="secondary" className="text-xs">
            Новое
          </Badge>
        </div>
        <CardTitle className="mt-4 transition-colors group-hover:text-blue-600">{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex items-center text-sm font-medium text-blue-600 transition-all group-hover:gap-2">
          Узнать больше
          <ChevronRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
        </div>
      </CardContent>
    </Card>
  );
};

const demoSteps: StepDef[] = [
  { id: 1, title: "Шаг 1", description: "Начало работы" },
  { id: 2, title: "Шаг 2", description: "Настройка" },
  { id: 3, title: "Шаг 3", description: "Проверка" },
  { id: 4, title: "Завершено", description: "Готово к запуску" },
];

export default function ComponentShowcase() {
  const [currentStep, setCurrentStep] = useState(0);
  const [verticalStep, setVerticalStep] = useState(0);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50 p-4 sm:p-8 dark:from-slate-950 dark:via-blue-950 dark:to-indigo-950">
      <div className="mx-auto max-w-7xl space-y-12">
        <div className="space-y-4 py-8 text-center">
          <h1 className="bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-4xl font-bold text-transparent sm:text-5xl">
            Современная UI-библиотека
          </h1>
          <p className="text-muted-foreground mx-auto max-w-2xl text-lg">
            Карточки, степпер и градиенты — те же примитивы, что используются в экране оркестрации.
          </p>
        </div>

        <section className="space-y-6">
          <div className="space-y-2">
            <h2 className="text-2xl font-bold text-foreground">Горизонтальный степпер</h2>
            <p className="text-muted-foreground">Индикация прогресса</p>
          </div>
          <Card className="border-border/50 bg-background/95 p-6 shadow-xl backdrop-blur-sm sm:p-8">
            <Stepper steps={demoSteps} currentStep={currentStep} onStepChange={setCurrentStep} orientation="horizontal" />
            <div className="mt-8 rounded-xl border border-border/50 bg-gradient-to-br from-blue-500/5 to-indigo-600/5 p-6">
              <h3 className="mb-2 text-lg font-semibold">{demoSteps[currentStep].title}</h3>
              <p className="text-muted-foreground mb-4">{demoSteps[currentStep].description}</p>
              <div className="flex flex-wrap gap-3">
                <Button variant="outline" className="gap-2" disabled={currentStep === 0} onClick={() => setCurrentStep((s) => Math.max(0, s - 1))}>
                  <ChevronLeft className="h-4 w-4" />
                  Назад
                </Button>
                <Button
                  className="gap-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700"
                  disabled={currentStep === demoSteps.length - 1}
                  onClick={() => setCurrentStep((s) => Math.min(demoSteps.length - 1, s + 1))}
                >
                  {currentStep === demoSteps.length - 1 ? "Завершить" : "Далее"}
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </Card>
        </section>

        <section className="grid gap-8 lg:grid-cols-2">
          <div className="space-y-6">
            <h2 className="text-2xl font-bold">Вертикальный степпер</h2>
            <Card className="border-border/50 bg-background/95 p-6 shadow-xl backdrop-blur-sm">
              <Stepper steps={demoSteps} currentStep={verticalStep} onStepChange={setVerticalStep} orientation="vertical" />
              <div className="mt-6 flex gap-3">
                <Button variant="outline" size="sm" disabled={verticalStep === 0} onClick={() => setVerticalStep((s) => s - 1)}>
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <Button
                  size="sm"
                  className="flex-1 bg-gradient-to-r from-blue-600 to-indigo-600"
                  disabled={verticalStep === demoSteps.length - 1}
                  onClick={() => setVerticalStep((s) => s + 1)}
                >
                  {verticalStep === demoSteps.length - 1 ? "Завершить" : "Далее"}
                </Button>
              </div>
            </Card>
          </div>
          <Card className="border-border/50 bg-background/95 p-6 shadow-xl backdrop-blur-sm">
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">Общий прогресс</span>
                <span className="text-muted-foreground text-sm">
                  {Math.round(((currentStep + 1) / demoSteps.length) * 100)}%
                </span>
              </div>
              <div className="bg-muted h-3 overflow-hidden rounded-full">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-blue-500 to-indigo-600 transition-all duration-500 ease-out"
                  style={{ width: `${((currentStep + 1) / demoSteps.length) * 100}%` }}
                />
              </div>
            </div>
          </Card>
        </section>

        <section className="space-y-6">
          <h2 className="text-2xl font-bold">Варианты карточек</h2>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            <ModernCard
              title="Стандартная карточка"
              description="Тонкие границы и лёгкий подъём при наведении"
              icon={<Sparkles className="h-6 w-6 text-blue-600" />}
              variant="default"
              gradient="bg-gradient-to-br from-blue-500 to-indigo-600"
            />
            <ModernCard
              title="Приподнятая"
              description="Тени для акцента"
              icon={<Zap className="h-6 w-6 text-amber-600" />}
              variant="elevated"
              gradient="bg-gradient-to-br from-amber-500 to-orange-600"
            />
            <ModernCard
              title="Стекло"
              description="Blur и прозрачность"
              icon={<Shield className="h-6 w-6 text-emerald-600" />}
              variant="glass"
              gradient="bg-gradient-to-br from-emerald-500 to-teal-600"
            />
          </div>
        </section>

        <section className="relative overflow-hidden rounded-2xl border border-white/20 bg-gradient-to-br from-white/40 to-white/10 p-8 shadow-2xl backdrop-blur-2xl sm:p-12 dark:from-slate-800/40 dark:to-slate-900/10">
          <div className="absolute inset-0 bg-gradient-to-br from-blue-500/20 via-purple-500/20 to-pink-500/20" />
          <div className="relative z-10 space-y-6">
            <div className="inline-block rounded-full border border-white/20 bg-white/30 px-4 py-2 backdrop-blur-sm dark:bg-slate-800/30">
              <span className="text-sm font-medium">Премиум-блок</span>
            </div>
            <h3 className="text-3xl font-bold sm:text-4xl">
              Стекломорфизм
              <br />
              <span className="bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">2025</span>
            </h3>
            <div className="flex flex-wrap gap-3">
              <Button className="border border-white/20 bg-white/20 text-foreground backdrop-blur-sm hover:bg-white/30">
                Начать
              </Button>
              <Button variant="outline" className="border-white/20 bg-white/10 backdrop-blur-sm">
                Подробнее
              </Button>
            </div>
          </div>
        </section>

        <div className="flex justify-center pb-8">
          <div className="inline-flex items-center gap-2 rounded-full border border-blue-500/20 bg-gradient-to-r from-blue-500/10 to-indigo-600/10 px-4 py-2">
            <Rocket className="h-4 w-4 text-blue-600" />
            <span className="text-sm font-medium">Готово к продакшену</span>
          </div>
        </div>
      </div>
    </div>
  );
}
