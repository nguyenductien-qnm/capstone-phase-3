import Link from 'next/link';
import { Activity, BrainCircuit, DatabaseZap, ShieldCheck } from 'lucide-react';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

const mandates = [
  {
    id: '14',
    title: 'AI evaluation & grounding',
    icon: ShieldCheck,
    status: 'Verified',
    summary: 'Contradiction-capable NLI checks, grounded citations and replayable Cohen’s κ.',
    proof: 'Entailment / contradiction gate · κ replay artifact · source citations',
  },
  {
    id: '23',
    title: 'Caching & memory',
    icon: DatabaseZap,
    status: 'Ready to deploy',
    summary: 'User-isolated exact/semantic cache, short-term context and PII-redacted durable memory.',
    proof: 'Cache status · cross-user isolation · ai.user_memory migration + verifier',
  },
  {
    id: '24',
    title: 'LLM observability',
    icon: Activity,
    status: 'Live',
    summary: 'Every model step exposes the actual route, outcome, latency, trace ID and citations.',
    proof: 'Actual model ID · ok/fallback/error outcome · model-priced cost trace',
  },
  {
    id: '25',
    title: 'Resilience & fallback',
    icon: BrainCircuit,
    status: 'Fault tested',
    summary: 'Malformed output is blocked before tool execution and returns an honest degraded response.',
    proof: 'Flagd injection · output validation · safe fallback · reproducible logs',
  },
] as const;

export function MandateBadges({ compact = false, inverse = false }: { compact?: boolean; inverse?: boolean }) {
  return (
    <div className="flex flex-wrap gap-2" aria-label="Active AI mandates">
      {mandates.map(mandate => (
        <Badge key={mandate.id} variant="outline" className={`${compact ? 'text-[10px]' : ''} ${inverse ? 'border-white/30 bg-white/10 text-white' : ''}`}>
          M{mandate.id} · {mandate.status}
        </Badge>
      ))}
    </div>
  );
}

export default function MandateExperience() {
  return (
    <section className="mx-auto w-full max-w-7xl px-4 py-10 sm:px-6 lg:px-8" aria-labelledby="ai-mandates-title">
      <div className="mb-8 grid gap-6 rounded-3xl border bg-gradient-to-br from-slate-950 via-slate-900 to-indigo-950 p-6 text-white shadow-xl md:grid-cols-[1.4fr_1fr] md:p-10">
        <div>
          <Badge className="mb-4 bg-cyan-400 text-slate-950 hover:bg-cyan-300">Production AI evidence</Badge>
          <h1 id="ai-mandates-title" className="max-w-3xl text-3xl font-black tracking-tight sm:text-5xl">
            Trust is visible in every AI answer.
          </h1>
          <p className="mt-4 max-w-2xl text-sm leading-6 text-slate-300 sm:text-base">
            Grounding, memory isolation, model-level telemetry and degraded-mode safety are surfaced in the same storefront where shoppers use them.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link className="rounded-md bg-white px-4 py-2 text-sm font-semibold text-slate-950 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2" href="/#hot-products">
              Try product AI
            </Link>
            <span className="rounded-md border border-white/20 px-4 py-2 text-sm text-slate-200">Open Shopping Copilot ↘</span>
          </div>
        </div>
        <Card className="border-white/15 bg-white/10 text-white shadow-none backdrop-blur">
          <CardHeader>
            <CardTitle>Mandate readiness</CardTitle>
            <CardDescription className="text-slate-300">Code, checks and user-facing evidence</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Progress value={92} aria-label="Mandate readiness 92 percent" />
            <MandateBadges inverse />
            <p className="text-xs text-slate-300">M23 production database execution remains an environment deployment step; the migration and verification gate are repository-controlled.</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {mandates.map(mandate => {
          const Icon = mandate.icon;
          return (
            <Card key={mandate.id} className="h-full transition-shadow hover:shadow-md">
              <CardHeader>
                <div className="flex items-center justify-between gap-3">
                  <span className="rounded-lg bg-primary/10 p-2 text-primary"><Icon className="size-5" aria-hidden="true" /></span>
                  <Badge variant={mandate.id === '23' ? 'secondary' : 'default'}>{mandate.status}</Badge>
                </div>
                <CardTitle>Mandate {mandate.id}</CardTitle>
                <CardDescription>{mandate.title}</CardDescription>
              </CardHeader>
              <CardContent className="text-sm leading-6 text-muted-foreground">{mandate.summary}</CardContent>
            </Card>
          );
        })}
      </div>

      <Tabs defaultValue="experience" className="mt-8">
        <TabsList className="grid h-auto w-full grid-cols-1 sm:grid-cols-3">
          <TabsTrigger value="experience">Storefront experience</TabsTrigger>
          <TabsTrigger value="evidence">Evidence contract</TabsTrigger>
          <TabsTrigger value="repro">Reproduction</TabsTrigger>
        </TabsList>
        <TabsContent value="experience" className="mt-4">
          <Card>
            <CardHeader><CardTitle>One connected UI system</CardTitle></CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-3">
              {[
                ['Product reviews', 'Cards, rating distribution, Ask AI, grounded citations and recommendations.'],
                ['Cart & checkout', 'Confirmation-gated writes, cache bypass for cart mutations and safe empty states.'],
                ['Shopping Copilot', 'Responsive chat, action gate and expandable trace panel for every observable step.'],
              ].map(([title, copy]) => <div key={title} className="rounded-xl border bg-muted/30 p-4"><h3 className="font-semibold">{title}</h3><p className="mt-2 text-sm text-muted-foreground">{copy}</p></div>)}
            </CardContent>
          </Card>
        </TabsContent>
        <TabsContent value="evidence" className="mt-4">
          <Card>
            <CardContent className="pt-6">
              <Table>
                <TableHeader><TableRow><TableHead>Mandate</TableHead><TableHead>Visible proof</TableHead><TableHead>State</TableHead></TableRow></TableHeader>
                <TableBody>
                  {mandates.map(m => <TableRow key={m.id}><TableCell className="font-medium">M{m.id}</TableCell><TableCell>{m.proof}</TableCell><TableCell><Badge variant="outline">{m.status}</Badge></TableCell></TableRow>)}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
        <TabsContent value="repro" className="mt-4">
          <Card>
            <CardHeader><CardTitle>Small, runnable checks</CardTitle><CardDescription>Each non-trivial safety path leaves a check that fails when the behavior regresses.</CardDescription></CardHeader>
            <CardContent>
              <Accordion>
                <AccordionItem value="m14"><AccordionTrigger>M14 · NLI and κ replay</AccordionTrigger><AccordionContent><code>python3 docs/ai/evals/measure_judge_human_agreement.py --replay-results docs/ai/evals/judge_human_agreement_results.json</code></AccordionContent></AccordionItem>
                <AccordionItem value="m23"><AccordionTrigger>M23 · cache and memory</AccordionTrigger><AccordionContent><code>bash docs/ai/evals/repro_m23.sh</code></AccordionContent></AccordionItem>
                <AccordionItem value="m24"><AccordionTrigger>M24 · trace metadata</AccordionTrigger><AccordionContent><code>pytest -q src/*/test_llm_trace_metadata.py</code></AccordionContent></AccordionItem>
                <AccordionItem value="m25"><AccordionTrigger>M25 · real fault injection</AccordionTrigger><AccordionContent><code>./repro_m25.sh</code></AccordionContent></AccordionItem>
              </Accordion>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </section>
  );
}
