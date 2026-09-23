import { describe, it, expect, vi, beforeEach } from 'vitest';
import { submitQuery, checkHealth } from './queries';

const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

describe('submitQuery', () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it('sends POST request with correct body', async () => {
    const mockResponse = {
      session_id: 'sess-1',
      answer: 'B007 is the highest.',
      tools_used: [],
      latency_ms: 500,
    };
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockResponse),
    });

    const result = await submitQuery({ question: 'Which is highest?' });

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, options] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toContain('/api/v1/query');
    expect(options.method).toBe('POST');
    expect(JSON.parse(options.body as string)).toEqual({
      question: 'Which is highest?',
    });
    expect(result).toEqual(mockResponse);
  });

  it('throws on non-OK response', async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
      text: () => Promise.resolve('Internal server error'),
    });

    await expect(
      submitQuery({ question: 'test' })
    ).rejects.toThrow('API error 500');
  });
});

describe('checkHealth', () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it('returns health status', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ status: 'ok' }),
    });

    const result = await checkHealth();
    expect(result.status).toBe('ok');
  });
});
