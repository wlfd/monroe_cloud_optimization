import { useState } from "react";
import { Link } from "react-router-dom";
import { Area, AreaChart, CartesianGrid, XAxis, YAxis } from "recharts";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart";
import type { ChartConfig } from "@/components/ui/chart";
import {
  Tabs,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { AlertTriangle } from "lucide-react";
import { useSpendSummary, useSpendTrend, useSpendBreakdown, useTopResources } from "@/services/cost";
import { useAnomalySummary } from "@/services/anomaly";
import api from "@/services/api";

const chartConfig = {
  total_cost: {
    label: "Daily Spend",
    color: "hsl(var(--chart-1))",
  },
} satisfies ChartConfig;

function formatCurrency(value: number): string {
  return `$${value.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function MomDeltaBadge({ delta }: { delta: number | null }) {
  if (delta === null) {
    return <span className="text-sm text-muted-foreground">N/A</span>;
  }
  const isDecrease = delta < 0;
  const arrow = isDecrease ? "↓" : "↑";
  const colorClass = isDecrease ? "text-green-600" : "text-red-600";
  const sign = delta > 0 ? "+" : "";
  return (
    <span className={`text-sm font-medium ${colorClass}`}>
      {arrow} {sign}{delta.toFixed(1)}% vs prior month
    </span>
  );
}

export function DashboardPage() {
  const [days, setDays] = useState<number>(30);
  const [dimension, setDimension] = useState<string>("service_name");
  const [isExporting, setIsExporting] = useState<boolean>(false);

  const summaryQuery = useSpendSummary();
  const trendQuery = useSpendTrend(days);
  const breakdownQuery = useSpendBreakdown(dimension, days);
  const topResourcesQuery = useTopResources(days);
  const anomalySummary = useAnomalySummary();

  const trendData = trendQuery.data ?? [];

  const handleExport = async () => {
    setIsExporting(true);
    try {
      const response = await api.get("/costs/export", {
        params: { dimension, days },
        responseType: "blob",
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `cost-breakdown-${dimension}-${days}d.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>

      {/* KPI Cards */}
      {summaryQuery.isError && (
        <p className="text-destructive">Failed to load cost data</p>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {/* Month-to-Date Spend */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Month-to-Date Spend
            </CardTitle>
          </CardHeader>
          <CardContent>
            {summaryQuery.isLoading ? (
              <div className="animate-pulse bg-muted rounded h-8 w-32" />
            ) : (
              <p className="text-2xl font-bold">
                {summaryQuery.data
                  ? formatCurrency(summaryQuery.data.mtd_total)
                  : "—"}
              </p>
            )}
          </CardContent>
        </Card>

        {/* Projected Month-End */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Projected Month-End
            </CardTitle>
          </CardHeader>
          <CardContent>
            {summaryQuery.isLoading ? (
              <div className="animate-pulse bg-muted rounded h-8 w-32" />
            ) : (
              <>
                <p className="text-2xl font-bold">
                  {summaryQuery.data
                    ? formatCurrency(summaryQuery.data.projected_month_end)
                    : "—"}
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  Linear projection
                </p>
              </>
            )}
          </CardContent>
        </Card>

        {/* Prior Month + MoM Delta */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Prior Month
            </CardTitle>
          </CardHeader>
          <CardContent>
            {summaryQuery.isLoading ? (
              <div className="animate-pulse bg-muted rounded h-8 w-32" />
            ) : (
              <>
                <p className="text-2xl font-bold">
                  {summaryQuery.data
                    ? formatCurrency(summaryQuery.data.prior_month_total)
                    : "—"}
                </p>
                {summaryQuery.data && (
                  <div className="mt-1">
                    <MomDeltaBadge delta={summaryQuery.data.mom_delta_pct} />
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>

        {/* Active Anomalies */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <AlertTriangle className="h-4 w-4" />
              Active Anomalies
            </CardTitle>
          </CardHeader>
          <CardContent>
            {anomalySummary.isLoading ? (
              <div className="space-y-1">
                <Skeleton className="h-8 w-12" />
                <Skeleton className="h-3 w-24" />
              </div>
            ) : (
              <>
                <p className={`text-2xl font-bold ${(anomalySummary.data?.active_count ?? 0) > 0 ? "text-destructive" : "text-foreground"}`}>
                  {anomalySummary.data?.active_count ?? 0}
                </p>
                {anomalySummary.data && (
                  <p className="text-xs font-medium mt-0.5 truncate">
                    {(() => {
                      const parts = [
                        (anomalySummary.data.critical_count ?? 0) > 0 ? { label: `${anomalySummary.data.critical_count} Critical`, cls: "text-red-600" } : null,
                        (anomalySummary.data.high_count ?? 0) > 0 ? { label: `${anomalySummary.data.high_count} High`, cls: "text-orange-500" } : null,
                        (anomalySummary.data.medium_count ?? 0) > 0 ? { label: `${anomalySummary.data.medium_count} Medium`, cls: "text-blue-600" } : null,
                      ].filter(Boolean) as { label: string; cls: string }[];
                      return parts.length > 0
                        ? parts.map((p, i) => (
                            <span key={p.label}>
                              {i > 0 && <span className="text-muted-foreground"> · </span>}
                              <span className={p.cls}>{p.label}</span>
                            </span>
                          ))
                        : <span className="text-muted-foreground">No active anomalies</span>;
                    })()}
                  </p>
                )}
                <Link
                  to="/anomalies"
                  className="text-xs text-muted-foreground hover:underline hover:text-foreground transition-colors"
                >
                  View anomalies →
                </Link>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Trend Chart */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-base font-semibold">
              Daily Spend Trend
            </CardTitle>
            <Tabs
              defaultValue="30"
              onValueChange={(v) => setDays(Number(v))}
            >
              <TabsList>
                <TabsTrigger value="30">30d</TabsTrigger>
                <TabsTrigger value="60">60d</TabsTrigger>
                <TabsTrigger value="90">90d</TabsTrigger>
              </TabsList>
            </Tabs>
          </div>
        </CardHeader>
        <CardContent>
          {trendQuery.isLoading ? (
            <div className="h-[180px] flex items-center justify-center">
              <p className="text-muted-foreground">Loading chart...</p>
            </div>
          ) : (
            <ChartContainer config={chartConfig} className="h-[180px] w-full">
              <AreaChart data={trendData}>
                <CartesianGrid vertical={false} />
                <XAxis
                  dataKey="usage_date"
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={(v) => {
                    const d = new Date(v + "T00:00:00");
                    return d.toLocaleDateString("en-US", {
                      month: "short",
                      day: "numeric",
                    });
                  }}
                />
                <YAxis
                  tickFormatter={(v) => `$${Number(v).toLocaleString()}`}
                  width={80}
                />
                <ChartTooltip content={<ChartTooltipContent />} />
                <Area
                  dataKey="total_cost"
                  fill="var(--color-total_cost)"
                  stroke="var(--color-total_cost)"
                  fillOpacity={0.2}
                  connectNulls={true}
                />
              </AreaChart>
            </ChartContainer>
          )}
        </CardContent>
      </Card>

      {/* Cost Breakdown */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between gap-2">
            <CardTitle className="text-base font-semibold">
              Cost Breakdown
            </CardTitle>
            <div className="flex items-center gap-2">
              <Select value={dimension} onValueChange={setDimension}>
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="Dimension" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="service_name">Service</SelectItem>
                  <SelectItem value="resource_group">Resource Group</SelectItem>
                  <SelectItem value="region">Region</SelectItem>
                  <SelectItem value="tag">Tag</SelectItem>
                </SelectContent>
              </Select>
              <Button
                variant="outline"
                size="sm"
                onClick={handleExport}
                disabled={isExporting}
              >
                {isExporting ? "Exporting..." : "Export CSV"}
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Dimension</TableHead>
                <TableHead className="text-right">Total Cost (USD)</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {breakdownQuery.data && breakdownQuery.data.length > 0 ? (
                breakdownQuery.data.map((item) => (
                  <TableRow key={item.dimension_value ?? "(untagged)"}>
                    <TableCell>{item.dimension_value || "(untagged)"}</TableCell>
                    <TableCell className="text-right font-mono">
                      ${item.total_cost.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={2} className="text-center text-muted-foreground">
                    {breakdownQuery.isLoading ? "Loading..." : "No cost data for this period"}
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Top 10 Resources */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base font-semibold">
            Top 10 Most Expensive Resources
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            Last {days} days
          </p>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Resource</TableHead>
                <TableHead>Service</TableHead>
                <TableHead>Resource Group</TableHead>
                <TableHead className="text-right">Total Cost (USD)</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {topResourcesQuery.data && topResourcesQuery.data.length > 0 ? (
                topResourcesQuery.data.map((resource) => (
                  <TableRow key={resource.resource_id || resource.resource_name}>
                    <TableCell
                      className="font-medium max-w-[200px] truncate"
                      title={resource.resource_name}
                    >
                      {resource.resource_name || resource.resource_id || "(unknown)"}
                    </TableCell>
                    <TableCell>{resource.service_name}</TableCell>
                    <TableCell>{resource.resource_group}</TableCell>
                    <TableCell className="text-right font-mono">
                      ${resource.total_cost.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-muted-foreground">
                    {topResourcesQuery.isLoading
                      ? "Loading..."
                      : "No resource-level data available. Run ingestion to populate resource data."}
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
