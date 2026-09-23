import type { QueryResponse } from '../types/api';

interface ResultDisplayProps {
  result: QueryResponse;
}

export function ResultDisplay({ result }: ResultDisplayProps) {
  return (
    <div className="result-display">
      <h3>Answer</h3>
      <div className="result-answer">{result.answer}</div>
      <div className="result-meta">
        <span className="result-latency">{result.latency_ms}ms</span>
        {result.session_id && (
          <span className="result-session">
            Session: {result.session_id.slice(0, 8)}...
          </span>
        )}
      </div>
    </div>
  );
}
