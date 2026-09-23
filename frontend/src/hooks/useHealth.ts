import { useState, useEffect } from 'react';
import { checkHealth } from '../api/queries';

interface HealthState {
  status: 'checking' | 'online' | 'offline';
}

export function useHealth() {
  const [health, setHealth] = useState<HealthState>({ status: 'checking' });

  useEffect(() => {
    let cancelled = false;

    async function check() {
      try {
        const result = await checkHealth();
        if (!cancelled) {
          setHealth({
            status: result.status === 'ok' ? 'online' : 'offline',
          });
        }
      } catch {
        if (!cancelled) {
          setHealth({ status: 'offline' });
        }
      }
    }

    void check();

    return () => {
      cancelled = true;
    };
  }, []);

  return health;
}
