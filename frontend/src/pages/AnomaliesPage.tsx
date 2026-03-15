import { useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { AlertTriangle, Download, TrendingUp, ExternalLink } from 'lucide-react';
import {
  useAnomalies,
  useAnomalySummary,
  useUpdateAnomalyStatus,
  useMarkAnomalyExpected,
  useUnmarkAnomalyExpected,
  exportAnomalies,
  type Anomaly,
} from '@/services/anomaly';

// ── Color mapping constants ───────────────────────────────────────────────────

const severityDotColor: Record<string, string> = {
  critical: 'bg-red-500',
  high: 'bg-orange-500',
  medium: 'bg-blue-500',
};

const severityBadgeClass: Record<string, string> = {
  critical: 'bg-red-100 text-red-800 border border-red-200',
  high: 'bg-orange-100 text-orange-800 border border-orange-200',
  medium: 'bg-blue-100 text-blue-800 border border-blue-200',
};

const statusBadgeClass: Record<string, string> = {
  new: 'bg-slate-100 text-slate-700',
  investigating: 'bg-yellow-100 text-yellow-800',
  resolved: 'bg-green-100 text-green-800',
  dismissed: 'bg-gray-100 text-gray-500',
};

// ── AnomalyCard sub-component ─────────────────────────────────────────────────

function AnomalyCard({ anomaly }: { anomaly: Anomaly }) {
  const updateStatus = useUpdateAnomalyStatus();
  const markExpected = useMarkAnomalyExpected();
  const unmarkExpected = useUnmarkAnomalyExpected();

  const detectedDate = new Date(anomaly.detected_date + "T00:00:00").toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });

  const impactFormatted = anomaly.estimated_monthly_impact.toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  });

  const isNew = anomaly.status === 'new';
  const isInvestigating = anomaly.status === 'investigating';
  const isResolved = anomaly.status === 'resolved';
  const isDismissed = anomaly.status === 'dismissed';
  const isExpected = anomaly.expected;

  // Derive whether any mutation is in progress
  const isMutating =
    updateStatus.isPending || markExpected.isPending || unmarkExpected.isPending;

  return (
    <Card>
      <CardContent className="pt-4">
        <div className="flex items-start gap-4">
          {/* Severity dot */}
          <div className="mt-1 flex-shrink-0">
            <span
              className={`block w-3 h-3 rounded-full ${severityDotColor[anomaly.severity] ?? 'bg-gray-400'}`}
            />
          </div>

          {/* Main content */}
          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-2 mb-1">
              <span className="font-semibold text-sm">{anomaly.service_name}</span>
              <Badge className={severityBadgeClass[anomaly.severity] ?? ''}>
                {anomaly.severity.charAt(0).toUpperCase() + anomaly.severity.slice(1)}
              </Badge>
              <Badge className={statusBadgeClass[anomaly.status] ?? ''}>
                {isExpected ? 'Expected' : anomaly.status.charAt(0).toUpperCase() + anomaly.status.slice(1)}
              </Badge>
            </div>
            <p className="text-sm text-muted-foreground mb-1">{anomaly.description}</p>
            <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
              <span>Resource Group: {anomaly.resource_group || '—'}</span>
              <span>Detected: {detectedDate}</span>
            </div>

            {/* Context-sensitive action buttons */}
            <div className="flex flex-wrap gap-2 mt-3">
              {/* New status: show all three primary actions */}
              {isNew && (
                <>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={isMutating}
                    onClick={() => updateStatus.mutate({ id: anomaly.id, status: 'investigating' })}
                  >
                    Investigate
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={isMutating}
                    onClick={() => updateStatus.mutate({ id: anomaly.id, status: 'dismissed' })}
                  >
                    Dismiss
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={isMutating}
                    onClick={() => markExpected.mutate({ id: anomaly.id })}
                  >
                    Mark as Expected
                  </Button>
                </>
              )}

              {/* Investigating status: mark resolved or revert */}
              {isInvestigating && (
                <>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={isMutating}
                    onClick={() => updateStatus.mutate({ id: anomaly.id, status: 'resolved' })}
                  >
                    Mark as Resolved
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={isMutating}
                    onClick={() => updateStatus.mutate({ id: anomaly.id, status: 'new' })}
                  >
                    Revert to New
                  </Button>
                </>
              )}

              {/* Dismissed but NOT expected: show revert */}
              {isDismissed && !isExpected && (
                <Button
                  variant="outline"
                  size="sm"
                  disabled={isMutating}
                  onClick={() => updateStatus.mutate({ id: anomaly.id, status: 'new' })}
                >
                  Revert to New
                </Button>
              )}

              {/* Expected (dismissed + expected=true): show unmark */}
              {isExpected && (
                <Button
                  variant="outline"
                  size="sm"
                  disabled={isMutating}
                  onClick={() => unmarkExpected.mutate({ id: anomaly.id })}
                >
                  Unmark Expected
                </Button>
              )}

              {/* Resolved: allow revert to new */}
              {isResolved && (
                <Button
                  variant="outline"
                  size="sm"
                  disabled={isMutating}
                  onClick={() => updateStatus.mutate({ id: anomaly.id, status: 'new' })}
                >
                  Revert to New
                </Button>
              )}

              {/* View Resources always visible */}
              <Button
                variant="ghost"
                size="sm"
                disabled
                className="text-muted-foreground"
              >
                <ExternalLink className="mr-1 h-3 w-3" />
                View Resources
              </Button>
            </div>
          </div>

          {/* Estimated impact */}
          <div className="flex-shrink-0 text-right">
            <p className="text-sm font-semibold text-red-600">+{impactFormatted}</p>
            <p className="text-xs text-muted-foreground">est. monthly</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ── Main page component ───────────────────────────────────────────────────────

export default function AnomaliesPage() {
  const [selectedSeverity, setSelectedSeverity] = useState<string>('all');
  const [selectedService, setSelectedService] = useState<string>('all');
  const [selectedResourceGroup, setSelectedResourceGroup] = useState<string>('all');
  const [isExporting, setIsExporting] = useState(false);

  // Unfiltered list — used to derive filter options
  const { data: allAnomalies = [] } = useAnomalies();

  // Filtered list — used for display
  const { data: anomalies = [], isLoading } = useAnomalies({
    severity: selectedSeverity !== 'all' ? selectedSeverity : undefined,
    service_name: selectedService !== 'all' ? selectedService : undefined,
    resource_group: selectedResourceGroup !== 'all' ? selectedResourceGroup : undefined,
  });

  const { data: summary } = useAnomalySummary();

  const allServices = [...new Set(allAnomalies.map(a => a.service_name))].sort();
  const allResourceGroups = [...new Set(allAnomalies.map(a => a.resource_group))].sort();

  const handleExport = async () => {
    setIsExporting(true);
    try {
      await exportAnomalies({
        severity: selectedSeverity !== 'all' ? selectedSeverity : undefined,
        service_name: selectedService !== 'all' ? selectedService : undefined,
      });
    } finally {
      setIsExporting(false);
    }
  };

  const severityBreakdownParts = [
    (summary?.critical_count ?? 0) > 0 ? { label: `${summary!.critical_count} Critical`, cls: 'text-red-600' } : null,
    (summary?.high_count ?? 0) > 0 ? { label: `${summary!.high_count} High`, cls: 'text-orange-500' } : null,
    (summary?.medium_count ?? 0) > 0 ? { label: `${summary!.medium_count} Medium`, cls: 'text-blue-600' } : null,
  ].filter(Boolean) as { label: string; cls: string }[];

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Anomaly Detection</h1>
          <p className="text-sm text-muted-foreground">
            Spending deviations from 30-day rolling baseline
          </p>
        </div>
        <Button onClick={handleExport} disabled={isExporting} variant="outline">
          <Download className="mr-2 h-4 w-4" />
          {isExporting ? 'Exporting...' : 'Export Report'}
        </Button>
      </div>

      {/* 4 KPI Summary Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {/* Active Anomalies */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <AlertTriangle className="h-4 w-4" />
              Active Anomalies
            </CardTitle>
          </CardHeader>
          <CardContent>
            {summary === undefined ? (
              <div className="space-y-1">
                <Skeleton className="h-8 w-12" />
                <Skeleton className="h-3 w-24" />
              </div>
            ) : (
              <>
                <p className={`text-2xl font-bold ${(summary.active_count ?? 0) > 0 ? 'text-destructive' : 'text-foreground'}`}>
                  {summary.active_count ?? 0}
                </p>
                <p className="text-xs font-medium mt-0.5 truncate">
                  {severityBreakdownParts.length > 0
                    ? severityBreakdownParts.map((p, i) => (
                        <span key={p.label}>
                          {i > 0 && <span className="text-muted-foreground"> · </span>}
                          <span className={p.cls}>{p.label}</span>
                        </span>
                      ))
                    : <span className="text-muted-foreground">No active anomalies</span>}
                </p>
              </>
            )}
          </CardContent>
        </Card>

        {/* Potential Impact */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <TrendingUp className="h-4 w-4" />
              Potential Impact
            </CardTitle>
          </CardHeader>
          <CardContent>
            {summary === undefined ? (
              <Skeleton className="h-8 w-28" />
            ) : (
              <p className="text-2xl font-bold text-red-600">
                {(summary.total_potential_impact ?? 0).toLocaleString('en-US', {
                  style: 'currency',
                  currency: 'USD',
                  minimumFractionDigits: 0,
                  maximumFractionDigits: 0,
                })}
              </p>
            )}
          </CardContent>
        </Card>

        {/* Resolved This Month */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Resolved This Month
            </CardTitle>
          </CardHeader>
          <CardContent>
            {summary === undefined ? (
              <Skeleton className="h-8 w-12" />
            ) : (
              <p className="text-2xl font-bold">
                {summary.resolved_this_month ?? 0}
              </p>
            )}
          </CardContent>
        </Card>

        {/* Detection Accuracy */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Detection Accuracy
            </CardTitle>
          </CardHeader>
          <CardContent>
            {summary === undefined ? (
              <Skeleton className="h-8 w-16" />
            ) : (
              <p className="text-2xl font-bold">
                {summary.detection_accuracy != null
                  ? `${summary.detection_accuracy.toFixed(1)}%`
                  : 'N/A'}
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Filter row */}
      <div className="flex flex-wrap gap-3">
        <Select value={selectedService} onValueChange={setSelectedService}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="All Services" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Services</SelectItem>
            {allServices.map(service => (
              <SelectItem key={service} value={service}>
                {service}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={selectedResourceGroup} onValueChange={setSelectedResourceGroup}>
          <SelectTrigger className="w-[200px]">
            <SelectValue placeholder="All Resource Groups" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Resource Groups</SelectItem>
            {allResourceGroups.map(rg => (
              <SelectItem key={rg} value={rg}>
                {rg}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={selectedSeverity} onValueChange={setSelectedSeverity}>
          <SelectTrigger className="w-[160px]">
            <SelectValue placeholder="All Severities" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Severities</SelectItem>
            <SelectItem value="critical">Critical</SelectItem>
            <SelectItem value="high">High</SelectItem>
            <SelectItem value="medium">Medium</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Section header with severity summary */}
      <div className="flex items-center gap-3">
        <h2 className="text-lg font-semibold">Anomalies</h2>
        <span className="text-sm font-medium truncate">
          {severityBreakdownParts.length > 0
            ? severityBreakdownParts.map((p, i) => (
                <span key={p.label}>
                  {i > 0 && <span className="text-muted-foreground"> · </span>}
                  <span className={p.cls}>{p.label}</span>
                </span>
              ))
            : <span className="text-muted-foreground">No active anomalies</span>}
        </span>
      </div>

      {/* Anomaly card list */}
      {isLoading ? (
        <div className="space-y-3">
          {[1, 2, 3].map(i => (
            <Skeleton key={i} className="h-32 w-full" />
          ))}
        </div>
      ) : anomalies.length === 0 ? (
        <div className="py-12 text-center text-muted-foreground">
          <AlertTriangle className="mx-auto mb-3 h-10 w-10 opacity-30" />
          <p>No anomalies detected for the selected filters.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {anomalies.map(anomaly => (
            <AnomalyCard key={anomaly.id} anomaly={anomaly} />
          ))}
        </div>
      )}

      {/* Detection Configuration panel */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Detection Configuration</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3 text-sm">
            <div>
              <p className="text-muted-foreground">Baseline Period</p>
              <p className="font-medium">30 days rolling average</p>
            </div>
            <div>
              <p className="text-muted-foreground">Minimum Deviation</p>
              <p className="font-medium">20% above baseline</p>
            </div>
            <div>
              <p className="text-muted-foreground">Severity Thresholds</p>
              <p className="font-medium">Critical &ge; $1,000 &middot; High &ge; $500 &middot; Medium &ge; $100</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
