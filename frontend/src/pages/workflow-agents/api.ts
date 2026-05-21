import { apiJson, apiPostJson } from '@/api/client'

export type AgentStep = {
  id: string
  step_key: string
  title: string
  tool_name: string
  status: string
  mutates_state: boolean
  approval_required: boolean
  risk_level: string
  confidence: number
  error_message?: string
  output_json?: Record<string, unknown>
}

export type AgentProposal = {
  id: string
  run_id: string
  step_id: string
  tool_name: string
  title: string
  status: string
  impact: string
  risk_level: string
  workflow_code?: string
  fascicolo_id?: string
}

export type AgentMetric = {
  baseline_minutes: number
  preview_minutes: number
  review_minutes: number
  correction_minutes: number
  saved_minutes: number
  saving_percentage: number
  target_80_met: boolean
  accepted_actions: number
  rejected_actions: number
}

export type AgentRun = {
  id: string
  workflow_code: string
  fascicolo_id?: string
  status: string
  created_by: string
  created_at: string
  risk_level: string
  confidence: number
  plan: {
    title: string
    description: string
    steps: AgentStep[]
    baseline_minutes: number
    expected_review_minutes: number
    expected_correction_minutes: number
    warnings?: string[]
  }
  proposals: AgentProposal[]
  metrics?: AgentMetric | null
  audit_hash?: string
}

export type WorkflowAgentSummary = {
  code: string
  title: string
  description: string
  risk_level: string
  baseline_minutes: number
}

export type WorkflowAgentMetrics = {
  run_count: number
  average_saving_percentage: number
  saved_minutes: number
  target_80_met: boolean
  accepted_actions: number
  rejected_actions: number
  top_workflows: Array<{ workflow_code: string; run_count: number; average_saving_percentage: number; saved_minutes: number }>
}

export type WorkflowAgentsHomePayload = {
  ok: boolean
  feature_flags: {
    enabled: boolean
    writeActions: boolean
    scheduledRuns: boolean
    homeRoute: boolean
    reviewQueueRoute: boolean
  }
  workflows: WorkflowAgentSummary[]
  latest_runs: AgentRun[]
  metrics: WorkflowAgentMetrics
  message?: string
}

const emptyMetrics: WorkflowAgentMetrics = {
  run_count: 0,
  average_saving_percentage: 0,
  saved_minutes: 0,
  target_80_met: false,
  accepted_actions: 0,
  rejected_actions: 0,
  top_workflows: [],
}

const emptyHome: WorkflowAgentsHomePayload = {
  ok: false,
  feature_flags: { enabled: false, writeActions: false, scheduledRuns: false, homeRoute: false, reviewQueueRoute: false },
  workflows: [],
  latest_runs: [],
  metrics: emptyMetrics,
}

export function fetchWorkflowAgentsHome(signal?: AbortSignal) {
  return apiJson('/api/v1/ui/workflow-agents', emptyHome, { signal })
}

export function previewWorkflowAgent(workflowCode: string, payload: Record<string, unknown> = {}) {
  return apiPostJson<{ ok: boolean; run: AgentRun | null; message?: string }>(
    '/api/v1/ui/workflow-agents/preview',
    { workflow_code: workflowCode, ...payload },
    { ok: false, run: null },
  )
}

export function fetchWorkflowAgentRun(runId: string, signal?: AbortSignal) {
  return apiJson<{ ok: boolean; run: AgentRun | null; message?: string }>(
    `/api/v1/ui/workflow-agents/runs/${encodeURIComponent(runId)}`,
    { ok: false, run: null },
    { signal },
  )
}

export function fetchWorkflowAgentApprovals(signal?: AbortSignal) {
  return apiJson<{ ok: boolean; approvals: AgentProposal[]; message?: string }>(
    '/api/v1/ui/workflow-agents/approvals',
    { ok: false, approvals: [] },
    { signal },
  )
}

export function approveWorkflowAgentRun(runId: string, stepIds: string[]) {
  return apiPostJson<{ ok: boolean; run: AgentRun | null; message?: string }>(
    `/api/v1/ui/workflow-agents/runs/${encodeURIComponent(runId)}/approve`,
    { approved_step_ids: stepIds },
    { ok: false, run: null },
  )
}

export function rejectWorkflowAgentRun(runId: string, stepIds: string[], reason = '') {
  return apiPostJson<{ ok: boolean; run: AgentRun | null; message?: string }>(
    `/api/v1/ui/workflow-agents/runs/${encodeURIComponent(runId)}/reject`,
    { rejected_step_ids: stepIds, reason },
    { ok: false, run: null },
  )
}

export function fetchWorkflowAgentMetrics(signal?: AbortSignal) {
  return apiJson<{ ok: boolean; metrics: WorkflowAgentMetrics }>(
    '/api/v1/ui/workflow-agents/metrics',
    { ok: false, metrics: emptyMetrics },
    { signal },
  )
}

