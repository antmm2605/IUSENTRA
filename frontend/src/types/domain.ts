export type Tone = "neutral" | "primary" | "secondary" | "success" | "warning" | "danger" | "info" | "gold";

export interface DashboardStats {
  todayAppointments: number;
  urgentDeadlines: number;
  openMatters: number;
  unpaidAmount: string;
  documentsToReview: number;
}

export interface DashboardPayload {
  source: string;
  generated_at: string;
  stats: DashboardStats;
  actions: NextAction[];
  fascicoli: FascicoloSummary[];
  warning?: string;
}

export interface NextAction {
  id: string;
  title: string;
  description: string;
  tone: Tone;
  href?: string;
}

export interface FascicoloSummary {
  id: string;
  title: string;
  rg: string;
  office: string;
  status: string;
  client: string;
  counterparty: string;
  nextHearing?: string;
  riskScore: number;
}

export interface DocumentItem {
  id: string;
  title: string;
  type: string;
  status: "acquisito" | "da_acquisire" | "da_validare" | "firmato";
  source: "studio" | "pst" | "pdp" | "pat" | "ptt";
  date: string;
}

export interface LexMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  createdAt: string;
}
