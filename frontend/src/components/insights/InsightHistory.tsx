import styled from 'styled-components';

import { useInsight } from '../../hooks/useInsight';

const List = styled.div`
  display: flex;
  flex-direction: column;
  gap: 16px;
`;

const Entry = styled.article`
  background: rgba(255, 255, 255, 0.9);
  border-radius: 24px;
  padding: 24px;
  box-shadow: ${({ theme }) => theme.shadows.soft};
`;

export function InsightHistory() {
  const { data } = useInsight();
  return (
    <List>
      <Entry>
        <h3>{data?.metric_date ? new Date(data.metric_date).toDateString() : '—'}</h3>
        <p>{data?.narrative ?? 'No insight yet.'}</p>
      </Entry>
    </List>
  );
}
