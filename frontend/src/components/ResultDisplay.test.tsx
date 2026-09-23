import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ResultDisplay } from './ResultDisplay';
import type { QueryResponse } from '../types/api';

describe('ResultDisplay', () => {
  const mockResult: QueryResponse = {
    session_id: 'abc-123-def-456',
    answer: 'Building B007 had the highest consumption at 14,291 kWh.',
    tools_used: [],
    latency_ms: 1200,
    request_id: 'req-1',
  };

  it('renders the answer text', () => {
    render(<ResultDisplay result={mockResult} />);
    expect(
      screen.getByText(/Building B007 had the highest consumption/)
    ).toBeInTheDocument();
  });

  it('shows latency', () => {
    render(<ResultDisplay result={mockResult} />);
    expect(screen.getByText('1200ms')).toBeInTheDocument();
  });

  it('shows session ID prefix', () => {
    render(<ResultDisplay result={mockResult} />);
    expect(screen.getByText(/abc-123-/)).toBeInTheDocument();
  });
});
