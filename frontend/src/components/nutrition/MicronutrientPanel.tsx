import styled from 'styled-components';
import { useNutritionDailySummary } from '../../hooks/useNutritionIntake';

const OVER_COLOR = '#F59E0B';

const Grid = styled.div`
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px 28px;

  @media (max-width: 600px) {
    grid-template-columns: 1fr;
  }
`;

const GroupLabel = styled.div`
  font-size: 0.55rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  opacity: 0.35;
  margin-bottom: 8px;
`;

const Column = styled.div`
  display: flex;
  flex-direction: column;
  gap: 4px;
`;

const Row = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 4px 0;
`;

const Name = styled.span`
  font-size: 0.78rem;
  color: ${({ theme }) => theme.colors.textPrimary};
`;

const PctGroup = styled.span<{ $over?: boolean }>`
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 0.72rem;
  font-weight: ${({ $over }) => ($over ? 600 : 400)};
  color: ${({ $over, theme }) => ($over ? OVER_COLOR : theme.colors.textSecondary)};
`;

const Dot = styled.span`
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: ${OVER_COLOR};
  flex-shrink: 0;
`;

const TrackBar = styled.div`
  height: 3px;
  background: ${({ theme }) => theme.colors.overlay};
  border-radius: 2px;
  overflow: hidden;
  margin-top: 2px;
`;

const FillBar = styled.div<{ $pct: number; $over?: boolean }>`
  width: ${({ $pct }) => Math.min($pct, 100)}%;
  height: 100%;
  background: ${({ $over, theme }) =>
    $over ? OVER_COLOR : theme.colors.accent};
  border-radius: 2px;
  transition: width 0.4s ease;
`;

const EmptyMessage = styled.p`
  font-size: 0.8rem;
  color: ${({ theme }) => theme.colors.textSecondary};
  margin: 0;
  grid-column: 1 / -1;
`;

export function MicronutrientPanel() {
  const { data } = useNutritionDailySummary();
  const nutrients = data?.nutrients ?? [];

  const vitamins = nutrients.filter((n) => n.group === 'vitamin');
  const minerals = nutrients.filter((n) => n.group === 'mineral');

  if (vitamins.length === 0 && minerals.length === 0) {
    return (
      <Grid>
        <EmptyMessage>No micronutrient data available.</EmptyMessage>
      </Grid>
    );
  }

  const renderGroup = (
    label: string,
    items: typeof nutrients
  ) => (
    <Column>
      <GroupLabel>{label}</GroupLabel>
      {items.map((n) => {
        const pct = n.percent_of_goal ?? 0;
        const over = pct > 100;
        return (
          <div key={n.slug}>
            <Row>
              <Name>{n.display_name}</Name>
              <PctGroup $over={over}>
                {over && <Dot />}
                {n.goal != null ? `${Math.round(pct)}%` : `${Math.round(n.amount ?? 0)} ${n.unit}`}
              </PctGroup>
            </Row>
            {n.goal != null && (
              <TrackBar>
                <FillBar
                  $pct={pct}
                  $over={over}
                  role="progressbar"
                  aria-valuenow={Math.round(pct)}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-label={`${n.display_name} progress`}
                />
              </TrackBar>
            )}
          </div>
        );
      })}
    </Column>
  );

  return (
    <Grid>
      {vitamins.length > 0 && renderGroup('Vitamins', vitamins)}
      {minerals.length > 0 && renderGroup('Minerals', minerals)}
    </Grid>
  );
}
