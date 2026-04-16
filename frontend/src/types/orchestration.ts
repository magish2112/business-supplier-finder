export type OrchestrationStep =
  | "INTAKE"
  | "LOCAL_MATCH"
  | "AWAIT_CLARIFICATION"
  | "AWAIT_RECIPIENT_SELECTION"
  | "AWAIT_USER_LOCAL_CONFIRM"
  | "WEB_DISCOVERY"
  | "PROPOSE"
  | "AWAIT_SEND_CONFIRM"
  | "DONE";

export interface EmailDraft {
  subject?: string;
  body_preview?: string;
  body?: string;
  recipients?: string[];
}

export interface SupplierCard {
  id?: string;
  name?: string;
  title?: string;
  website?: string;
  email?: string;
  city?: string;
  phone?: string;
  note?: string;
}

export interface RequestState {
  request_id: string;
  step: OrchestrationStep | string;
  message?: string;
  suppliers?: SupplierCard[];
  recipient_candidates?: SupplierCard[];
  clarification_questions?: string[];
  email_draft?: EmailDraft;
  structured?: Record<string, unknown>;
  _error?: boolean;
}
