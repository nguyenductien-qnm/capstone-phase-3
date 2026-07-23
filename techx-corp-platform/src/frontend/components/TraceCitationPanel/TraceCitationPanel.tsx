import React, { useState } from 'react';
import styled from 'styled-components';

const PanelContainer = styled.div`
  margin-top: 12px;
  padding: 12px;
  background: #f8f9fa;
  border-radius: 6px;
  border: 1px solid #e9ecef;
  font-size: 13px;
  font-family: monospace;
`;

const Header = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  cursor: pointer;
  user-select: none;
`;

const Title = styled.strong`
  color: #495057;
  display: flex;
  align-items: center;
  gap: 6px;
`;

const TraceId = styled.span`
  color: #0066cc;
  cursor: pointer;
  &:hover {
    text-decoration: underline;
  }
`;

const Content = styled.div<{ $isOpen: boolean }>`
  display: ${props => props.$isOpen ? 'block' : 'none'};
`;

const SectionTitle = styled.div`
  font-weight: bold;
  color: #343a40;
  margin: 12px 0 4px 0;
  text-transform: uppercase;
  font-size: 11px;
  letter-spacing: 0.5px;
`;

const StepItem = styled.div`
  display: flex;
  justify-content: space-between;
  padding: 4px 0;
  border-bottom: 1px dashed #dee2e6;
  &:last-child {
    border-bottom: none;
  }
`;

const StepName = styled.span`
  color: #495057;
`;

const StepDetail = styled.div`
  font-size: 11px;
  color: #6c757d;
  margin-top: 4px;
  background: #e9ecef;
  padding: 4px;
  border-radius: 4px;
  white-space: pre-wrap;
  word-break: break-all;
`;

const StepMetrics = styled.span`
  display: flex;
  gap: 12px;
`;

const StepLatency = styled.span`
  color: #6c757d;
`;

const StepStatus = styled.span<{ $status: string }>`
  font-weight: bold;
  color: ${props => {
    if (props.$status === 'blocked') return '#dc3545';
    if (props.$status === 'pass' || props.$status === 'ok') return '#198754';
    return '#6c757d';
  }};
`;

const CitationList = styled.ul`
  margin: 0;
  padding-left: 20px;
  color: #495057;
`;

const CitationItem = styled.li`
  margin-bottom: 4px;
`;

export interface TraceStep {
  stepName?: string;
  latencyMs?: number;
  status?: string;
  detail?: string;
  // in protobuf, snake_case becomes camelCase
  step_name?: string;
  latency_ms?: number;
}

export interface Citation {
  reviewId?: string;
  review_id?: string;
  snippet?: string;
  score?: string;
}

export interface TraceCitationPanelProps {
  traceId?: string;
  traceSteps?: TraceStep[];
  citations?: Citation[];
  defaultOpen?: boolean;
}

export const TraceCitationPanel: React.FC<TraceCitationPanelProps> = ({ 
  traceId, 
  traceSteps = [], 
  citations = [],
  defaultOpen = false
}) => {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  if (!traceId && (!traceSteps || traceSteps.length === 0) && (!citations || citations.length === 0)) {
    return null;
  }

  return (
    <PanelContainer data-cy="TraceCitationPanel">
      <Header onClick={() => setIsOpen(!isOpen)}>
        <Title>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          AI Evaluation Trace {isOpen ? '▼' : '▶'}
        </Title>
        {traceId && (
          <TraceId 
            title="Click to copy Trace ID"
            onClick={(e) => {
              e.stopPropagation();
              navigator.clipboard?.writeText(traceId);
            }}
          >
            {traceId.slice(0, 8)}...
          </TraceId>
        )}
      </Header>
      
      <Content $isOpen={isOpen}>
        {traceSteps && traceSteps.length > 0 && (
          <>
            <SectionTitle>Execution Steps</SectionTitle>
            <div>
              {traceSteps.map((step, idx) => {
                const name = step.stepName || step.step_name || 'Unknown Step';
                const latency = step.latencyMs ?? step.latency_ms ?? 0;
                const status = step.status || 'unknown';
                
                return (
                  <StepItem key={idx}>
                    <div style={{ flex: 1, paddingRight: '12px' }}>
                      <StepName>{name}</StepName>
                      {step.detail && <StepDetail>{step.detail}</StepDetail>}
                    </div>
                    <StepMetrics>
                      <StepLatency>{latency}ms</StepLatency>
                      <StepStatus $status={status}>[{status.toUpperCase()}]</StepStatus>
                    </StepMetrics>
                  </StepItem>
                );
              })}
            </div>
          </>
        )}

        {citations && citations.length > 0 && (
          <>
            <SectionTitle>Grounded Sources</SectionTitle>
            <CitationList>
              {citations.map((c, i) => (
                <CitationItem key={i}>
                  "{c.snippet}" - <em>{c.reviewId || c.review_id}</em> ({c.score}★)
                </CitationItem>
              ))}
            </CitationList>
          </>
        )}
      </Content>
    </PanelContainer>
  );
};
