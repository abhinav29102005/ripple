import { z } from 'zod';

export const HealthResponseSchema = z.object({
  status: z.string(),
  graphs: z.array(z.string()),
  llm_mode: z.string().optional(),
});

export const TaskSchema = z.object({
  id: z.string(),
  key: z.string(),
  type: z.string(),
  status: z.enum(['queued', 'claimed', 'done', 'failed']),
  priority: z.number().optional().default(1),
  created: z.number().optional().default(0),
  lease_until: z.number().optional().default(0),
  attempts: z.number().optional().default(0),
  claimed_by: z.string().nullable().optional(),
  dependencies: z.array(z.string()).optional().default([]),
});

export const TasksResponseSchema = z.object({
  tasks: z.array(TaskSchema),
});

export const AgentSchema = z.object({
  id: z.string(),
  role: z.string(),
  started: z.number().optional(),
  heartbeat: z.number().optional(),
  task_type: z.string().optional().default(''),
  status: z.string().optional().default('active'),
  current_task_key: z.string().nullable().optional(),
});

export const AgentsResponseSchema = z.object({
  agents: z.array(AgentSchema),
});

export const GraphNodeSchema = z.object({
  id: z.string(),
  label: z.enum(['Retraction', 'Trial', 'Review', 'Guideline', 'Decision', 'Committee', 'Person']),
  title: z.string().optional(),
  status: z.string().optional(),
  reason: z.string().optional(),
  reason_category: z.string().optional(),
  committee: z.string().optional(),
  notify: z.array(z.string()).optional().default([]),
  yi: z.number().optional(),
  sei: z.number().optional(),
  hemisphere: z.string().optional(),
  role: z.string().optional(),
});

export const GraphEdgeSchema = z.object({
  source: z.string(),
  target: z.string(),
  type: z.string(),
  yi: z.number().optional(),
  sei: z.number().optional(),
  weight: z.number().optional(),
});

export const BlastResponseSchema = z.object({
  retraction_id: z.string(),
  nodes: z.array(GraphNodeSchema),
  edges: z.array(GraphEdgeSchema),
});

export const AppliedRuleSchema = z.object({
  id: z.string().optional(),
  rule_id: z.string().optional(),
  feature: z.string().optional(),
  value: z.string().optional(),
  delta: z.number(),
  support: z.number().optional(),
  hit_rate: z.number().optional(),
  description: z.string().optional(),
});

export const AlertSchema = z.object({
  review_id: z.string(),
  title: z.string(),
  base: z.number(),
  score: z.number(),
  delta: z.number(),
  raw_delta: z.number().optional().default(0),
  reason_category: z.string().optional().default('unknown'),
  weight_share: z.number().optional().default(0),
  weight_bucket: z.string().optional().default('low'),
  flips: z.boolean().optional().default(false),
  guidelines: z.array(z.string()).optional().default([]),
  applied_rules: z.array(AppliedRuleSchema).optional().default([]),
  safety_floor_active: z.boolean().optional().default(false),
  safety_floor_triggered: z.boolean().optional().default(false),
  rank: z.number(),
});

export const RankingsResponseSchema = z.object({
  tenant: z.string(),
  retraction_id: z.string(),
  ranking_id: z.string(),
  ranked_alerts: z.array(AlertSchema),
});

export const RuleExplanationSchema = z.object({
  rule_id: z.string(),
  feature: z.string(),
  value: z.string(),
  delta: z.number(),
  description: z.string(),
  learned_from_episodes: z.array(z.string()).optional().default([]),
});

export const ExplainResponseSchema = z.object({
  ranking_id: z.string().optional(),
  review_id: z.string(),
  rank: z.number(),
  base_score: z.number(),
  final_score: z.number(),
  rules_applied: z.array(RuleExplanationSchema).optional().default([]),
});

export const EpisodeSchema = z.object({
  id: z.string(),
  ts: z.number(),
  kind: z.string(),
  reason: z.string().optional().default(''),
  weight_bucket: z.string().optional().default(''),
  flips: z.union([z.boolean(), z.string()]).optional().default(false),
  ext_review: z.string().optional().default(''),
  ext_retraction: z.string().optional().default(''),
  notes: z.string().optional().default(''),
});

export const ActiveRuleSchema = z.object({
  id: z.string(),
  feature: z.string(),
  value: z.string(),
  delta: z.number(),
  support: z.number(),
  hit_rate: z.number(),
  description: z.string(),
  status: z.string().optional().default('active'),
  episode_ids: z.array(z.string()).optional().default([]),
});

export const FactSchema = z.object({
  id: z.string(),
  key: z.string(),
  value: z.string(),
  valid_from: z.number(),
  valid_to: z.number().nullable().optional(),
  supersedes_id: z.string().nullable().optional(),
});

export const MemoryResponseSchema = z.object({
  tenant: z.string(),
  episodes: z.array(EpisodeSchema),
  active_rules: z.array(ActiveRuleSchema),
  facts: z.array(FactSchema),
});

export const ChatMessageSchema = z.object({
  id: z.string(),
  seq: z.number(),
  role: z.enum(['user', 'analyst', 'system']),
  text: z.string(),
  ts: z.number(),
});

export const ChatResponseSchema = z.object({
  session_id: z.string(),
  messages: z.array(ChatMessageSchema),
});

export const ToolTraceItemSchema = z.object({
  step: z.number().optional(),
  tool: z.string(),
  algorithm: z.string().optional(),
  args: z.record(z.string(), z.any()).optional().default({}),
  output: z.any().optional(),
  data: z.any().optional(),
  selected_by: z.string().optional(),
});

export const AnalystResponseSchema = z.object({
  retraction_id: z.string(),
  tenant: z.string(),
  tool_trace: z.array(ToolTraceItemSchema),
  recommendation: z.string(),
  ticket_created: z.string().nullable().optional(),
  target_decision_id: z.string().nullable().optional(),
  algorithms_used: z.array(z.string()).optional().default([]),
});

export const BenchResponseSchema = z.object({
  benchmark: z.string(),
  timestamp: z.string(),
  total_tasks: z.number(),
  completed_tasks: z.number(),
  db_verified_done: z.number(),
  workers: z.number(),
  concurrent_tenant_graphs: z.number(),
  duration_seconds: z.number(),
  throughput_tasks_per_sec: z.number(),
  double_claims: z.number(),
  claim_latency_p50_ms: z.number(),
  claim_latency_p95_ms: z.number(),
  pass: z.boolean(),
});

export const ChaosResponseSchema = z.object({
  experiment: z.string().optional(),
  timestamp: z.string().optional(),
  passed: z.boolean().optional(),
  reclaimed_tasks: z.number().optional(),
  summary: z.string().optional(),
}).passthrough();
