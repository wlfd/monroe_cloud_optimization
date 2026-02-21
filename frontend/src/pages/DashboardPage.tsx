import { useState } from "react";
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
import { useSpendSummary, useSpendTrend } from "@/services/cost";

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
  const summaryQuery = useSpendSummary();
  const trendQuery = useSpendTrend(days);

  const trendData = trendQuery.data ?? [];

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>

      {/* KPI Cards */}
      {summaryQuery.isError && (
        <p className="text-destructive">Failed to load cost data</p>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
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
            <div className="min-h-[300px] flex items-center justify-center">
              <p className="text-muted-foreground">Loading chart...</p>
            </div>
          ) : (
            <ChartContainer config={chartConfig} className="min-h-[300px] w-full">
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
    </div>
  );
}
