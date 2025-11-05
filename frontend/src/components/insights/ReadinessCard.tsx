import styled from 'styled-components';

import { useInsight } from '../../hooks/useInsight';

const Card = styled.div`
  background: linear-gradient(145deg, rgba(196, 181, 253, 0.9), rgba(126, 200, 227, 0.85));
  border-radius: 32px;
  padding: 32px;
  color: ${({ theme }) => theme.colors.mistWhite};
  min-height: 220px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  grid-column: 1 / -1;
`;

const Score = styled.div`
  font-size: 3rem;
  font-family: ${({ theme }) => theme.fonts.heading};
`;

const Narrative = styled.p`
  font-size: 1rem;
  line-height: 1.6;
  white-space: pre-line;
`;

export function ReadinessCard() {
  const { data, isLoading } = useInsight();
  return (
    <Card>
      <span>Morning Readiness</span>
      <Score>{isLoading ? '…' : data?.readiness_score ?? '—'}</Score>
      <strong>{data?.readiness_label ?? 'Awaiting insight'}</strong>
      <Narrative>{data?.narrative ?? 'Vertex AI will paint today\'s story soon.'}</Narrative>
    </Card>
  );
}
