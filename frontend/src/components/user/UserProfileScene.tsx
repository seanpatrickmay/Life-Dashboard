import { useEffect, useMemo, useRef, useState } from 'react';
import styled from 'styled-components';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  type NutritionGoal,
  type UserProfileData,
  connectGarmin,
  fetchGarminStatus,
  logout,
  reauthGarmin
} from '../../services/api';
import { useUserProfile } from '../../hooks/useUserProfile';

const SceneLayout = styled.div`
  display: flex;
  flex-direction: column;
  gap: clamp(20px, 3vw, 32px);
  color: ${({ theme }) => (theme.mode === 'light' ? '#F6F0E8' : theme.colors.textPrimary)};
`;

const SceneHeader = styled.div`
  display: flex;
  justify-content: flex-end;
  align-items: center;
  min-height: 40px;
`;

const SignOutButton = styled.button`
  border-radius: 999px;
  padding: 10px 18px;
  border: 1px solid rgba(255, 255, 255, 0.4);
  background: ${({ theme }) => theme.colors.accent};
  color: #0b0f19;
  font-family: ${({ theme }) => theme.fonts.heading};
  letter-spacing: 0.16em;
  text-transform: uppercase;
  font-size: 0.75rem;
  cursor: pointer;
  box-shadow: 0 10px 24px rgba(7, 9, 19, 0.35);
`;

const SectionGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: clamp(16px, 2vw, 24px);
`;

const StackColumn = styled.div`
  display: flex;
  flex-direction: column;
  gap: clamp(16px, 2vw, 24px);
`;

const LilyPadCard = styled.section`
  border-radius: 32px;
  padding: clamp(18px, 2.2vw, 28px);
  background: rgba(10, 22, 42, 0.55);
  border: 1px solid rgba(255, 255, 255, 0.12);
  backdrop-filter: blur(9px);
  box-shadow: 0 12px 40px rgba(7, 9, 19, 0.35);
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 180px;
  color: ${({ theme }) => (theme.mode === 'light' ? '#F6F0E8' : theme.colors.textPrimary)};
`;

const SectionTitle = styled.h2`
  font-family: ${({ theme }) => theme.fonts.heading};
  letter-spacing: 0.2em;
  text-transform: uppercase;
  font-size: 0.75rem;
  opacity: 0.8;
  margin: 0;
`;

const FieldGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px 16px;
`;

const Field = styled.label`
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 0.85rem;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: ${({ theme }) =>
    theme.mode === 'light' ? 'rgba(246, 240, 232, 0.78)' : theme.colors.textSecondary};
  input,
  select {
    font-size: 1rem;
    padding: 10px 14px;
    border-radius: 18px;
    border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
    background: ${({ theme }) =>
      theme.mode === 'light' ? 'rgba(255, 255, 255, 0.9)' : 'rgba(10, 18, 32, 0.6)'};
    color: ${({ theme }) => theme.colors.textPrimary};
    font-family: ${({ theme }) => theme.fonts.body};
    &::placeholder {
      color: ${({ theme }) => theme.colors.textSecondary};
    }
  }
`;

const PadButtonRow = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 8px;
  align-items: center;
`;

const PadButton = styled.button<{ $variant?: 'primary' | 'ghost' }>`
  border-radius: 999px;
  padding: 10px 20px;
  border: 1px solid rgba(255, 255, 255, 0.3);
  background: ${({ $variant }) => ($variant === 'primary' ? 'rgba(255, 255, 255, 0.2)' : 'transparent')};
  color: ${({ theme }) => (theme.mode === 'light' ? '#F6F0E8' : theme.colors.textPrimary)};
  text-transform: uppercase;
  letter-spacing: 0.18em;
  font-size: 0.78rem;
  cursor: pointer;
  transition: opacity 0.2s ease;
  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
`;

const SaveStatus = styled.span<{ $tone: 'neutral' | 'success' | 'error' }>`
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 0.7rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  border: 1px solid
    ${({ $tone }) =>
      $tone === 'success'
        ? 'rgba(120,255,200,0.6)'
        : $tone === 'error'
          ? 'rgba(255,140,140,0.6)'
          : 'rgba(255,255,255,0.2)'};
  background: ${({ $tone }) =>
    $tone === 'success'
      ? 'rgba(64,180,120,0.2)'
      : $tone === 'error'
        ? 'rgba(200,80,80,0.2)'
        : 'rgba(16,20,28,0.4)'};
  color: ${({ theme }) => (theme.mode === 'light' ? '#F6F0E8' : theme.colors.textPrimary)};
`;

const GoalsList = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 8px;
`;

const GoalChip = styled.div`
  min-width: 120px;
  border-radius: 18px;
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.08);
  display: flex;
  flex-direction: column;
  gap: 4px;
  span {
    font-size: 0.7rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    opacity: 0.75;
  }
  strong {
    font-size: 1rem;
  }
`;

const StatusPill = styled.span<{ $active?: boolean }>`
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 0.7rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  border: 1px solid ${({ $active }) => ($active ? 'rgba(120,255,200,0.6)' : 'rgba(255,255,255,0.2)')};
  background: ${({ $active }) => ($active ? 'rgba(64,180,120,0.25)' : 'rgba(16,20,28,0.4)')};
  color: ${({ theme }) => (theme.mode === 'light' ? '#F6F0E8' : theme.colors.textPrimary)};
`;

const HelperText = styled.p`
  margin: 0;
  font-size: 0.8rem;
  opacity: 0.75;
  line-height: 1.4;
`;

const InlineForm = styled.div`
  display: grid;
  gap: 12px;
`;

const KG_TO_LB = 2.20462;
const CM_TO_IN = 0.393701;

const toRoundedString = (value: number, digits: number) => {
  const factor = 10 ** digits;
  return (Math.round(value * factor) / factor).toString();
};

export function UserProfileScene() {
  const { profileQuery, updateProfile } = useUserProfile();
  const queryClient = useQueryClient();
  const [formState, setFormState] = useState<UserProfileData>({
    date_of_birth: '',
    sex: '',
    height_cm: undefined,
    current_weight_kg: undefined,
    preferred_units: 'metric',
    daily_energy_delta_kcal: 0
  });
  const [garminEmail, setGarminEmail] = useState('');
  const [garminPassword, setGarminPassword] = useState('');
  const preferredUnits = formState.preferred_units ?? profileQuery.data?.profile?.preferred_units ?? 'metric';
  const [isEditing, setIsEditing] = useState(false);
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const [hasInitialized, setHasInitialized] = useState(false);
  const saveTimerRef = useRef<number | null>(null);

  const hasProfileValues = Boolean(
    profileQuery.data?.profile?.height_cm ||
      profileQuery.data?.profile?.current_weight_kg ||
      profileQuery.data?.profile?.date_of_birth ||
      profileQuery.data?.profile?.sex
  );

  const garminStatusQuery = useQuery({
    queryKey: ['garmin', 'status'],
    queryFn: fetchGarminStatus
  });

  const connectMutation = useMutation({
    mutationFn: () =>
      connectGarmin({
        garmin_email: garminEmail,
        garmin_password: garminPassword
      }),
    onSuccess: () => {
      setGarminPassword('');
      queryClient.invalidateQueries({ queryKey: ['garmin', 'status'] });
    }
  });

  const reauthMutation = useMutation({
    mutationFn: () => reauthGarmin(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['garmin', 'status'] });
    }
  });

  useEffect(() => {
    if (profileQuery.data?.profile) {
      setFormState((prev) => ({
        ...prev,
        ...profileQuery.data?.profile
      }));
      if (!hasInitialized) {
        setIsEditing(!hasProfileValues);
        setHasInitialized(true);
      }
    }
  }, [profileQuery.data, hasInitialized, hasProfileValues]);

  useEffect(() => {
    return () => {
      if (saveTimerRef.current) {
        window.clearTimeout(saveTimerRef.current);
      }
    };
  }, []);

  const macroGoals = useMemo(() => {
    if (!profileQuery.data?.goals) return [];
    const importantSlugs = ['calories', 'protein', 'carbohydrates', 'fat', 'fiber'];
    return profileQuery.data.goals.filter((goal) => importantSlugs.includes(goal.slug));
  }, [profileQuery.data]);

  const handleInputChange = (key: keyof UserProfileData, value: string) => {
    if (saveState === 'saved' || saveState === 'error') {
      setSaveState('idle');
    }
    setFormState((prev) => ({
      ...prev,
      [key]: value === '' ? null : value
    }));
  };

  const handleNumberChange = (
    key: keyof UserProfileData,
    value: string,
    toMetric?: (value: number) => number
  ) => {
    if (saveState === 'saved' || saveState === 'error') {
      setSaveState('idle');
    }
    setFormState((prev) => ({
      ...prev,
      [key]: value === '' ? null : toMetric ? toMetric(Number(value)) : Number(value)
    }));
  };

  const onSaveProfile = async () => {
    const payload: UserProfileData = {
      ...formState,
      date_of_birth: formState.date_of_birth || null
    };
    setSaveState('saving');
    try {
      await updateProfile(payload);
      setSaveState('saved');
      setIsEditing(false);
    } catch {
      setSaveState('error');
    } finally {
      if (saveTimerRef.current) {
        window.clearTimeout(saveTimerRef.current);
      }
      saveTimerRef.current = window.setTimeout(() => setSaveState('idle'), 2500);
    }
  };

  const handleGarminConnect = async () => {
    if (!garminEmail || !garminPassword) return;
    await connectMutation.mutateAsync();
  };

  const handleLogout = async () => {
    await logout();
    queryClient.clear();
    window.location.href = '/login';
  };

  if (profileQuery.isLoading) {
    return <span>Loading profile…</span>;
  }

  const isReadOnly = hasProfileValues && !isEditing;
  const showEditButton = hasProfileValues && !isEditing;
  const showSaveButton = !hasProfileValues || isEditing;

  return (
    <SceneLayout>
      <SceneHeader>
        <SignOutButton onClick={handleLogout}>Sign Out</SignOutButton>
      </SceneHeader>
      <SectionGrid>
        <LilyPadCard>
          <SectionTitle>Personal Stats</SectionTitle>
          <FieldGrid>
            <Field>
              Date of Birth
              <input
                type="date"
                value={(formState.date_of_birth as string) || ''}
                disabled={isReadOnly}
                onChange={(event) => handleInputChange('date_of_birth', event.target.value)}
              />
            </Field>
            <Field>
              Sex
              <select
                value={formState.sex ?? ''}
                disabled={isReadOnly}
                onChange={(event) => handleInputChange('sex', event.target.value)}
              >
                <option value="">—</option>
                <option value="female">Female</option>
                <option value="male">Male</option>
                <option value="other">Other</option>
              </select>
            </Field>
            <Field>
              Height ({preferredUnits === 'imperial' ? 'in' : 'cm'})
              <input
                type="number"
                inputMode="decimal"
                step={preferredUnits === 'imperial' ? 0.1 : 1}
                value={
                  formState.height_cm == null
                    ? ''
                    : preferredUnits === 'imperial'
                      ? toRoundedString(formState.height_cm * CM_TO_IN, 1)
                      : toRoundedString(formState.height_cm, 0)
                }
                disabled={isReadOnly}
                onChange={(event) =>
                  handleNumberChange(
                    'height_cm',
                    event.target.value,
                    preferredUnits === 'imperial' ? (value) => value / CM_TO_IN : undefined
                  )
                }
              />
            </Field>
            <Field>
              Weight ({preferredUnits === 'imperial' ? 'lb' : 'kg'})
              <input
                type="number"
                inputMode="decimal"
                step={0.1}
                value={
                  formState.current_weight_kg == null
                    ? ''
                    : preferredUnits === 'imperial'
                      ? toRoundedString(formState.current_weight_kg * KG_TO_LB, 1)
                      : toRoundedString(formState.current_weight_kg, 1)
                }
                disabled={isReadOnly}
                onChange={(event) =>
                  handleNumberChange(
                    'current_weight_kg',
                    event.target.value,
                    preferredUnits === 'imperial' ? (value) => value / KG_TO_LB : undefined
                  )
                }
              />
            </Field>
            <Field>
              Units
              <select
                value={formState.preferred_units ?? 'metric'}
                disabled={isReadOnly}
                onChange={(event) =>
                  handleInputChange('preferred_units', event.target.value as 'metric' | 'imperial')
                }
              >
                <option value="metric">Metric</option>
                <option value="imperial">Imperial</option>
              </select>
            </Field>
            <Field>
              Daily Calorie Delta
              <input
                type="number"
                inputMode="numeric"
                value={formState.daily_energy_delta_kcal ?? 0}
                disabled={isReadOnly}
                onChange={(event) => handleNumberChange('daily_energy_delta_kcal', event.target.value)}
              />
            </Field>
          </FieldGrid>
          <PadButtonRow>
            {showEditButton ? (
              <PadButton
                $variant="primary"
                type="button"
                onClick={() => setIsEditing(true)}
              >
                Edit
              </PadButton>
            ) : null}
            {showSaveButton ? (
              <PadButton
                $variant="primary"
                type="button"
                onClick={onSaveProfile}
                disabled={profileQuery.isFetching || saveState === 'saving'}
              >
                {saveState === 'saving' ? 'Saving…' : 'Save'}
              </PadButton>
            ) : null}
            {saveState === 'saved' ? <SaveStatus $tone="success">Saved</SaveStatus> : null}
            {saveState === 'error' ? <SaveStatus $tone="error">Save failed</SaveStatus> : null}
            {saveState === 'saving' ? <SaveStatus $tone="neutral">Saving</SaveStatus> : null}
          </PadButtonRow>
        </LilyPadCard>

        <StackColumn>
          <LilyPadCard>
            <SectionTitle>Latest Energy</SectionTitle>
            {profileQuery.data?.latest_energy ? (
              <>
                <strong style={{ fontSize: '1.6rem' }}>
                  {Math.round(profileQuery.data.latest_energy.total_kcal ?? 0)} kcal
                </strong>
                <p style={{ opacity: 0.8, margin: 0 }}>
                  {profileQuery.data.latest_energy.metric_date} · Source:{' '}
                  {profileQuery.data.latest_energy.source ?? 'calculated'}
                </p>
                <p style={{ opacity: 0.8, margin: 0 }}>
                  Active {Math.round(profileQuery.data.latest_energy.active_kcal ?? 0)} kcal · BMR{' '}
                  {Math.round(profileQuery.data.latest_energy.bmr_kcal ?? 0)} kcal
                </p>
              </>
            ) : (
              <p style={{ opacity: 0.8 }}>No energy data yet.</p>
            )}
          </LilyPadCard>

          <LilyPadCard>
            <SectionTitle>Macro Targets</SectionTitle>
            <GoalsList>
              {macroGoals.map((goal: NutritionGoal) => (
                <GoalChip key={goal.slug}>
                  <span>{goal.display_name}</span>
                  <strong>
                    {Math.round(goal.goal)}
                    {goal.unit ? ` ${goal.unit}` : ''}
                  </strong>
                </GoalChip>
              ))}
            </GoalsList>
            <p style={{ opacity: 0.75, margin: '6px 0 0' }}>
              Computed {profileQuery.data?.goals?.[0]?.computed_at?.split('T')[0] ?? '—'} · Source:{' '}
              {profileQuery.data?.goals?.[0]?.calorie_source ?? 'calculated'}
            </p>
          </LilyPadCard>
        </StackColumn>
      </SectionGrid>

      <SectionGrid>
        <LilyPadCard>
          <SectionTitle>Garmin Connection</SectionTitle>
          <StatusPill $active={garminStatusQuery.data?.connected && !garminStatusQuery.data?.requires_reauth}>
            {garminStatusQuery.data?.connected
              ? garminStatusQuery.data?.requires_reauth
                ? 'Re-auth needed'
                : 'Connected'
              : 'Not connected'}
          </StatusPill>
          {garminStatusQuery.data?.garmin_email && (
            <HelperText>Connected as {garminStatusQuery.data.garmin_email}</HelperText>
          )}
          <InlineForm>
            <Field>
              Garmin Email
              <input
                type="email"
                value={garminEmail}
                onChange={(event) => setGarminEmail(event.target.value)}
                placeholder="you@example.com"
              />
            </Field>
            <Field>
              Garmin Password
              <input
                type="password"
                value={garminPassword}
                onChange={(event) => setGarminPassword(event.target.value)}
                placeholder="••••••••"
              />
            </Field>
          </InlineForm>
          <PadButtonRow>
            <PadButton
              $variant="primary"
              onClick={handleGarminConnect}
              disabled={!garminEmail || !garminPassword || connectMutation.isPending}
            >
              {garminStatusQuery.data?.connected ? 'Update Credentials' : 'Connect Garmin'}
            </PadButton>
            {garminStatusQuery.data?.connected && (
              <PadButton
                onClick={() => reauthMutation.mutate()}
                disabled={reauthMutation.isPending}
              >
                Re-auth
              </PadButton>
            )}
          </PadButtonRow>
          <HelperText>
            Credentials are stored encrypted and only used to refresh Garmin tokens.
          </HelperText>
        </LilyPadCard>
      </SectionGrid>
    </SceneLayout>
  );
}
