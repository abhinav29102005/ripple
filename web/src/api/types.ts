import { z } from 'zod';
import * as schemas from './schemas';

export type HealthResponse = z.infer<typeof schemas.HealthResponseSchema>;
export type Task = z.infer<typeof schemas.TaskSchema>;
export type TasksResponse = z.infer<typeof schemas.TasksResponseSchema>;
export type Agent = z.infer<typeof schemas.AgentSchema>;
export type AgentsResponse = z.infer<typeof schemas.AgentsResponseSchema>;
export type GraphNode = z.infer<typeof schemas.GraphNodeSchema>;
export type GraphEdge = z.infer<typeof schemas.GraphEdgeSchema>;
export type BlastResponse = z.infer<typeof schemas.BlastResponseSchema>;
export type Alert = z.infer<typeof schemas.AlertSchema>;
export type RankingsResponse = z.infer<typeof schemas.RankingsResponseSchema>;
export type ExplainResponse = z.infer<typeof schemas.ExplainResponseSchema>;
export type Episode = z.infer<typeof schemas.EpisodeSchema>;
export type ActiveRule = z.infer<typeof schemas.ActiveRuleSchema>;
export type Fact = z.infer<typeof schemas.FactSchema>;
export type MemoryResponse = z.infer<typeof schemas.MemoryResponseSchema>;
export type ChatMessage = z.infer<typeof schemas.ChatMessageSchema>;
export type ChatResponse = z.infer<typeof schemas.ChatResponseSchema>;
export type ToolTraceItem = z.infer<typeof schemas.ToolTraceItemSchema>;
export type AnalystResponse = z.infer<typeof schemas.AnalystResponseSchema>;
export type BenchResponse = z.infer<typeof schemas.BenchResponseSchema>;
export type ChaosResponse = z.infer<typeof schemas.ChaosResponseSchema>;

export type TenantId = 'tenant_cardio' | 'tenant_onco';
export type ViewTab = 'coordination' | 'memory' | 'analyst' | 'chat' | 'proof';
