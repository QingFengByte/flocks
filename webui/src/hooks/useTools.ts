import { useState, useEffect, useCallback, useRef } from 'react';
import { toolAPI, Tool } from '@/api/tool';

export function useTools() {
  const [tools, setTools] = useState<Tool[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const lastRefreshRef = useRef(0);

  const fetchTools = useCallback(async (showLoading = false) => {
    try {
      if (showLoading) setLoading(true);
      setError(null);
      const response = await toolAPI.list();
      setTools(Array.isArray(response.data) ? response.data : []);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch tools');
    } finally {
      if (showLoading) setLoading(false);
    }
  }, []);

  const refreshAndFetch = useCallback(async () => {
    const now = Date.now();
    if (now - lastRefreshRef.current < 5000) return;
    lastRefreshRef.current = now;
    try {
      await toolAPI.refresh();
    } catch { /* ignore */ }
    await fetchTools(false);
  }, [fetchTools]);

  useEffect(() => {
    const init = async () => {
      try { await toolAPI.refresh(); } catch { /* ignore */ }
      lastRefreshRef.current = Date.now();
      await fetchTools(true);
    };
    init();

    const onVisible = () => {
      if (document.visibilityState === 'visible') refreshAndFetch();
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => document.removeEventListener('visibilitychange', onVisible);
  }, [fetchTools, refreshAndFetch]);

  return {
    tools,
    loading,
    error,
    refetch: () => fetchTools(false),
  };
}
