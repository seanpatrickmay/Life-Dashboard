import { useState } from 'react';
import styled from 'styled-components';
import { Card } from '../common/Card';
import { useNutritionDailySummary, useNutritionHistory } from '../../hooks/useNutritionIntake';
import {
  GROUP_LABELS,
  GROUP_ORDER,
  GroupBody,
  GroupEmpty,
  GroupHeader,
  GroupSection,
  type GroupKey,
  Chevron
} from './NutrientGroupUI';

const Grid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
`;

const ProgressBlock = styled.div`
  background: rgba(0,0,0,0.15);
  border-radius: 16px;
  padding: 10px 14px;
`;

const Bar = styled.div<{ $percent?: number | null }>`
  height: 6px;
  border-radius: 999px;
  background: rgba(255,255,255,0.1);
  overflow: hidden;
  margin-top: 8px;
  &::after {
    content: '';
    display: block;
    height: 100%;
    width: ${({ $percent }) => ($percent != null ? Math.min(100, Math.max(0, $percent)) : 0)}%;
    background: ${({ theme }) => theme.colors.accent};
  }
`;

export function NutritionDashboard() {
  const summaryQuery = useNutritionDailySummary();
  const historyQuery = useNutritionHistory();
  const [summaryExpanded, setSummaryExpanded] = useState<Record<GroupKey, boolean>>({
    macro: true,
    vitamin: false,
    mineral: false
  });
  const [historyExpanded, setHistoryExpanded] = useState<Record<GroupKey, boolean>>({
    macro: true,
    vitamin: false,
    mineral: false
  });

  const summary = summaryQuery.data?.nutrients ?? [];
  const history = historyQuery.data?.nutrients ?? [];

  const groupEntries = (items: typeof summary) => {
    const buckets: Record<GroupKey, typeof items> = {
      macro: [],
      vitamin: [],
      mineral: []
    };
    items.forEach((item) => {
      const key = (item.group as GroupKey | undefined) ?? 'macro';
      buckets[key].push(item);
    });
    return GROUP_ORDER.map((key) => ({
      key,
      label: GROUP_LABELS[key],
      items: buckets[key]
    }));
  };

  const summaryGroups = groupEntries(summary);
  const historyGroups = groupEntries(history);

  return (
    <Card>
      <h3 data-halo="heading">Daily Intake</h3>
      {summaryGroups.map(({ key, label, items }) => (
        <GroupSection key={key} style={{ marginBottom: 12 }}>
          <GroupHeader type="button" onClick={() => setSummaryExpanded((prev) => ({ ...prev, [key]: !prev[key] }))}>
            {label}
            <Chevron $expanded={summaryExpanded[key]}>›</Chevron>
          </GroupHeader>
          <GroupBody $expanded={summaryExpanded[key]}>
            {items.length === 0 ? (
              <GroupEmpty>No {label.toLowerCase()} logged yet.</GroupEmpty>
            ) : (
              <Grid>
                {items.map((item) => (
                  <ProgressBlock key={item.slug}>
                    <strong>{item.display_name}</strong>
                    <div>
                      {item.amount ?? 0} / {item.goal ?? '—'} {item.unit}
                    </div>
                    <Bar $percent={item.percent_of_goal} />
                  </ProgressBlock>
                ))}
              </Grid>
            )}
          </GroupBody>
        </GroupSection>
      ))}
      <h4 data-halo="heading" style={{ marginTop: 12 }}>
        14-day Avg % Goal
      </h4>
      {historyGroups.map(({ key, label, items }) => (
        <GroupSection key={key} style={{ marginBottom: 12 }}>
          <GroupHeader type="button" onClick={() => setHistoryExpanded((prev) => ({ ...prev, [key]: !prev[key] }))}>
            {label}
            <Chevron $expanded={historyExpanded[key]}>›</Chevron>
          </GroupHeader>
          <GroupBody $expanded={historyExpanded[key]}>
            {items.length === 0 ? (
              <GroupEmpty>No {label.toLowerCase()} logged yet.</GroupEmpty>
            ) : (
              <Grid>
                {items.map((item) => (
                  <ProgressBlock key={item.slug}>
                    <strong>{item.display_name}</strong>
                    <div>{item.percent_of_goal?.toFixed(1) ?? 0}% of goal</div>
                    <Bar $percent={item.percent_of_goal} />
                  </ProgressBlock>
                ))}
              </Grid>
            )}
          </GroupBody>
        </GroupSection>
      ))}
    </Card>
  );
}
