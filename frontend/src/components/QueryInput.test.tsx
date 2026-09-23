import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryInput } from './QueryInput';

describe('QueryInput', () => {
  it('renders textarea and submit button', () => {
    render(<QueryInput onSubmit={vi.fn()} isLoading={false} />);
    expect(screen.getByRole('textbox')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /submit/i })).toBeInTheDocument();
  });

  it('calls onSubmit with input value', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<QueryInput onSubmit={onSubmit} isLoading={false} />);

    const textarea = screen.getByRole('textbox');
    await user.type(textarea, 'What is B007 consumption?');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    expect(onSubmit).toHaveBeenCalledWith('What is B007 consumption?');
  });

  it('disables input and button during loading', () => {
    render(<QueryInput onSubmit={vi.fn()} isLoading={true} />);
    expect(screen.getByRole('textbox')).toBeDisabled();
    expect(screen.getByRole('button')).toBeDisabled();
  });

  it('shows loading text on button when loading', () => {
    render(<QueryInput onSubmit={vi.fn()} isLoading={true} />);
    expect(screen.getByRole('button')).toHaveTextContent('Analyzing...');
  });

  it('does not submit empty input', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<QueryInput onSubmit={onSubmit} isLoading={false} />);

    await user.click(screen.getByRole('button', { name: /submit/i }));
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('renders with default value', () => {
    render(
      <QueryInput
        onSubmit={vi.fn()}
        isLoading={false}
        defaultValue="test question"
      />
    );
    expect(screen.getByRole('textbox')).toHaveValue('test question');
  });
});
