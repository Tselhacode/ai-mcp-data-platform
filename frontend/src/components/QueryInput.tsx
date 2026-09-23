import { useState, useCallback, type KeyboardEvent, type FormEvent } from 'react';

interface QueryInputProps {
  onSubmit: (question: string) => void;
  isLoading: boolean;
  defaultValue?: string;
}

export function QueryInput({ onSubmit, isLoading, defaultValue }: QueryInputProps) {
  const [value, setValue] = useState(defaultValue ?? '');

  const handleSubmit = useCallback(
    (e: FormEvent) => {
      e.preventDefault();
      const trimmed = value.trim();
      if (trimmed && !isLoading) {
        onSubmit(trimmed);
      }
    },
    [value, isLoading, onSubmit]
  );

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        const trimmed = value.trim();
        if (trimmed && !isLoading) {
          onSubmit(trimmed);
        }
      }
    },
    [value, isLoading, onSubmit]
  );

  return (
    <form onSubmit={handleSubmit} className="query-input">
      <label htmlFor="query-textarea" className="sr-only">
        Ask a question about energy data
      </label>
      <textarea
        id="query-textarea"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask about energy consumption..."
        disabled={isLoading}
        rows={3}
        maxLength={2000}
        aria-label="Ask a question about energy data"
      />
      <div className="query-input-footer">
        <span className="char-count">{value.length}/2000</span>
        <button type="submit" disabled={isLoading || !value.trim()}>
          {isLoading ? 'Analyzing...' : 'Submit'}
        </button>
      </div>
    </form>
  );
}
