import { apiRequest } from './client';
import type {
  QueryRequest,
  QueryResponse,
  HealthResponse,
} from '../types/api';

export async function submitQuery(
  request: QueryRequest
): Promise<QueryResponse> {
  return apiRequest<QueryResponse>('/api/v1/query', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

export async function checkHealth(): Promise<HealthResponse> {
  return apiRequest<HealthResponse>('/api/v1/health');
}
