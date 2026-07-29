import { useProductReview } from '../../providers/ProductReview.provider';
import { useAiAssistant } from '../../providers/ProductAIAssistant.provider';
import React, { useState, useMemo } from 'react';
import { CypressFields } from '../../utils/enums/CypressFields';
import { TraceCitationPanel } from '../TraceCitationPanel';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

const clamp = (n: number, min = 0, max = 5) => Math.max(min, Math.min(max, n));

const StarRating = ({ value, max = 5 }: { value: number; max?: number }) => {
  const rounded = clamp(Math.round(value), 0, max);
  return (
    <span className="text-yellow-500 text-lg" aria-label={`${value.toFixed(1)} out of ${max} stars`}>
      {Array.from({ length: max }, (_, i) => (i < rounded ? '★' : '☆')).join(' ')}
    </span>
  );
};

const ProductReviews = () => {
  const { productReviews, loading, error, averageScore } = useProductReview();
  const average = useMemo(() => (averageScore ? clamp(Number(averageScore)) : null), [averageScore]);
  const distribution = useMemo(() => {
    if (!Array.isArray(productReviews)) return [0, 0, 0, 0, 0];
    return [1, 2, 3, 4, 5].map(s => productReviews.filter(r => clamp(Math.round(Number(r.score)), 1, 5) === s).length);
  }, [productReviews]);
  const normalizedPercents = useMemo(() => {
    if (!productReviews?.length) return [0, 0, 0, 0, 0];
    const raw = distribution.map(c => (c / productReviews.length) * 100);
    const floored = raw.map(p => Math.floor(p));
    let remainder = 100 - floored.reduce((a, b) => a + b, 0);
    const order = raw.map((p, i) => ({ i, frac: p - Math.floor(p) })).sort((a, b) => b.frac - a.frac);
    const final = floored.slice();
    for (let k = 0; k < remainder; k++) final[order[k].i] += 1;
    return final;
  }, [distribution, productReviews]);

  const [aiQuestion, setAiQuestion] = useState('');
  const { sendAiRequest, aiResponse, aiLoading, aiError, reset } = useAiAssistant();
  const handleAskAI = (q?: string) => {
    const question = (q ?? aiQuestion).trim();
    if (!question) return;
    reset();
    sendAiRequest({ question });
  };
  const handleQuickPrompt = (p: string) => {
    setAiQuestion(p);
    handleAskAI(p);
  };

  return (
    <div aria-live="polite" data-cy={CypressFields.ProductReviews} className="flex flex-col gap-6">
      <Card className="p-4" data-cy="AskAISection">
        <h3 className="mb-3 text-lg font-bold">Ask AI About This Product</h3>
        <div className="flex gap-2">
          <Input
            id="ask-ai-input"
            placeholder="Type a question about the product…"
            value={aiQuestion}
            onChange={e => setAiQuestion(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter' && !aiLoading && aiQuestion.trim()) handleAskAI();
            }}
            data-cy="AskAIInput"
          />
          <Button onClick={() => handleAskAI()} disabled={aiLoading || !aiQuestion.trim()} data-cy="AskAIButton">
            {aiLoading ? 'Asking AI…' : 'Ask'}
          </Button>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {[
            'Can you summarize the product reviews?',
            'What age(s) is this recommended for?',
            'Were there any negative reviews?',
          ].map(p => (
            <Button key={p} variant="outline" size="sm" onClick={() => handleQuickPrompt(p)}>
              {p}
            </Button>
          ))}
        </div>
        {aiError && (
          <p className="mt-2 text-sm text-red-500" data-cy="AIError">
            {aiError.message ?? 'Sorry, something went wrong.'}
          </p>
        )}
        {aiResponse && (
          <div className="mt-3" data-cy="AIAnswer">
            <p className="rounded-md bg-muted p-3 text-sm">
              <strong>AI Response:</strong> {typeof aiResponse === 'string' ? aiResponse : aiResponse.text}
            </p>
            {typeof aiResponse !== 'string' && aiResponse.traceId && (
              <TraceCitationPanel
                traceId={aiResponse.traceId}
                citations={aiResponse.citations}
                traceSteps={aiResponse.traceSteps}
              />
            )}
          </div>
        )}
      </Card>
      <h3 className="text-xl font-bold">Customer Reviews</h3>
      {loading && <p>Loading…</p>}
      {!loading && error && <p>Could not load reviews.</p>}
      {!loading && !error && !productReviews?.length && <p>No reviews yet.</p>}
      {!loading && !error && (
        <>
          {average != null && (
            <Card className="p-4">
              <div className="flex flex-col gap-4 sm:flex-row">
                <div className="flex flex-col items-center gap-1">
                  <span className="text-3xl font-bold">{average.toFixed(1)}</span>
                  <StarRating value={average} />
                  <span className="text-xs text-muted-foreground">{productReviews?.length || 0} reviews</span>
                </div>
                <div className="flex-1 space-y-1">
                  {[5, 4, 3, 2, 1].map(score => {
                    const pct = normalizedPercents[score - 1];
                    return (
                      <div key={score} className="flex items-center gap-2 text-sm">
                        <span className="w-12 text-right">
                          {score} star{score > 1 ? 's' : ''}
                        </span>
                        <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
                          <div className="h-full rounded-full bg-yellow-500" style={{ width: `${pct}%` }} />
                        </div>
                        <span className="w-10 text-right text-muted-foreground">{pct}%</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            </Card>
          )}
          {productReviews?.length > 0 && (
            <div className="grid gap-4 sm:grid-cols-2">
              {productReviews.map((review, idx) => (
                <Card key={`${review.username}-${review.score}-${idx}`} className="p-4">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="font-medium">{review.username}</span>
                    <StarRating value={Number(review.score) || 0} />
                  </div>
                  <p className="text-sm text-muted-foreground">{review.description || 'No description provided.'}</p>
                </Card>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default ProductReviews;
