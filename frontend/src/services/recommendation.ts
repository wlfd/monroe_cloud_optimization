import { useQuery } from '@tanstack/react-query';
import api from '@/services/api';

// ── TypeScript Interfaces ─────────────────────────────────────────────────────

export interface Recommendation {
  id: string;
  generated_date: string;
  resource_name: string;
  resource_group: string;
  subscription_id: string;
  service_name: string;
  meter_category: string;
  category: 'right-sizing' | 'idle' | 'reserved' | 'storage';
  explanation: string;
  estimated_monthly_savings: number;
  confidence_score: number;
  current_monthly_cost: number;
  created_at: string;
}

export interface RecommendationSummary {
  total_count: number;
  potential_monthly_savings: number;
  by_category: Record<string, number>;
  daily_limit_reached: boolean;
  calls_used_today: number;
  daily_call_limit: number;
}

export interface RecommendationFilters {
  category?: string;
  min_savings?: number;
  min_confidence?: number;
}

// ── Query Hooks ───────────────────────────────────────────────────────────────

export function useRecommendations(filters: RecommendationFilters = {}) {
  return useQuery<Recommendation[]>({
    queryKey: ['recommendations', filters],
    queryFn: async () => {
      const params = Object.fromEntries(
        Object.entries(filters).filter(([, v]) => v !== undefined && v !== '' && v !== 'all' && v !== 0)
      );
      const { data } = await api.get<Recommendation[]>('/recommendations/', { params });
      return data;
    },
    staleTime: 5 * 60 * 1000, // 5 min — recommendations change at most once daily
  });
}

export function useRecommendationSummary() {
  return useQuery<RecommendationSummary>({
    queryKey: ['recommendation-summary'],
    queryFn: async () => {
      const { data } = await api.get<RecommendationSummary>('/recommendations/summary');
      return data;
    },
    staleTime: 5 * 60 * 1000,
  });
}

// ── One-off Action (not server state) ────────────────────────────────────────

export async function triggerRecommendations(): Promise<void> {
  await api.post('/recommendations/run');
}
