import { useEffect, useMemo, useState } from 'react';
import Head from 'next/head';
import { Activity, CircleDollarSign, Gauge, RefreshCw, ShieldCheck, Zap } from 'lucide-react';
import { AppSidebar } from '@/components/app-sidebar';
import { Badge } from '@/components/ui/badge';
import { Breadcrumb, BreadcrumbItem, BreadcrumbList, BreadcrumbPage } from '@/components/ui/breadcrumb';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { SidebarInset, SidebarProvider, SidebarTrigger } from '@/components/ui/sidebar';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { aggregateEvidence, anonymizeId, buildEvidenceBadges, type EvidenceRecord, loadEvidence, parseTraceMetadata } from '@/components/CopilotChat/copilotEvidence';

export default function DashboardPage() {
  const [records, setRecords] = useState<EvidenceRecord[]>([]);
  const refresh = () => setRecords(loadEvidence().slice().reverse());
  useEffect(refresh, []);
  const metrics = useMemo(() => aggregateEvidence(records), [records]);
  const outcomes = useMemo(() => records.reduce<Record<string, number>>((counts, record) => {
    for (const badge of buildEvidenceBadges(record)) counts[badge] = (counts[badge] || 0) + 1;
    return counts;
  }, {}), [records]);

  return (
    <SidebarProvider>
      <Head><title>AI Evidence | TechX Corp</title></Head>
      <AppSidebar />
      <SidebarInset>
        <header className="flex h-16 shrink-0 items-center justify-between gap-2 border-b px-4">
          <div className="flex items-center gap-2"><SidebarTrigger className="-ml-1" /><Separator orientation="vertical" className="mr-2 h-4" /><Breadcrumb><BreadcrumbList><BreadcrumbItem><BreadcrumbPage>AI Evidence</BreadcrumbPage></BreadcrumbItem></BreadcrumbList></Breadcrumb></div>
          <Button size="sm" variant="outline" onClick={refresh}><RefreshCw className="mr-2 size-4" />Refresh</Button>
        </header>

        <main className="flex flex-1 flex-col gap-6 p-4 md:p-6">
          <div><h1 className="text-3xl font-bold tracking-tight">AI Evidence Dashboard</h1><p className="mt-1 text-muted-foreground">Live browser-session evidence from Copilot requests. Empty values stay empty; no mocked readiness.</p></div>

          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-6">
            <MetricCard icon={Activity} label="Requests" value={String(metrics.requests)} />
            <MetricCard icon={Gauge} label="p50 / p95" value={`${metrics.p50LatencyMs} / ${metrics.p95LatencyMs} ms`} />
            <MetricCard icon={CircleDollarSign} label="Cost / request" value={`$${metrics.costPerRequest.toFixed(6)}`} />
            <MetricCard icon={Zap} label="Tokens" value={String(metrics.totalTokens)} />
            <MetricCard icon={ShieldCheck} label="Cache hit rate" value={`${(metrics.cacheHitRate * 100).toFixed(0)}%`} />
            <MetricCard icon={ShieldCheck} label="Fallback rate" value={`${(metrics.fallbackRate * 100).toFixed(0)}%`} />
          </div>

          <div className="grid gap-4 lg:grid-cols-[1fr_2fr]">
            <Card>
              <CardHeader><CardTitle>Evaluation outcomes</CardTitle><CardDescription>Request-derived safety and grounding states</CardDescription></CardHeader>
              <CardContent className="space-y-2">
                {Object.keys(outcomes).length ? Object.entries(outcomes).map(([label, count]) => <div key={label} className="flex items-center justify-between rounded-lg border p-3"><span>{label}</span><Badge variant="outline">{count}</Badge></div>) : <Empty />}
              </CardContent>
            </Card>

            <Card className="overflow-hidden">
              <CardHeader><CardTitle>Recent traces</CardTitle><CardDescription>Model, surface, time, outcome, cache, latency, user and session</CardDescription></CardHeader>
              <CardContent className="overflow-x-auto p-0">
                {records.length ? <Table><TableHeader><TableRow><TableHead>Time</TableHead><TableHead>Surface / model</TableHead><TableHead>Outcome</TableHead><TableHead>Cache</TableHead><TableHead>Latency</TableHead><TableHead>Identity</TableHead><TableHead>Trace</TableHead></TableRow></TableHeader><TableBody>
                  {records.map((record, index) => {
                    const metadata = parseTraceMetadata(record.traceSteps);
                    const latency = record.traceSteps.reduce((sum, step) => sum + (step.latencyMs ?? step.latency_ms ?? 0), 0);
                    const outcome = metadata.outcome || (record.degraded ? 'fallback' : record.actionsTaken.some(action => action.succeeded) ? 'executed' : 'ok');
                    return <TableRow key={`${record.traceId || record.recordedAt}-${index}`}>
                      <TableCell className="whitespace-nowrap text-xs">{new Date(record.recordedAt).toLocaleString()}</TableCell>
                      <TableCell><div className="font-medium">{record.surface || 'Copilot'}</div><div className="text-xs text-muted-foreground">{metadata.modelId || 'not emitted'}</div></TableCell>
                      <TableCell><Badge variant={outcome === 'fallback' || outcome === 'blocked' ? 'destructive' : 'outline'}>{outcome}</Badge></TableCell>
                      <TableCell>{record.cacheStatus || 'not emitted'}</TableCell>
                      <TableCell>{latency}ms</TableCell>
                      <TableCell className="text-xs">u:{anonymizeId(record.userId)}<br />s:{anonymizeId(record.sessionId)}</TableCell>
                      <TableCell className="font-mono text-xs">{record.traceId ? `${record.traceId.slice(0, 8)}…` : 'not emitted'}</TableCell>
                    </TableRow>;
                  })}
                </TableBody></Table> : <div className="p-6"><Empty /></div>}
              </CardContent>
            </Card>
          </div>
        </main>
      </SidebarInset>
    </SidebarProvider>
  );
}

function MetricCard({ icon: Icon, label, value }: { icon: typeof Activity; label: string; value: string }) {
  return <Card><CardContent className="p-4"><div className="flex items-center gap-2 text-sm text-muted-foreground"><Icon className="size-4" />{label}</div><div className="mt-2 text-2xl font-bold">{value}</div></CardContent></Card>;
}

function Empty() {
  return <p className="text-sm text-muted-foreground">No evidence yet. Run scenarios on the Shopping Copilot page, then refresh.</p>;
}
