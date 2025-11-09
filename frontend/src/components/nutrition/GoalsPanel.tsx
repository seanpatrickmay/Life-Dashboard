import { useState } from 'react';
import styled from 'styled-components';
import { Card } from '../common/Card';
import { useNutritionGoals } from '../../hooks/useNutritionGoals';
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
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
`;

const GoalCard = styled.div`
  padding: 12px 14px;
  background: rgba(0,0,0,0.15);
  border-radius: 16px;
`;

const Input = styled.input`
  width: 100%;
  padding: 8px;
  margin-top: 6px;
  border-radius: 10px;
  border: 1px solid rgba(255,255,255,0.2);
  background: rgba(0,0,0,0.1);
  color: ${({ theme }) => theme.colors.textPrimary};
`;

export function GoalsPanel() {
  const { goalsQuery, updateGoal } = useNutritionGoals();
  const [drafts, setDrafts] = useState<Record<string, number | undefined>>({});
  const [expanded, setExpanded] = useState<Record<GroupKey, boolean>>({
    macro: true,
    vitamin: false,
    mineral: false
  });

  const goals = goalsQuery.data ?? [];
  const groupedGoals = (() => {
    const buckets: Record<GroupKey, typeof goals> = {
      macro: [],
      vitamin: [],
      mineral: []
    };
    goals.forEach((goal) => {
      const groupKey = (goal.group as GroupKey | undefined) ?? 'macro';
      buckets[groupKey].push(goal);
    });
    return GROUP_ORDER.map((key) => ({
      key,
      label: GROUP_LABELS[key],
      items: buckets[key]
    }));
  })();

  const onBlur = async (slug: string) => {
    const draft = drafts[slug];
    if (draft == null) return;
    await updateGoal({ slug, goal: draft });
  };

  return (
    <Card>
      <h3 data-halo="heading">Nutrient Goals</h3>
      {groupedGoals.map(({ key, label, items }) => (
        <GroupSection key={key} style={{ marginBottom: 12 }}>
          <GroupHeader type="button" onClick={() => setExpanded((prev) => ({ ...prev, [key]: !prev[key] }))}>
            {label}
            <Chevron $expanded={expanded[key]}>›</Chevron>
          </GroupHeader>
          <GroupBody $expanded={expanded[key]}>
            {items.length === 0 ? (
              <GroupEmpty>No {label.toLowerCase()} configured.</GroupEmpty>
            ) : (
              <Grid>
                {items.map((goal) => (
                  <GoalCard key={goal.slug}>
                    <strong>{goal.display_name}</strong>
                    <div>
                      {goal.goal} {goal.unit}
                    </div>
                    <Input
                      type="number"
                      step="0.1"
                      placeholder={String(goal.default_goal)}
                      value={drafts[goal.slug] ?? goal.goal}
                      onChange={(e) =>
                        setDrafts((prev) => ({
                          ...prev,
                          [goal.slug]: Number(e.target.value)
                        }))
                      }
                      onBlur={() => onBlur(goal.slug)}
                    />
                  </GoalCard>
                ))}
              </Grid>
            )}
          </GroupBody>
        </GroupSection>
      ))}
    </Card>
  );
}
