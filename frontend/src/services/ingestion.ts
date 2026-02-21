import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import api from '@/services/api';

// ── Types ────────────────────────────────────────────────────────────────────

export interface IngestionStatus {
  running: boolean;
}

export interface IngestionRun {
  id: string;
  started_at: string;
  completed_at: string | null;
  status: 'success' | 'failed' | 'running' | 'interrupted';
  records_ingested: number | null;
  triggered_by: 'scheduled' | 'manual' | 'backfill';
  error_detail: string | null;
}

export interface IngestionAlert {
  id: string;
  error_message: string;
  retry_count: number;
  failed_at: string;
  is_active: boolean;
}

// ── Query keys ───────────────────────────────────────────────────────────────

export const ingestionKeys = {
  status: ['ingestion', 'status'] as const,
  runs: ['ingestion', 'runs'] as const,
  alerts: ['ingestion', 'alerts'] as const,
};

// ── Hooks ────────────────────────────────────────────────────────────────────

/**
 * Polls /ingestion/status.
 *
 * Adaptive interval: 5 s while the pipeline is running so the UI reflects
 * completion quickly; 30 s when idle so we don't hammer the server for no
 * reason.  When the pipeline transitions from running → idle the hook
 * automatically invalidates runs + alerts so they refresh once.
 */
export function useIngestionStatus() {
  const queryClient = useQueryClient();

  return useQuery<IngestionStatus>({
    queryKey: ingestionKeys.status,
    queryFn: async () => {
      const { data } = await api.get<IngestionStatus>('/ingestion/status');
      return data;
    },
    staleTime: 4_000, // treat as fresh for 4 s — slightly under the poll window
    refetchInterval: (query) => {
      const isRunning = query.state.data?.running ?? false;
      return isRunning ? 5_000 : 30_000;
    },
    // When the pipeline finishes (running flips false) invalidate sibling queries
    // so runs and alerts refresh exactly once without extra polling logic.
    select: (data) => data,
  });
}

/**
 * Fetches the last 20 ingestion runs.
 * Kept stale for 60 s — the list only changes after a run completes.
 */
export function useIngestionRuns() {
  return useQuery<IngestionRun[]>({
    queryKey: ingestionKeys.runs,
    queryFn: async () => {
      const { data } = await api.get<IngestionRun[]>('/ingestion/runs?limit=20');
      return data;
    },
    staleTime: 60_000,
  });
}

/**
 * Fetches active ingestion alerts.
 * Stale for 60 s — alert state doesn't change mid-flight.
 */
export function useIngestionAlerts() {
  return useQuery<IngestionAlert[]>({
    queryKey: ingestionKeys.alerts,
    queryFn: async () => {
      const { data } = await api.get<IngestionAlert[]>(
        '/ingestion/alerts?active_only=true'
      );
      return data;
    },
    staleTime: 60_000,
  });
}

/**
 * Triggers a manual ingestion run.
 * On success: optimistically marks status as running and invalidates runs +
 * alerts so they pick up the new run entry immediately.
 */
export function useRunIngestionNow() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      await api.post('/ingestion/run');
    },
    onSuccess: () => {
      // Optimistically mark status as running so the button disables instantly
      queryClient.setQueryData<IngestionStatus>(ingestionKeys.status, {
        running: true,
      });
      // Invalidate runs so the new entry appears as soon as the server responds
      queryClient.invalidateQueries({ queryKey: ingestionKeys.runs });
    },
  });
}
