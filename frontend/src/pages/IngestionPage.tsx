import { useRef, useCallback, useState } from 'react';
import { AlertTriangle } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useAuth } from '@/hooks/useAuth';
import { useQueryClient } from '@tanstack/react-query';
import type { AxiosError } from 'axios';
import {
  useIngestionStatus,
  useIngestionRuns,
  useIngestionAlerts,
  useRunIngestionNow,
  ingestionKeys,
} from '@/services/ingestion';
import type { IngestionRun, IngestionAlert } from '@/services/ingestion';

// ---- Helpers ----

function formatLocalDateTime(iso: string): string {
  return new Date(iso).toLocaleString();
}

function formatDuration(started: string, completed: string | null): string {
  if (!completed) return '—';
  const diff = Math.round(
    (new Date(completed).getTime() - new Date(started).getTime()) / 1000
  );
  if (diff < 0) return '—';
  if (diff < 60) return `${diff}s`;
  return `${Math.floor(diff / 60)}m ${diff % 60}s`;
}

function truncate(text: string | null, maxLen = 60): string {
  if (!text) return '—';
  return text.length > maxLen ? text.slice(0, maxLen) + '…' : text;
}

// ---- Status badge ----

const STATUS_STYLES: Record<string, string> = {
  success: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
  running: 'bg-yellow-100 text-yellow-800',
  interrupted: 'bg-gray-100 text-gray-600',
};

function StatusBadge({ status }: { status: string }) {
  const cls = STATUS_STYLES[status] ?? 'bg-gray-100 text-gray-600';
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${cls}`}>
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}

// ---- Triggered-by pill ----

const TRIGGER_LABELS: Record<string, string> = {
  scheduled: 'Scheduled',
  manual: 'Manual',
  backfill: 'Backfill',
};

function TriggerPill({ value }: { value: string }) {
  return (
    <span className="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium text-muted-foreground">
      {TRIGGER_LABELS[value] ?? value}
    </span>
  );
}

// ---- Toast state ----

interface Toast {
  id: number;
  message: string;
  variant: 'success' | 'error';
}

// ---- Sub-components ----

function RunHistoryTable({ runs }: { runs: IngestionRun[] }) {
  if (runs.length === 0) {
    return <p className="text-sm text-muted-foreground">No runs yet.</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-muted-foreground">
            <th className="pb-2 pr-4 text-left font-medium">Timestamp</th>
            <th className="pb-2 pr-4 text-left font-medium">Status</th>
            <th className="pb-2 pr-4 text-left font-medium">Triggered By</th>
            <th className="pb-2 pr-4 text-right font-medium">Records</th>
            <th className="pb-2 pr-4 text-left font-medium">Duration</th>
            <th className="pb-2 text-left font-medium">Error</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => (
            <tr key={run.id} className="border-b last:border-0">
              <td className="py-2 pr-4 whitespace-nowrap text-muted-foreground">
                {formatLocalDateTime(run.started_at)}
              </td>
              <td className="py-2 pr-4">
                <StatusBadge status={run.status} />
              </td>
              <td className="py-2 pr-4">
                <TriggerPill value={run.triggered_by} />
              </td>
              <td className="py-2 pr-4 text-right tabular-nums">
                {run.records_ingested ?? '—'}
              </td>
              <td className="py-2 pr-4 whitespace-nowrap">
                {formatDuration(run.started_at, run.completed_at)}
              </td>
              <td
                className="py-2 text-muted-foreground"
                title={run.error_detail ?? undefined}
              >
                {truncate(run.error_detail)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AlertBanner({ alert }: { alert: IngestionAlert }) {
  return (
    <div className="rounded-lg border border-red-500 bg-red-50 p-4 text-red-900">
      <div className="flex items-start gap-3">
        <AlertTriangle className="h-5 w-5 mt-0.5 shrink-0 text-red-600" />
        <div className="flex flex-col gap-1">
          <p className="font-semibold">Ingestion Failure</p>
          <p className="text-sm">Error: {alert.error_message}</p>
          <p className="text-xs text-red-700">
            Retries attempted: {alert.retry_count} | Failed at:{' '}
            {formatLocalDateTime(alert.failed_at)}
          </p>
        </div>
      </div>
    </div>
  );
}

// ---- Main page ----

export function IngestionPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const [toasts, setToasts] = useState<Toast[]>([]);
  const toastCounterRef = useRef(0);

  // ---- Admin guard ----
  if (user && user.role !== 'admin') {
    return (
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">Ingestion</h1>
        <p className="text-muted-foreground">You don't have permission to view this page.</p>
      </div>
    );
  }

  // ---- Toast helpers ----

  const addToast = useCallback((message: string, variant: 'success' | 'error') => {
    const id = ++toastCounterRef.current;
    setToasts((prev) => [...prev, { id, message, variant }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  }, []);

  // ---- Queries — each card has its own independent loading state ----

  const statusQuery = useIngestionStatus();
  const runsQuery = useIngestionRuns();
  const alertsQuery = useIngestionAlerts();

  // Track previous running state so we can trigger a refresh of runs + alerts
  // when a pipeline run completes (running flips from true → false).
  const prevRunningRef = useRef<boolean | null>(null);
  const currentRunning = statusQuery.data?.running ?? null;
  if (prevRunningRef.current === true && currentRunning === false) {
    queryClient.invalidateQueries({ queryKey: ingestionKeys.runs });
    queryClient.invalidateQueries({ queryKey: ingestionKeys.alerts });
  }
  prevRunningRef.current = currentRunning;

  // ---- Mutation ----

  const runNow = useRunIngestionNow();

  const handleRunNow = useCallback(async () => {
    try {
      await runNow.mutateAsync(undefined);
      addToast('Ingestion started', 'success');
    } catch (err) {
      const axiosErr = err as AxiosError;
      if (axiosErr.response?.status === 409) {
        addToast('Already running', 'error');
      } else {
        addToast('Failed to trigger ingestion', 'error');
      }
    }
  }, [runNow, addToast]);

  // ---- Derived values ----

  const activeAlert =
    (alertsQuery.data ?? []).find((a) => a.is_active) ?? null;

  // ---- Render ----

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Ingestion</h1>
        <p className="text-muted-foreground text-sm mt-1">Azure billing data pipeline</p>
      </div>

      {/* Toasts */}
      {toasts.length > 0 && (
        <div className="fixed top-4 right-4 z-50 flex flex-col gap-2">
          {toasts.map((toast) => (
            <div
              key={toast.id}
              className={`rounded-md px-4 py-3 text-sm font-medium shadow-lg transition-all ${
                toast.variant === 'success'
                  ? 'bg-green-600 text-white'
                  : 'bg-red-600 text-white'
              }`}
            >
              {toast.message}
            </div>
          ))}
        </div>
      )}

      {/* Alert banner — renders as soon as alertsQuery resolves */}
      {activeAlert && <AlertBanner alert={activeAlert} />}

      {/* Status + Run Now — renders as soon as statusQuery resolves */}
      <Card>
        <CardHeader>
          <CardTitle>Pipeline Status</CardTitle>
        </CardHeader>
        <CardContent>
          {statusQuery.isPending ? (
            <div className="flex items-center gap-4">
              <Skeleton className="h-5 w-24" />
              <Skeleton className="h-9 w-28" />
            </div>
          ) : (
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span
                  className={`h-2.5 w-2.5 rounded-full ${
                    statusQuery.data?.running ? 'bg-green-500' : 'bg-gray-400'
                  }`}
                />
                <span className="text-sm font-medium">
                  {statusQuery.data?.running ? 'Running' : 'Idle'}
                </span>
              </div>
              <Button
                onClick={handleRunNow}
                disabled={statusQuery.data?.running === true || runNow.isPending}
              >
                Run Now
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Run history — renders as soon as runsQuery resolves */}
      <Card>
        <CardHeader>
          <CardTitle>Run History</CardTitle>
        </CardHeader>
        <CardContent>
          {runsQuery.isPending ? (
            <div className="flex flex-col gap-2">
              {[...Array(3)].map((_, i) => (
                <Skeleton key={i} className="h-8 w-full" />
              ))}
            </div>
          ) : (
            <RunHistoryTable runs={runsQuery.data ?? []} />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
