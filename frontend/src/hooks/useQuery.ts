import { useState, useCallback } from 'react';
import { submitQuery } from '../api/queries';
import type { QueryResponse } from '../types/api';

interface QueryState {
  status: 'idle' | 'loading' | 'success' | 'error';
  result: QueryResponse | null;
  error: string | null;
  sessionId: string | null;
}

export function useQuery() {
  const [state, setState] = useState<QueryState>({
    status: 'idle',
    result: null,
    error: null,
    sessionId: null,
  });

  const submit = useCallback(
    async (question: string) => {
      setState((s) => ({ ...s, status: 'loading', error: null }));
      try {
        const result = await submitQuery({
          question,
          session_id: state.sessionId,
        });
        setState({
          status: 'success',
          result,
          error: null,
          sessionId: result.session_id,
        });
      } catch (err) {
        setState((s) => ({
          ...s,
          status: 'error',
          error: err instanceof Error ? err.message : 'Unknown error',
        }));
      }
    },
    [state.sessionId]
  );

  const reset = useCallback(() => {
    setState({
      status: 'idle',
      result: null,
      error: null,
      sessionId: null,
    });
  }, []);

  return { ...state, submit, reset };
}
