import { useState, useRef } from 'react';
import { GripVertical } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  useTenantProfiles,
  useUpdateTenantName,
  useAcknowledgeTenant,
  useAllocationRules,
  useCreateAllocationRule,
  useDeleteAllocationRule,
  useReorderAllocationRules,
  type TenantProfile,
  type AllocationRule,
} from '@/services/attribution';

// ── TenantsTab sub-component ──────────────────────────────────────────────────

function TenantsTab() {
  const { data: tenants = [], isLoading } = useTenantProfiles();
  const updateName = useUpdateTenantName();
  const acknowledge = useAcknowledgeTenant();

  // Map of tenant_id -> editing state
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');

  function startEdit(tenant: TenantProfile) {
    setEditingId(tenant.tenant_id);
    setEditValue(tenant.display_name ?? '');
  }

  function cancelEdit() {
    setEditingId(null);
    setEditValue('');
  }

  function saveName(tenant_id: string) {
    updateName.mutate(
      { tenant_id, display_name: editValue },
      {
        onSuccess: () => {
          setEditingId(null);
          setEditValue('');
        },
      },
    );
  }

  if (isLoading) {
    return (
      <div className="space-y-3 mt-4">
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </div>
    );
  }

  if (tenants.length === 0) {
    return (
      <p className="text-sm text-muted-foreground mt-4">
        No tenant profiles found. Tenants appear here once attribution data is ingested.
      </p>
    );
  }

  return (
    <Table className="mt-4">
      <TableHeader>
        <TableRow>
          <TableHead>Tenant ID</TableHead>
          <TableHead>Display Name</TableHead>
          <TableHead>First Seen</TableHead>
          <TableHead>Status</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {tenants.map((tenant) => (
          <TableRow key={tenant.id}>
            <TableCell className="font-mono text-sm">{tenant.tenant_id}</TableCell>
            <TableCell>
              {editingId === tenant.tenant_id ? (
                <div className="flex items-center gap-2">
                  <Input
                    className="h-7 w-48 text-sm"
                    value={editValue}
                    onChange={(e) => setEditValue(e.target.value)}
                    onBlur={() => {
                      // Cancel if user blurs without saving
                      if (editingId === tenant.tenant_id) {
                        cancelEdit();
                      }
                    }}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') saveName(tenant.tenant_id);
                      if (e.key === 'Escape') cancelEdit();
                    }}
                    autoFocus
                  />
                  <Button
                    size="sm"
                    className="h-7 text-xs"
                    disabled={updateName.isPending}
                    onMouseDown={(e) => {
                      // Prevent blur from firing before click
                      e.preventDefault();
                      saveName(tenant.tenant_id);
                    }}
                  >
                    Save
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-7 text-xs"
                    onMouseDown={(e) => {
                      e.preventDefault();
                      cancelEdit();
                    }}
                  >
                    Cancel
                  </Button>
                </div>
              ) : (
                <button
                  className="text-sm hover:underline text-left cursor-pointer"
                  onClick={() => startEdit(tenant)}
                >
                  {tenant.display_name ?? (
                    <span className="text-muted-foreground italic">Click to set name</span>
                  )}
                </button>
              )}
            </TableCell>
            <TableCell className="text-sm text-muted-foreground">
              {new Date(tenant.first_seen).toLocaleDateString('en-US', {
                year: 'numeric',
                month: 'short',
                day: 'numeric',
              })}
            </TableCell>
            <TableCell>
              {tenant.is_new ? (
                <div className="flex items-center gap-2">
                  <Badge variant="secondary">New</Badge>
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-6 text-xs"
                    disabled={acknowledge.isPending}
                    onClick={() => acknowledge.mutate({ tenant_id: tenant.tenant_id })}
                  >
                    Acknowledge
                  </Button>
                </div>
              ) : (
                <span className="text-sm text-muted-foreground">Active</span>
              )}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

// ── AllocationRulesTab sub-component ──────────────────────────────────────────

type NewRuleForm = {
  priority: string;
  target_type: 'resource_group' | 'service_category' | '';
  target_value: string;
  method: 'by_count' | 'by_usage' | 'manual_pct' | '';
  manual_pct: string;
};

const EMPTY_FORM: NewRuleForm = {
  priority: '',
  target_type: '',
  target_value: '',
  method: '',
  manual_pct: '',
};

function AllocationRulesTab() {
  const { data: rules = [], isLoading } = useAllocationRules();
  const createRule = useCreateAllocationRule();
  const deleteRule = useDeleteAllocationRule();
  const reorderRules = useReorderAllocationRules();

  const [isAddingRule, setIsAddingRule] = useState(false);
  const [form, setForm] = useState<NewRuleForm>(EMPTY_FORM);

  // Drag state — refs hold source/target so the pointerup closure is never stale
  const dragFromRef = useRef<number | null>(null);
  const dragToRef = useRef<number | null>(null);
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);

  function startDrag(e: React.PointerEvent, index: number) {
    e.preventDefault(); // prevent text selection while dragging
    dragFromRef.current = index;
    dragToRef.current = index;
    setDragIndex(index);

    function onPointerUp() {
      const from = dragFromRef.current;
      const to = dragToRef.current;
      if (from !== null && to !== null && from !== to) {
        const reordered = [...rules];
        const [moved] = reordered.splice(from, 1);
        reordered.splice(to, 0, moved);
        reorderRules.mutate({ rule_ids: reordered.map((r) => r.id) });
      }
      dragFromRef.current = null;
      dragToRef.current = null;
      setDragIndex(null);
      setDragOverIndex(null);
      document.removeEventListener('pointerup', onPointerUp);
    }

    document.addEventListener('pointerup', onPointerUp);
  }

  function handleRowPointerEnter(index: number) {
    if (dragFromRef.current !== null) {
      dragToRef.current = index;
      setDragOverIndex(index);
    }
  }

  function handleDelete(rule: AllocationRule) {
    if (!window.confirm('Delete this rule?')) return;
    deleteRule.mutate({ rule_id: rule.id });
  }

  function handleSaveNewRule() {
    if (!form.target_type || !form.method) return;

    let manual_pct: Record<string, number> | null = null;
    if (form.method === 'manual_pct' && form.manual_pct.trim()) {
      try {
        manual_pct = JSON.parse(form.manual_pct);
      } catch {
        alert('Invalid JSON for manual %');
        return;
      }
    }

    createRule.mutate(
      {
        priority: parseInt(form.priority, 10) || (rules.length + 1),
        target_type: form.target_type as 'resource_group' | 'service_category',
        target_value: form.target_value,
        method: form.method as 'by_count' | 'by_usage' | 'manual_pct',
        manual_pct,
      },
      {
        onSuccess: () => {
          setIsAddingRule(false);
          setForm(EMPTY_FORM);
        },
      },
    );
  }

  if (isLoading) {
    return (
      <div className="space-y-3 mt-4">
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </div>
    );
  }

  return (
    <div className="mt-4 space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          Rules are evaluated in priority order. Lower number = higher priority.
        </p>
        <Button
          size="sm"
          variant="outline"
          onClick={() => setIsAddingRule(true)}
          disabled={isAddingRule}
        >
          Add Rule
        </Button>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-8" />
            <TableHead className="w-16">Priority</TableHead>
            <TableHead>Target Type</TableHead>
            <TableHead>Target Value</TableHead>
            <TableHead>Method</TableHead>
            <TableHead>Manual %</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rules.map((rule, index) => (
            <TableRow
              key={rule.id}
              onPointerEnter={() => handleRowPointerEnter(index)}
              className={dragOverIndex === index && dragIndex !== index ? 'border-t-2 border-primary' : ''}
            >
              <TableCell
                className="pr-0 cursor-grab active:cursor-grabbing select-none"
                onPointerDown={(e) => startDrag(e, index)}
              >
                <GripVertical className="h-4 w-4 text-muted-foreground pointer-events-none" />
              </TableCell>
              <TableCell className="text-sm text-muted-foreground">{rule.priority}</TableCell>
              <TableCell className="text-sm">{rule.target_type}</TableCell>
              <TableCell className="text-sm font-mono">{rule.target_value}</TableCell>
              <TableCell className="text-sm">{rule.method}</TableCell>
              <TableCell className="text-sm font-mono text-muted-foreground">
                {rule.manual_pct ? JSON.stringify(rule.manual_pct) : '—'}
              </TableCell>
              <TableCell className="text-right">
                <Button
                  size="sm"
                  variant="destructive"
                  className="h-7 text-xs"
                  disabled={deleteRule.isPending}
                  onClick={() => handleDelete(rule)}
                >
                  Delete
                </Button>
              </TableCell>
            </TableRow>
          ))}

          {/* Inline add row */}
          {isAddingRule && (
            <TableRow>
              <TableCell />
              <TableCell>
                <Input
                  type="number"
                  placeholder={String(rules.length + 1)}
                  className="h-7 w-16 text-sm"
                  value={form.priority}
                  onChange={(e) => setForm((f) => ({ ...f, priority: e.target.value }))}
                />
              </TableCell>
              <TableCell>
                <Select
                  value={form.target_type}
                  onValueChange={(v) =>
                    setForm((f) => ({ ...f, target_type: v as NewRuleForm['target_type'] }))
                  }
                >
                  <SelectTrigger className="h-7 w-36 text-xs">
                    <SelectValue placeholder="Target type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="resource_group">resource_group</SelectItem>
                    <SelectItem value="service_category">service_category</SelectItem>
                  </SelectContent>
                </Select>
              </TableCell>
              <TableCell>
                <Input
                  placeholder="Target value"
                  className="h-7 w-36 text-sm"
                  value={form.target_value}
                  onChange={(e) => setForm((f) => ({ ...f, target_value: e.target.value }))}
                />
              </TableCell>
              <TableCell>
                <Select
                  value={form.method}
                  onValueChange={(v) =>
                    setForm((f) => ({ ...f, method: v as NewRuleForm['method'] }))
                  }
                >
                  <SelectTrigger className="h-7 w-36 text-xs">
                    <SelectValue placeholder="Method" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="by_count">by_count</SelectItem>
                    <SelectItem value="by_usage">by_usage</SelectItem>
                    <SelectItem value="manual_pct">manual_pct</SelectItem>
                  </SelectContent>
                </Select>
              </TableCell>
              <TableCell>
                {form.method === 'manual_pct' ? (
                  <Input
                    placeholder='{"tenant-a": 60, "tenant-b": 40}'
                    className="h-7 w-48 text-xs font-mono"
                    value={form.manual_pct}
                    onChange={(e) => setForm((f) => ({ ...f, manual_pct: e.target.value }))}
                  />
                ) : (
                  <span className="text-xs text-muted-foreground">—</span>
                )}
              </TableCell>
              <TableCell className="text-right">
                <div className="flex justify-end gap-1">
                  <Button
                    size="sm"
                    className="h-7 text-xs"
                    disabled={createRule.isPending || !form.target_type || !form.method}
                    onClick={handleSaveNewRule}
                  >
                    Save
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-7 text-xs"
                    onClick={() => {
                      setIsAddingRule(false);
                      setForm(EMPTY_FORM);
                    }}
                  >
                    Cancel
                  </Button>
                </div>
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>

      {rules.length === 0 && !isAddingRule && (
        <p className="text-sm text-muted-foreground text-center py-4">
          No allocation rules defined. Add a rule to control how shared costs are split across tenants.
        </p>
      )}
    </div>
  );
}

// ── Main page component ───────────────────────────────────────────────────────

export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-sm text-muted-foreground">
          Manage tenant profiles and cost allocation rules
        </p>
      </div>

      <Tabs defaultValue="tenants">
        <TabsList>
          <TabsTrigger value="tenants">Tenants</TabsTrigger>
          <TabsTrigger value="rules">Allocation Rules</TabsTrigger>
        </TabsList>

        <TabsContent value="tenants">
          <TenantsTab />
        </TabsContent>

        <TabsContent value="rules">
          <AllocationRulesTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
