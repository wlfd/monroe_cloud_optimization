import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import api from '@/services/api';

// ── TypeScript Interfaces ────────────────────────────────────────────────────

export interface Anomaly {
  id: string;
  detected_date: string;
  service_name: string;
  resource_group: string;
  description: string;
  severity: 'critical' | 'high' | 'medium';
  status: 'new' | 'investigating' | 'resolved' | 'dismissed';
  expected: boolean;
  pct_deviation: number;
  estimated_monthly_impact: number;
  baseline_daily_avg: number;
  current_daily_cost: number;
  created_at: string;
  updated_at: string;
}

export interface AnomalySummary {
  active_count: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  total_potential_impact: number;
  resolved_this_month: number;
  detection_accuracy: number | null;
}

export interface AnomalyFilters {
  status?: string;
  severity?: string;
  service_name?: string;
  resource_group?: string;
}

// ── Query Hooks ──────────────────────────────────────────────────────────────

export function useAnomalies(filters: AnomalyFilters = {}) {
  return useQuery<Anomaly[]>({
    queryKey: ['anomalies', filters],
    queryFn: async () => {
      // Remove undefined/empty values from params
      const params = Object.fromEntries(
        Object.entries(filters).filter(([, v]) => v !== undefined && v !== '' && v !== 'all')
      );
      const { data } = await api.get<Anomaly[]>('/anomalies/', { params });
      return data;
    },
    staleTime: 2 * 60 * 1000, // 2 min
  });
}

export function useAnomalySummary() {
  return useQuery<AnomalySummary>({
    queryKey: ['anomaly-summary'],
    queryFn: async () => {
      const { data } = await api.get<AnomalySummary>('/anomalies/summary');
      return data;
    },
    staleTime: 2 * 60 * 1000,
  });
}

// ── Mutation Hooks ───────────────────────────────────────────────────────────

export function useUpdateAnomalyStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, status }: { id: string; status: string }) => {
      await api.patch(`/anomalies/${id}/status`, { status });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['anomalies'] });
      queryClient.invalidateQueries({ queryKey: ['anomaly-summary'] });
    },
  });
}

export function useMarkAnomalyExpected() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id }: { id: string }) => {
      await api.patch(`/anomalies/${id}/expected`, { expected: true });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['anomalies'] });
      queryClient.invalidateQueries({ queryKey: ['anomaly-summary'] });
    },
  });
}

export function useUnmarkAnomalyExpected() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id }: { id: string }) => {
      await api.patch(`/anomalies/${id}/expected`, { expected: false });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['anomalies'] });
      queryClient.invalidateQueries({ queryKey: ['anomaly-summary'] });
    },
  });
}

// ── One-off Action (not server state, no hook needed) ────────────────────────

export async function exportAnomalies(
  filters: Pick<AnomalyFilters, 'severity' | 'service_name'> = {}
): Promise<void> {
  const params = Object.fromEntries(
    Object.entries(filters).filter(([, v]) => v !== undefined && v !== '' && v !== 'all')
  );
  const response = await api.get('/anomalies/export', {
    params,
    responseType: 'blob',
  });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', 'anomaly-report.csv');
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}
