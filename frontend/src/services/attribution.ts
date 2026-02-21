import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import api from '@/services/api';

// ── TypeScript Interfaces ────────────────────────────────────────────────────

export interface TenantAttribution {
  tenant_id: string;
  display_name: string | null;
  year: number;
  month: number;
  total_cost: number;
  pct_of_total: number;
  mom_delta_usd: number | null;
  top_service_category: string | null;
  allocated_cost: number;
  tagged_cost: number;
  computed_at: string;
}

export interface ServiceBreakdownItem {
  service_name: string;
  total_cost: number;
}

export interface TenantProfile {
  id: string;
  tenant_id: string;
  display_name: string | null;
  is_new: boolean;
  acknowledged_at: string | null;
  first_seen: string;
}

export interface AllocationRule {
  id: string;
  priority: number;
  target_type: 'resource_group' | 'service_category';
  target_value: string;
  method: 'by_count' | 'by_usage' | 'manual_pct';
  manual_pct: Record<string, number> | null;
}

// ── Query Hooks ──────────────────────────────────────────────────────────────

// useAttribution — GET /attribution/?year=Y&month=M
export function useAttribution(year: number, month: number) {
  return useQuery<TenantAttribution[]>({
    queryKey: ['attribution', year, month],
    queryFn: async () => {
      const { data } = await api.get<TenantAttribution[]>('/attribution/', { params: { year, month } });
      return data;
    },
    staleTime: 5 * 60 * 1000,
  });
}

// useAttributionBreakdown — GET /attribution/breakdown/{tenant_id}?year=Y&month=M
// Only enabled when tenantId is non-null (called from expanded row)
export function useAttributionBreakdown(tenantId: string | null, year: number, month: number) {
  return useQuery<ServiceBreakdownItem[]>({
    queryKey: ['attribution-breakdown', tenantId, year, month],
    queryFn: async () => {
      const { data } = await api.get<ServiceBreakdownItem[]>(`/attribution/breakdown/${tenantId}`, { params: { year, month } });
      return data;
    },
    enabled: tenantId !== null,
    staleTime: 5 * 60 * 1000,
  });
}

// useTenantProfiles — GET /settings/tenants
export function useTenantProfiles() {
  return useQuery<TenantProfile[]>({
    queryKey: ['tenants'],
    queryFn: async () => {
      const { data } = await api.get<TenantProfile[]>('/settings/tenants');
      return data;
    },
    staleTime: 5 * 60 * 1000,
  });
}

// useAllocationRules — GET /settings/rules
export function useAllocationRules() {
  return useQuery<AllocationRule[]>({
    queryKey: ['rules'],
    queryFn: async () => {
      const { data } = await api.get<AllocationRule[]>('/settings/rules');
      return data;
    },
    staleTime: 5 * 60 * 1000,
  });
}

// ── Mutation Hooks ───────────────────────────────────────────────────────────

// useUpdateTenantName — PATCH /settings/tenants/{tenant_id}/name
// Invalidates: ['tenants'] queryKey on success
export function useUpdateTenantName() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ tenant_id, display_name }: { tenant_id: string; display_name: string }) => {
      await api.patch(`/settings/tenants/${tenant_id}/name`, { display_name });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tenants'] });
    },
  });
}

// useAcknowledgeTenant — POST /settings/tenants/{tenant_id}/acknowledge
// Invalidates: ['tenants'] queryKey on success
export function useAcknowledgeTenant() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ tenant_id }: { tenant_id: string }) => {
      await api.post(`/settings/tenants/${tenant_id}/acknowledge`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tenants'] });
    },
  });
}

// useCreateAllocationRule — POST /settings/rules
// Invalidates: ['rules'] queryKey on success
export function useCreateAllocationRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (rule: Omit<AllocationRule, 'id'>) => {
      const { data } = await api.post<AllocationRule>('/settings/rules', rule);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rules'] });
    },
  });
}

// useUpdateAllocationRule — PATCH /settings/rules/{rule_id}
// Invalidates: ['rules'] queryKey on success
export function useUpdateAllocationRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ rule_id, ...updates }: Partial<AllocationRule> & { rule_id: string }) => {
      const { data } = await api.patch<AllocationRule>(`/settings/rules/${rule_id}`, updates);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rules'] });
    },
  });
}

// useDeleteAllocationRule — DELETE /settings/rules/{rule_id}
// Invalidates: ['rules'] queryKey on success
export function useDeleteAllocationRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ rule_id }: { rule_id: string }) => {
      await api.delete(`/settings/rules/${rule_id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rules'] });
    },
  });
}

// useReorderAllocationRules — POST /settings/rules/reorder (body: {rule_ids: string[]})
// Invalidates: ['rules'] queryKey on success
export function useReorderAllocationRules() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ rule_ids }: { rule_ids: string[] }) => {
      await api.post('/settings/rules/reorder', { rule_ids });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rules'] });
    },
  });
}

// ── One-off Action (not server state, no hook needed) ────────────────────────

// exportAttribution — GET /attribution/export with responseType: blob
// Same blob download pattern as cost.ts exportCostBreakdown
export async function exportAttribution(year: number, month: number): Promise<void> {
  const response = await api.get('/attribution/export', {
    params: { year, month },
    responseType: 'blob',
  });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', `attribution-${year}-${String(month).padStart(2, '0')}.csv`);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}
