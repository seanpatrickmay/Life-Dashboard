import styled from 'styled-components';
import { useNutritionDailySummary } from '../../hooks/useNutritionIntake';

const CALORIE_SLUG = 'calories';

const MACRO_COLORS: Record<string, string> = {
  calories: '#7ED7C4',
  protein: '#FFC075',
  carbohydrate: '#BF6BAB',
  fat: '#C2D5FF',
  fiber: '#82dcb8',
};

const OVER_COLOR = '#F59E0B';

const getColor = (slug: string) =>
  MACRO_COLORS[slug] ?? '#aaa';

/* ── Styled Components ── */

const Wrapper = styled.div`
  display: flex;
  flex-direction: column;
  gap: 12px;
`;

const CalorieCard = styled.div<{ $accent: string }>`
  border-radius: 20px;
  padding: clamp(16px, 2vw, 22px);
  background: ${({ $accent }) => `${$accent}0A`};
  border: 1px solid ${({ $accent }) => `${$accent}33`};
`;

const CalorieRow = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 10px;
  gap: 16px;
`;

const CalorieLabel = styled.span`
  font-size: 0.6rem;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  opacity: 0.5;
  display: block;
  margin-bottom: 2px;
`;

const CalorieValue = styled.span<{ $accent: string }>`
  font-size: clamp(1.6rem, 3vw, 2.2rem);
  font-weight: bold;
  color: ${({ $accent }) => $accent};
  line-height: 1.1;
`;

const CalorieUnit = styled.span`
  font-size: 0.85rem;
  opacity: 0.4;
  font-weight: normal;
  margin-left: 4px;
`;

const CalorieRight = styled.div`
  text-align: right;
  flex-shrink: 0;
`;

const GoalText = styled.div`
  font-size: 0.75rem;
  opacity: 0.5;
`;

const RemainingText = styled.div<{ $accent: string; $over?: boolean }>`
  font-size: 0.85rem;
  color: ${({ $accent, $over }) => ($over ? OVER_COLOR : $accent)};
  font-weight: 600;
`;

const TrackBar = styled.div`
  height: 8px;
  background: ${({ theme }) => theme.colors.overlay};
  border-radius: 4px;
  overflow: hidden;
`;

const FillBar = styled.div<{ $pct: number; $accent: string; $over?: boolean }>`
  width: ${({ $pct }) => Math.min($pct, 100)}%;
  height: 100%;
  background: ${({ $accent, $over }) =>
    $over ? `linear-gradient(90deg, ${$accent}, ${OVER_COLOR})` : $accent};
  border-radius: 4px;
  transition: width 0.4s ease;
`;

const MacroGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;

  @media (max-width: 768px) {
    grid-template-columns: repeat(2, 1fr);
  }

  @media (max-width: 480px) {
    grid-template-columns: 1fr;
  }
`;

const MacroCard = styled.div<{ $accent: string }>`
  border-radius: 16px;
  padding: clamp(12px, 1.5vw, 16px);
  background: ${({ $accent }) => `${$accent}0A`};
  border: 1px solid ${({ $accent }) => `${$accent}26`};
`;

const MacroLabel = styled.div`
  font-size: 0.55rem;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  opacity: 0.5;
  margin-bottom: 4px;
`;

const MacroValue = styled.div<{ $accent: string }>`
  font-size: clamp(1rem, 1.8vw, 1.2rem);
  font-weight: bold;
  color: ${({ $accent }) => $accent};
`;

const MacroGoal = styled.span`
  font-size: 0.6rem;
  opacity: 0.4;
  font-weight: normal;
  margin-left: 4px;
`;

const SmallTrack = styled.div`
  height: 4px;
  background: ${({ theme }) => theme.colors.overlay};
  border-radius: 2px;
  overflow: hidden;
  margin-top: 8px;
`;

const Pct = styled.div`
  font-size: 0.5rem;
  opacity: 0.35;
  margin-top: 4px;
  text-align: right;
`;

const EmptyMessage = styled.p`
  font-size: 0.85rem;
  color: ${({ theme }) => theme.colors.textSecondary};
  margin: 0;
  padding: 20px 0;
`;

const SkeletonBlock = styled.div`
  border-radius: 16px;
  background: ${({ theme }) => theme.colors.overlay};
  animation: pulse 1.5s ease-in-out infinite;

  @keyframes pulse {
    0%, 100% { opacity: 0.4; }
    50% { opacity: 0.15; }
  }
`;

/* ── Component ── */

export function MacroHero() {
  const { data, isLoading } = useNutritionDailySummary();

  if (isLoading) {
    return (
      <Wrapper>
        <SkeletonBlock style={{ height: 110 }} />
        <MacroGrid>
          {[0, 1, 2, 3].map((i) => (
            <SkeletonBlock key={i} style={{ height: 90 }} />
          ))}
        </MacroGrid>
      </Wrapper>
    );
  }

  const nutrients = data?.nutrients ?? [];
  if (nutrients.length === 0) {
    return (
      <Wrapper>
        <EmptyMessage>No nutrition data logged today.</EmptyMessage>
      </Wrapper>
    );
  }

  const calorieEntry = nutrients.find((n) => n.slug === CALORIE_SLUG);
  const macros = nutrients.filter(
    (n) => n.group === 'macro' && n.slug !== CALORIE_SLUG
  );

  const formatNum = (v: number) =>
    v >= 1000 ? v.toLocaleString(undefined, { maximumFractionDigits: 0 }) : String(Math.round(v));

  return (
    <Wrapper>
      {calorieEntry ? (
        <CalorieCard $accent={getColor(CALORIE_SLUG)}>
          <CalorieRow>
            <div>
              <CalorieLabel>Calories</CalorieLabel>
              <CalorieValue $accent={MACRO_COLORS.calories}>
                {formatNum(calorieEntry.amount ?? 0)}
                <CalorieUnit>kcal</CalorieUnit>
              </CalorieValue>
            </div>
            {calorieEntry.goal != null && (
              <CalorieRight>
                <GoalText>of {formatNum(calorieEntry.goal)}</GoalText>
                {(() => {
                  const remaining = calorieEntry.goal - (calorieEntry.amount ?? 0);
                  const over = remaining < 0;
                  return (
                    <RemainingText $accent={MACRO_COLORS.calories} $over={over}>
                      {over
                        ? `over by ${formatNum(Math.abs(remaining))}`
                        : `${formatNum(remaining)} remaining`}
                    </RemainingText>
                  );
                })()}
              </CalorieRight>
            )}
          </CalorieRow>
          {calorieEntry.goal != null && (
            <TrackBar>
              <FillBar
                $pct={calorieEntry.percent_of_goal ?? 0}
                $accent={MACRO_COLORS.calories}
                $over={(calorieEntry.percent_of_goal ?? 0) > 100}
                role="progressbar"
                aria-valuenow={Math.round(calorieEntry.percent_of_goal ?? 0)}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label="Calories progress"
              />
            </TrackBar>
          )}
        </CalorieCard>
      ) : null}

      {macros.length > 0 && (
        <MacroGrid>
          {macros.map((nutrient) => {
            const accent = getColor(nutrient.slug);
            const pct = nutrient.percent_of_goal ?? 0;
            const over = pct > 100;
            return (
              <MacroCard key={nutrient.slug} $accent={accent}>
                <MacroLabel>{nutrient.display_name}</MacroLabel>
                <MacroValue $accent={accent}>
                  {formatNum(nutrient.amount ?? 0)}
                  {nutrient.unit ? nutrient.unit : ''}
                  {nutrient.goal != null && (
                    <MacroGoal>/ {formatNum(nutrient.goal)}</MacroGoal>
                  )}
                </MacroValue>
                {nutrient.goal != null && (
                  <>
                    <SmallTrack>
                      <FillBar
                        $pct={pct}
                        $accent={accent}
                        $over={over}
                        role="progressbar"
                        aria-valuenow={Math.round(pct)}
                        aria-valuemin={0}
                        aria-valuemax={100}
                        aria-label={`${nutrient.display_name} progress`}
                      />
                    </SmallTrack>
                    <Pct>{Math.round(pct)}%</Pct>
                  </>
                )}
              </MacroCard>
            );
          })}
        </MacroGrid>
      )}
    </Wrapper>
  );
}
