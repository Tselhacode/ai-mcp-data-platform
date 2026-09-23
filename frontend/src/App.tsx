import { useState, useCallback } from 'react';
import { QueryInput } from './components/QueryInput';
import { ExampleQuestions } from './components/ExampleQuestions';
import { ResultDisplay } from './components/ResultDisplay';
import { ToolActivity } from './components/ToolActivity';
import { StatusBadge } from './components/StatusBadge';
import { LoadingState } from './components/LoadingState';
import { useQuery } from './hooks/useQuery';
import { useHealth } from './hooks/useHealth';
import './App.css';

function App() {
  const { status, result, error, submit } = useQuery();
  const health = useHealth();
  const [inputValue, setInputValue] = useState('');

  const handleSubmit = useCallback(
    (question: string) => {
      setInputValue(question);
      void submit(question);
    },
    [submit]
  );

  const handleExampleSelect = useCallback((question: string) => {
    setInputValue(question);
  }, []);

  const isLoading = status === 'loading';

  return (
    <div className="app">
      <header className="app-header">
        <h1>Energy Analytics AI</h1>
        <StatusBadge status={health.status} />
      </header>

      <div className="app-layout">
        <aside className="app-sidebar">
          <div className="sidebar-section">
            <h2>About</h2>
            <p>
              Ask natural language questions about building energy consumption.
              The AI agent queries the database using MCP tools and returns
              data-grounded answers.
            </p>
          </div>
          <ExampleQuestions onSelect={handleExampleSelect} disabled={isLoading} />
        </aside>

        <main className="app-main">
          <QueryInput
            onSubmit={handleSubmit}
            isLoading={isLoading}
            defaultValue={inputValue}
            key={inputValue}
          />

          {isLoading && <LoadingState />}

          {error && (
            <div className="error-message" role="alert">
              <strong>Error:</strong> {error}
            </div>
          )}

          {result && status === 'success' && (
            <>
              <ResultDisplay result={result} />
              <ToolActivity
                tools={result.tools_used}
                latencyMs={result.latency_ms}
              />
            </>
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
