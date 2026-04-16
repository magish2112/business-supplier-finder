import React from "react";
import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

export interface StepDef {
  id: number;
  title: string;
  description: string;
}

interface StepperProps {
  steps: StepDef[];
  currentStep: number;
  onStepChange: (step: number) => void;
  orientation?: "horizontal" | "vertical";
}

export const Stepper: React.FC<StepperProps> = ({
  steps,
  currentStep,
  onStepChange,
  orientation = "horizontal",
}) => {
  const isHorizontal = orientation === "horizontal";
  return (
    <div className={cn("flex gap-2", isHorizontal ? "flex-row items-center" : "flex-col")}>
      {steps.map((step, index) => {
        const isCompleted = index < currentStep;
        const isCurrent = index === currentStep;
        const isLast = index === steps.length - 1;
        return (
          <React.Fragment key={step.id}>
            <div
              className={cn(
                "flex gap-3",
                isHorizontal ? "flex-col items-center" : "flex-row items-start",
                isCurrent ? "flex-1" : ""
              )}
            >
              <div className="flex flex-col items-center gap-2">
                <button
                  type="button"
                  onClick={() => onStepChange(index)}
                  className={cn(
                    "relative flex h-12 w-12 items-center justify-center rounded-full transition-all duration-300",
                    isCompleted
                      ? "bg-gradient-to-br from-green-500 to-emerald-600 text-white shadow-lg shadow-green-500/30"
                      : isCurrent
                        ? "scale-110 bg-gradient-to-br from-blue-500 to-indigo-600 text-white shadow-lg shadow-blue-500/30"
                        : "bg-muted text-muted-foreground hover:bg-muted/80"
                  )}
                >
                  {isCompleted ? <Check className="h-6 w-6" /> : <span className="text-sm font-semibold">{index + 1}</span>}
                  {isCurrent && (
                    <span className="absolute -inset-1 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 opacity-30 animate-pulse" />
                  )}
                </button>
              </div>
              <div className={cn(isHorizontal ? "text-center" : "flex-1", "transition-all duration-300")}>
                <p
                  className={cn(
                    "text-sm font-semibold transition-colors",
                    isCurrent ? "text-foreground" : "text-muted-foreground"
                  )}
                >
                  {step.title}
                </p>
                <p className="mt-1 hidden text-xs text-muted-foreground sm:block">{step.description}</p>
              </div>
            </div>
            {!isLast && (
              <div
                className={cn(
                  "transition-all duration-500",
                  isHorizontal ? "h-0.5 min-w-8 flex-1" : "ml-6 h-12 w-0.5",
                  isCompleted ? "bg-gradient-to-r from-green-500 to-emerald-600" : "bg-border"
                )}
              />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}
