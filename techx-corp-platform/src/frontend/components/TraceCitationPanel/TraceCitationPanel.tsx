import React, { useState } from 'react';
import styled from 'styled-components';

const PanelContainer = styled.div`
  margin-top: 16px;
  background: #ffffff;
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  font-size: 14px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
  overflow: hidden;
  transition: all 0.2s ease;

  &:hover {
    border-color: #d1d5db;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
  }
`;

const Header = styled.button`
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background: transparent;
  border: none;
  cursor: pointer;
  user-select: none;
  transition: background-color 0.2s ease;

  &:hover {
    background-color: #f9fafb;
  }
`;

const Title = styled.strong<{ $isOpen: boolean }>`
  color: #111827;
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 600;

  svg {
    color: #6b7280;
    transition: transform 0.3s cubic-bezier(0.87, 0, 0.13, 1);
    transform: ${props => props.$isOpen ? 'rotate(90deg)' : 'rotate(0deg)'};
  }
`;

const TraceId = styled.span`
  color: #3b82f6;
  font-size: 12px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  background: #eff6ff;
  padding: 4px 8px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.2s;
  &:hover {
    background: #dbeafe;
  }
`;

const ContentWrapper = styled.div<{ $isOpen: boolean }>`
  display: grid;
  grid-template-rows: ${props => props.$isOpen ? '1fr' : '0fr'};
  transition: grid-template-rows 0.3s cubic-bezier(0.87, 0, 0.13, 1);
`;

const ContentInner = styled.div`
  overflow: hidden;
`;

const Content = styled.div`
  padding: 0 20px 20px;
  border-top: 1px solid #f3f4f6;
  margin-top: 4px;
`;

const SectionTitle = styled.div`
  font-weight: 700;
  color: #4b5563;
  margin: 16px 0 8px 0;
  text-transform: uppercase;
  font-size: 12px;
  letter-spacing: 0.05em;
`;

const StepItem = styled.div`
  display: flex;
  justify-content: space-between;
  padding: 10px 0;
  border-bottom: 1px solid #f3f4f6;
  &:last-child {
    border-bottom: none;
  }
`;

const StepName = styled.span`
  color: #1f2937;
  font-weight: 500;
`;

const StepDetail = styled.div`
  font-size: 12px;
  color: #6b7280;
  margin-top: 6px;
  background: #f9fafb;
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px solid #e5e7eb;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: ui-monospace, monospace;
`;

const StepMetrics = styled.span`
  display: flex;
  gap: 16px;
  align-items: flex-start;
`;

const StepLatency = styled.span`
  color: #6b7280;
  font-variant-numeric: tabular-nums;
  font-size: 13px;
`;

const StepStatus = styled.span<{ $status: string }>`
  font-weight: 600;
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 9999px;
  background: ${props => {
    if (props.$status === 'blocked') return '#fee2e2';
    if (props.$status === 'pass' || props.$status === 'ok') return '#dcfce7';
    return '#f3f4f6';
  }};
  color: ${props => {
    if (props.$status === 'blocked') return '#991b1b';
    if (props.$status === 'pass' || props.$status === 'ok') return '#166534';
    return '#4b5563';
  }};
`;

const CitationList = styled.ul`
  margin: 0;
  padding-left: 24px;
  color: #374151;
`;

const CitationItem = styled.li`
  margin-bottom: 8px;
  line-height: 1.5;
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
        <Title $isOpen={isOpen}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
          </svg>
          AI Evaluation Trace
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
      
      <ContentWrapper $isOpen={isOpen}>
        <ContentInner>
          <Content>
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
                        <div style={{ flex: 1, paddingRight: '16px' }}>
                          <StepName>{name}</StepName>
                          {step.detail && <StepDetail>{step.detail}</StepDetail>}
                        </div>
                        <StepMetrics>
                          <StepLatency>{latency}ms</StepLatency>
                          <StepStatus $status={status}>{status.toUpperCase()}</StepStatus>
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
        </ContentInner>
      </ContentWrapper>
    </PanelContainer>
  );
};
