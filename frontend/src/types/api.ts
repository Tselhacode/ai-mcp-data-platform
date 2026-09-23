export interface ToolUsage {
  tool: string;
  args: Record<string, unknown>;
  result_summary: string;
}

export interface QueryResponse {
  session_id: string;
  answer: string;
  tools_used: ToolUsage[];
  latency_ms: number;
  request_id?: string;
}

export interface QueryRequest {
  question: string;
  session_id?: string | null;
}

export interface HealthResponse {
  status: string;
}
