import { useState } from 'react';
import type { ToolUsage } from '../types/api';

interface ToolActivityProps {
  tools: ToolUsage[];
  latencyMs: number;
}

export function ToolActivity({ tools, latencyMs }: ToolActivityProps) {
  const [expanded, setExpanded] = useState(false);

  if (tools.length === 0) {
    return null;
  }

  return (
    <div className="tool-activity">
      <button
        className="tool-activity-header"
        onClick={() => setExpanded(!expanded)}
        type="button"
        aria-expanded={expanded}
      >
        <span className="tool-activity-summary">
          Analysis complete &middot; {tools.length} tool{tools.length !== 1 ? 's' : ''} &middot;{' '}
          {(latencyMs / 1000).toFixed(1)}s
        </span>
        <span className="tool-activity-toggle">
          {expanded ? 'Collapse' : 'Expand'}
        </span>
      </button>
      {expanded && (
        <div className="tool-activity-details">
          {tools.map((tool, index) => (
            <div key={index} className="tool-call">
              <div className="tool-call-name">{tool.tool}</div>
              <div className="tool-call-args">
                <strong>Args:</strong>{' '}
                <code>{JSON.stringify(tool.args)}</code>
              </div>
              {tool.result_summary && (
                <div className="tool-call-result">
                  <strong>Result:</strong> {tool.result_summary.slice(0, 200)}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
