import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import {
  Card,
  CardContent,
  CardHeader,
} from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { AlertCircle, ArrowRight, Loader2, Lightbulb } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import {
  useRecommendations,
  useRecommendationSummary,
  triggerRecommendations,
  type Recommendation,
  type RecommendationFilters,
} from '@/services/recommendation';

// ── Category badge colors ─────────────────────────────────────────────────────

const CATEGORY_VARIANT: Record<string, string> = {
  'right-sizing': 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
  idle: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
  reserved: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
  storage: 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200',
};

const CATEGORY_LABEL: Record<string, string> = {
  'right-sizing': 'Right-Sizing',
  idle: 'Idle',
  reserved: 'Reserved',
  storage: 'Storage',
};

function confidenceVariant(score: number): string {
  if (score >= 80) return 'bg-green-100 text-green-800';
  if (score >= 60) return 'bg-yellow-100 text-yellow-800';
  return 'bg-gray-100 text-gray-700';
}

// ── RecommendationCard ────────────────────────────────────────────────────────

function RecommendationCard({ rec }: { rec: Recommendation }) {
  const recommendedCost = rec.current_monthly_cost - rec.estimated_monthly_savings;

  return (
    <Card className="mb-4">
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <p className="truncate font-semibold text-base">{rec.resource_name}</p>
            <p className="text-sm text-muted-foreground truncate">{rec.resource_group}</p>
          </div>
          <div className="flex flex-shrink-0 gap-2 pt-0.5">
            <span
              className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${CATEGORY_VARIANT[rec.category] ?? 'bg-gray-100 text-gray-700'}`}
            >
              {CATEGORY_LABEL[rec.category] ?? rec.category}
            </span>
            <span
              className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${confidenceVariant(rec.confidence_score)}`}
            >
              {rec.confidence_score >= 80 ? 'High' : rec.confidence_score >= 60 ? 'Medium' : 'Low'} Confidence
            </span>
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-0 space-y-3">
        {/* Current → Recommended comparison panel */}
        <div className="flex items-center gap-3 rounded-lg border bg-muted/40 p-3">
          <div className="flex-1 text-center">
            <p className="text-xs text-muted-foreground mb-1">Current</p>
            <p className="text-lg font-bold">${rec.current_monthly_cost.toFixed(0)}<span className="text-xs font-normal text-muted-foreground">/mo</span></p>
          </div>
          <ArrowRight className="h-5 w-5 text-muted-foreground flex-shrink-0" />
          <div className="flex-1 text-center">
            <p className="text-xs text-muted-foreground mb-1">Recommended</p>
            <p className="text-lg font-bold text-green-600">${Math.max(0, recommendedCost).toFixed(0)}<span className="text-xs font-normal text-muted-foreground">/mo</span></p>
          </div>
        </div>

        {/* Savings and confidence */}
        <div className="flex items-center justify-between text-sm">
          <span className="font-medium text-green-600">
            Est. savings: ${rec.estimated_monthly_savings.toFixed(0)}/mo
          </span>
          <span className="text-muted-foreground">
            Confidence: {rec.confidence_score}%
          </span>
        </div>

        {/* LLM explanation — always visible */}
        <p className="text-sm text-muted-foreground leading-relaxed">{rec.explanation}</p>
      </CardContent>
    </Card>
  );
}

// ── Loading skeletons ─────────────────────────────────────────────────────────

function RecommendationSkeleton() {
  return (
    <Card className="mb-4">
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 space-y-2">
            <Skeleton className="h-5 w-2/3" />
            <Skeleton className="h-4 w-1/2" />
          </div>
          <div className="flex gap-2">
            <Skeleton className="h-5 w-20 rounded-full" />
            <Skeleton className="h-5 w-24 rounded-full" />
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-0 space-y-3">
        <Skeleton className="h-20 w-full rounded-lg" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-4/5" />
        <Skeleton className="h-4 w-3/4" />
      </CardContent>
    </Card>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function RecommendationsPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [filters, setFilters] = useState<RecommendationFilters>({});
  const [triggering, setTriggering] = useState(false);

  const summary = useRecommendationSummary();
  const recommendations = useRecommendations(filters);

  const handleTrigger = async () => {
    setTriggering(true);
    try {
      await triggerRecommendations();
      // Refetch after a short delay to allow the background job to start
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ['recommendations'] });
        queryClient.invalidateQueries({ queryKey: ['recommendation-summary'] });
        setTriggering(false);
      }, 3000);
    } catch {
      setTriggering(false);
    }
  };

  const summaryData = summary.data;
  const recs = recommendations.data ?? [];
  const isLoading = recommendations.isLoading;

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <div className="flex items-center gap-2">
        <Lightbulb className="h-6 w-6 text-yellow-500" />
        <h1 className="text-2xl font-bold">Recommendations</h1>
      </div>

      {/* Summary stat row */}
      {summaryData && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-7">
          <Card className="col-span-2 sm:col-span-1 lg:col-span-2 bg-green-50 dark:bg-green-950 border-green-200">
            <CardContent className="p-4">
              <p className="text-xs text-muted-foreground">Potential Monthly Savings</p>
              <p className="text-2xl font-bold text-green-700 dark:text-green-400">
                ${summaryData.potential_monthly_savings.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <p className="text-xs text-muted-foreground">Total</p>
              <p className="text-2xl font-bold">{summaryData.total_count}</p>
            </CardContent>
          </Card>
          {(['right-sizing', 'idle', 'reserved', 'storage'] as const).map((cat) => (
            <Card key={cat}>
              <CardContent className="p-4">
                <p className="text-xs text-muted-foreground">{CATEGORY_LABEL[cat]}</p>
                <p className="text-2xl font-bold">{summaryData.by_category[cat] ?? 0}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Daily limit reached banner */}
      {summaryData?.daily_limit_reached && (
        <div className="flex items-center gap-2 rounded-md border border-yellow-200 bg-yellow-50 px-4 py-3 text-sm text-yellow-800">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>Daily recommendation limit reached. New recommendations will generate tomorrow.</span>
        </div>
      )}

      {/* Filter bar */}
      <div className="flex flex-wrap gap-3">
        <Select
          value={filters.category ?? 'all'}
          onValueChange={(v) => setFilters((f) => ({ ...f, category: v === 'all' ? undefined : v }))}
        >
          <SelectTrigger className="w-40">
            <SelectValue placeholder="Type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Types</SelectItem>
            <SelectItem value="right-sizing">Right-Sizing</SelectItem>
            <SelectItem value="idle">Idle</SelectItem>
            <SelectItem value="reserved">Reserved</SelectItem>
            <SelectItem value="storage">Storage</SelectItem>
          </SelectContent>
        </Select>

        <Select
          value={filters.min_savings !== undefined ? String(filters.min_savings) : 'any'}
          onValueChange={(v) =>
            setFilters((f) => ({ ...f, min_savings: v === 'any' ? undefined : Number(v) }))
          }
        >
          <SelectTrigger className="w-40">
            <SelectValue placeholder="Min Savings" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="any">Any Savings</SelectItem>
            <SelectItem value="100">$100+/mo</SelectItem>
            <SelectItem value="500">$500+/mo</SelectItem>
            <SelectItem value="1000">$1,000+/mo</SelectItem>
          </SelectContent>
        </Select>

        <Select
          value={filters.min_confidence !== undefined ? String(filters.min_confidence) : 'any'}
          onValueChange={(v) =>
            setFilters((f) => ({ ...f, min_confidence: v === 'any' ? undefined : Number(v) }))
          }
        >
          <SelectTrigger className="w-44">
            <SelectValue placeholder="Confidence" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="any">Any Confidence</SelectItem>
            <SelectItem value="70">70%+ Confidence</SelectItem>
            <SelectItem value="80">80%+ Confidence</SelectItem>
            <SelectItem value="90">90%+ Confidence</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Card list */}
      {isLoading ? (
        <>
          <RecommendationSkeleton />
          <RecommendationSkeleton />
          <RecommendationSkeleton />
        </>
      ) : recs.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16 text-center gap-4">
            <Lightbulb className="h-12 w-12 text-muted-foreground/40" />
            <div>
              <p className="text-lg font-medium text-muted-foreground">No recommendations yet</p>
              <p className="text-sm text-muted-foreground mt-1">
                Recommendations are generated daily at 02:00 UTC. Run manually to generate now.
              </p>
            </div>
            {user?.role === 'admin' && (
              <Button onClick={handleTrigger} disabled={triggering}>
                {triggering ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                    Generating...
                  </>
                ) : (
                  'Generate Recommendations'
                )}
              </Button>
            )}
          </CardContent>
        </Card>
      ) : (
        <div>
          <p className="text-sm text-muted-foreground mb-4">
            {recs.length} recommendation{recs.length !== 1 ? 's' : ''}
          </p>
          {recs.map((rec) => (
            <RecommendationCard key={rec.id} rec={rec} />
          ))}
        </div>
      )}
    </div>
  );
}
