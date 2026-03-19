import { useState } from 'react';
import styled from 'styled-components';
import { focusRing } from '../../styles/animations';
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
  background: ${({ theme }) => theme.colors.surfaceRaised};
  border-radius: 16px;
  padding: 10px 14px;
`;

const Bar = styled.div<{ $percent?: number | null }>`
  height: 6px;
  border-radius: 999px;
  background: ${({ theme }) => theme.colors.overlay};
  overflow: hidden;
  margin-top: 8px;
  &::after {
    content: '';
    display: block;
    height: 100%;
    width: ${({ $percent }) => ($percent != null ? Math.min(100, Math.max(0, $percent)) : 0)}%;
    background: ${({ theme }) => theme.palette?.pond?.['200'] ?? '#7ED7C4'};
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

  type Groupable = { slug: string; display_name: string; group: string; unit: string; percent_of_goal: number | null; goal: number | null };
  const groupEntries = <T extends Groupable>(items: T[]) => {
    const buckets: Record<GroupKey, T[]> = {
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
          <GroupHeader type="button" aria-expanded={summaryExpanded[key]} onClick={() => setSummaryExpanded((prev) => ({ ...prev, [key]: !prev[key] }))}>
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
                    <Bar
                      $percent={item.percent_of_goal}
                      role="progressbar"
                      aria-valuenow={item.percent_of_goal ?? 0}
                      aria-label={`${item.display_name}: ${item.percent_of_goal ?? 0}% of goal`}
                    />
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
          <GroupHeader type="button" aria-expanded={historyExpanded[key]} onClick={() => setHistoryExpanded((prev) => ({ ...prev, [key]: !prev[key] }))}>
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
                    <Bar
                      $percent={item.percent_of_goal}
                      role="progressbar"
                      aria-valuenow={item.percent_of_goal ?? 0}
                      aria-label={`${item.display_name}: ${item.percent_of_goal ?? 0}% of goal`}
                    />
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
