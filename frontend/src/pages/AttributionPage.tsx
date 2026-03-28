import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Download, ChevronDown, ChevronRight } from "lucide-react";
import {
  useAttribution,
  useAttributionBreakdown,
  exportAttribution,
  type TenantAttribution,
} from "@/services/attribution";

// ── Month names ───────────────────────────────────────────────────────────────

const MONTH_NAMES = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

// ── TenantBreakdownRow sub-component ─────────────────────────────────────────

function TenantBreakdownRow({
  tenantId,
  year,
  month,
}: {
  tenantId: string;
  year: number;
  month: number;
}) {
  const { data: breakdown, isPending } = useAttributionBreakdown(tenantId, year, month);

  if (isPending) {
    return (
      <div className="p-4 space-y-2">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-4/5" />
        <Skeleton className="h-4 w-3/5" />
      </div>
    );
  }

  if (!breakdown || breakdown.length === 0) {
    return <div className="p-4 text-sm text-muted-foreground">No breakdown data available.</div>;
  }

  return (
    <div className="p-4">
      <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
        Cost by Service
      </p>
      <div className="space-y-1">
        {breakdown.map((item) => (
          <div key={item.service_name} className="flex justify-between text-sm">
            <span className="text-muted-foreground">{item.service_name}</span>
            <span className="font-medium tabular-nums">
              $
              {item.total_cost.toLocaleString("en-US", {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Sort types ────────────────────────────────────────────────────────────────

type SortKey = "total_cost" | "pct_of_total" | "mom_delta_usd";
type SortDir = "asc" | "desc";

function sortAttributions(
  items: TenantAttribution[],
  key: SortKey,
  dir: SortDir
): TenantAttribution[] {
  return [...items].sort((a, b) => {
    const aVal = a[key] ?? 0;
    const bVal = b[key] ?? 0;
    const cmp = aVal < bVal ? -1 : aVal > bVal ? 1 : 0;
    return dir === "asc" ? cmp : -cmp;
  });
}

// ── Main page component ───────────────────────────────────────────────────────

export default function AttributionPage() {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("total_cost");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [isExporting, setIsExporting] = useState(false);

  const { data: attributions = [], isLoading } = useAttribution(year, month);

  // ── Derived summary stats ─────────────────────────────────────────────────

  const totalAttributed = attributions
    .filter((t) => t.tenant_id !== "UNALLOCATED")
    .reduce((sum, t) => sum + t.total_cost, 0);

  const unallocatedRow = attributions.find((t) => t.tenant_id === "UNALLOCATED");
  const unallocatedCost = unallocatedRow?.total_cost ?? 0;

  const activeTenants = attributions.filter((t) => t.tenant_id !== "UNALLOCATED").length;

  // ── Sorting ───────────────────────────────────────────────────────────────

  const sorted = sortAttributions(attributions, sortKey, sortDir);

  function handleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  function toggleExpand(tenantId: string) {
    setExpandedId((prev) => (prev === tenantId ? null : tenantId));
  }

  // ── Export ────────────────────────────────────────────────────────────────

  const handleExport = async () => {
    setIsExporting(true);
    try {
      await exportAttribution(year, month);
    } catch (err) {
      console.error("Attribution export failed:", err);
    } finally {
      setIsExporting(false);
    }
  };

  // ── Year options: current year and 2 prior ────────────────────────────────

  const currentYear = now.getFullYear();
  const yearOptions = [currentYear, currentYear - 1, currentYear - 2];

  // ── Sort indicator helper ─────────────────────────────────────────────────

  function SortIndicator({ col }: { col: SortKey }) {
    if (sortKey !== col) return <span className="ml-1 text-muted-foreground opacity-40">↕</span>;
    return <span className="ml-1">{sortDir === "asc" ? "↑" : "↓"}</span>;
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Cost Attribution</h1>
          <p className="text-sm text-muted-foreground">
            Per-tenant cloud spend for {MONTH_NAMES[month - 1]} {year}
          </p>
        </div>
        <Button onClick={handleExport} disabled={isExporting} variant="outline">
          <Download className="mr-2 h-4 w-4" />
          {isExporting ? "Exporting..." : "Export CSV"}
        </Button>
      </div>

      {/* Month picker row */}
      <div className="flex flex-wrap gap-3 items-center">
        <Select value={String(month)} onValueChange={(v) => setMonth(Number(v))}>
          <SelectTrigger className="w-[160px]">
            <SelectValue placeholder="Month" />
          </SelectTrigger>
          <SelectContent>
            {MONTH_NAMES.map((name, i) => (
              <SelectItem key={i + 1} value={String(i + 1)}>
                {name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={String(year)} onValueChange={(v) => setYear(Number(v))}>
          <SelectTrigger className="w-[120px]">
            <SelectValue placeholder="Year" />
          </SelectTrigger>
          <SelectContent>
            {yearOptions.map((y) => (
              <SelectItem key={y} value={String(y)}>
                {y}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Summary stat row */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-card border rounded-lg p-4">
          <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">
            Total Attributed
          </p>
          <p className="text-xl font-bold">
            $
            {totalAttributed.toLocaleString("en-US", {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            })}
          </p>
        </div>
        <div className="bg-card border rounded-lg p-4">
          <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">Unallocated</p>
          <p className="text-xl font-bold">
            $
            {unallocatedCost.toLocaleString("en-US", {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            })}
          </p>
        </div>
        <div className="bg-card border rounded-lg p-4">
          <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">
            Active Tenants
          </p>
          <p className="text-xl font-bold">{activeTenants}</p>
        </div>
      </div>

      {/* Attribution table */}
      <Card>
        <CardHeader>
          <CardTitle>
            Attribution by Tenant — {MONTH_NAMES[month - 1]} {year}
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-6 space-y-3">
              {[1, 2, 3, 4, 5].map((i) => (
                <Skeleton key={i} className="h-8 w-full" />
              ))}
            </div>
          ) : sorted.length === 0 ? (
            <div className="py-12 text-center text-muted-foreground px-6">
              <p>
                No attribution data available for this period. Run attribution or check ingestion
                status.
              </p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-8" />
                  <TableHead>Tenant</TableHead>
                  <TableHead
                    className="cursor-pointer select-none"
                    onClick={() => handleSort("total_cost")}
                  >
                    Monthly Cost
                    <SortIndicator col="total_cost" />
                  </TableHead>
                  <TableHead
                    className="cursor-pointer select-none"
                    onClick={() => handleSort("pct_of_total")}
                  >
                    % of Total
                    <SortIndicator col="pct_of_total" />
                  </TableHead>
                  <TableHead
                    className="cursor-pointer select-none"
                    onClick={() => handleSort("mom_delta_usd")}
                  >
                    MoM Change
                    <SortIndicator col="mom_delta_usd" />
                  </TableHead>
                  <TableHead>Top Category</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sorted.map((tenant) => (
                  <>
                    <TableRow
                      key={tenant.tenant_id}
                      onClick={() => toggleExpand(tenant.tenant_id)}
                      className="cursor-pointer hover:bg-muted/50"
                    >
                      <TableCell className="py-2">
                        {expandedId === tenant.tenant_id ? (
                          <ChevronDown className="h-4 w-4 text-muted-foreground" />
                        ) : (
                          <ChevronRight className="h-4 w-4 text-muted-foreground" />
                        )}
                      </TableCell>
                      <TableCell>
                        <span className="font-medium">
                          {tenant.display_name ?? tenant.tenant_id}
                        </span>
                        {tenant.tenant_id !== "UNALLOCATED" &&
                          (tenant as TenantAttribution & { is_new?: boolean }).is_new && (
                            <Badge variant="secondary" className="ml-2">
                              New
                            </Badge>
                          )}
                        {tenant.tenant_id === "UNALLOCATED" && (
                          <Badge variant="outline" className="ml-2">
                            Unallocated
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell className="tabular-nums">
                        $
                        {tenant.total_cost.toLocaleString("en-US", {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 2,
                        })}
                      </TableCell>
                      <TableCell className="tabular-nums">
                        {tenant.pct_of_total.toFixed(1)}%
                      </TableCell>
                      <TableCell className="tabular-nums">
                        {tenant.mom_delta_usd === null
                          ? "—"
                          : (tenant.mom_delta_usd >= 0 ? "+" : "") +
                            "$" +
                            tenant.mom_delta_usd.toLocaleString("en-US", {
                              minimumFractionDigits: 2,
                              maximumFractionDigits: 2,
                            })}
                      </TableCell>
                      <TableCell>{tenant.top_service_category ?? "—"}</TableCell>
                    </TableRow>
                    {expandedId === tenant.tenant_id && (
                      <TableRow key={`${tenant.tenant_id}-breakdown`}>
                        <TableCell colSpan={6} className="bg-muted/20 p-0">
                          <TenantBreakdownRow
                            tenantId={tenant.tenant_id}
                            year={year}
                            month={month}
                          />
                        </TableCell>
                      </TableRow>
                    )}
                  </>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
