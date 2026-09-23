import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ToolActivity } from './ToolActivity';
import type { ToolUsage } from '../types/api';

describe('ToolActivity', () => {
  const mockTools: ToolUsage[] = [
    {
      tool: 'get_building_summary',
      args: { building_id: 'B007' },
      result_summary: 'Total: 14291 kWh',
    },
    {
      tool: 'get_consumption_trend',
      args: { start_date: '2024-07-01' },
      result_summary: 'Trend data returned',
    },
  ];

  it('renders tool count and time', () => {
    render(<ToolActivity tools={mockTools} latencyMs={1800} />);
    expect(screen.getByText(/2 tools/)).toBeInTheDocument();
    expect(screen.getByText(/1.8s/)).toBeInTheDocument();
  });

  it('renders nothing when no tools', () => {
    const { container } = render(
      <ToolActivity tools={[]} latencyMs={0} />
    );
    expect(container.firstChild).toBeNull();
  });

  it('expands to show tool details', async () => {
    const user = userEvent.setup();
    render(<ToolActivity tools={mockTools} latencyMs={1800} />);

    // Initially collapsed
    expect(screen.queryByText('get_building_summary')).not.toBeInTheDocument();

    // Click to expand
    await user.click(screen.getByRole('button'));
    expect(screen.getByText('get_building_summary')).toBeInTheDocument();
    expect(screen.getByText('get_consumption_trend')).toBeInTheDocument();
  });

  it('collapses after expanding', async () => {
    const user = userEvent.setup();
    render(<ToolActivity tools={mockTools} latencyMs={1800} />);

    const button = screen.getByRole('button');
    await user.click(button); // expand
    expect(screen.getByText('get_building_summary')).toBeInTheDocument();

    await user.click(button); // collapse
    expect(screen.queryByText('get_building_summary')).not.toBeInTheDocument();
  });
});
