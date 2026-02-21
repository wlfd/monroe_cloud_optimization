import { useQuery } from '@tanstack/react-query';
import api from '@/services/api';

export interface SpendSummary {
  mtd_total: number;
  projected_month_end: number;
  prior_month_total: number;
  mom_delta_pct: number | null;
}

export interface DailySpend {
  usage_date: string;
  total_cost: number;
}

export interface BreakdownItem {
  dimension_value: string;
  total_cost: number;
}

export interface TopResource {
  resource_id: string;
  resource_name: string;
  service_name: string;
  resource_group: string;
  total_cost: number;
}

export function useSpendSummary() {
  return useQuery<SpendSummary>({
    queryKey: ['spend-summary'],
    queryFn: async () => {
      const { data } = await api.get<SpendSummary>('/costs/summary');
      return data;
    },
    staleTime: 5 * 60 * 1000,
  });
}

export function useSpendTrend(days: number) {
  return useQuery<DailySpend[]>({
    queryKey: ['spend-trend', days],
    queryFn: async () => {
      const { data } = await api.get<DailySpend[]>('/costs/trend', { params: { days } });
      return data;
    },
    staleTime: 5 * 60 * 1000,
  });
}

export function useSpendBreakdown(dimension: string, days: number) {
  return useQuery<BreakdownItem[]>({
    queryKey: ['spend-breakdown', dimension, days],
    queryFn: async () => {
      const { data } = await api.get<BreakdownItem[]>('/costs/breakdown', {
        params: { dimension, days },
      });
      return data;
    },
    staleTime: 5 * 60 * 1000,
  });
}

export function useTopResources(days: number) {
  return useQuery<TopResource[]>({
    queryKey: ['top-resources', days],
    queryFn: async () => {
      const { data } = await api.get<TopResource[]>('/costs/top-resources', { params: { days } });
      return data;
    },
    staleTime: 5 * 60 * 1000,
  });
}
