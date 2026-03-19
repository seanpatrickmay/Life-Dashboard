import { useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import type { Location } from 'react-router-dom';
import styled from 'styled-components';

import { enterGuestMode, exitGuestMode, isGuestDemoEnabled } from '../demo/guest/guestMode';
import { getApiBaseUrl } from '../services/api';

const Wrap = styled.div`
  min-height: 70vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 16px;
`;

const Card = styled.div`
  width: min(520px, 92vw);
  border-radius: 28px;
  padding: clamp(24px, 3vw, 36px);
  background: ${({ theme }) => theme.colors.backgroundCard};
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  box-shadow: ${({ theme }) => theme.shadows.soft};
  color: ${({ theme }) => theme.colors.textPrimary};
`;

const Title = styled.h1`
  margin: 0 0 12px;
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: clamp(1.6rem, 2.4vw, 2.1rem);
  letter-spacing: 0.12em;
  text-transform: uppercase;
`;

const Subtitle = styled.p`
  margin: 0 0 24px;
  color: ${({ theme }) => theme.colors.textSecondary};
  font-size: 0.95rem;
  line-height: 1.5;
`;

const ErrorText = styled.p`
  margin: -10px 0 18px;
  color: ${({ theme }) => theme.colors.danger};
  font-size: 0.85rem;
`;

const Actions = styled.div`
  display: flex;
  flex-direction: column;
  gap: 16px;
`;

const GoogleButton = styled.button`
  width: 100%;
  border-radius: 999px;
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  padding: 14px 18px;
  font-family: ${({ theme }) => theme.fonts.heading};
  letter-spacing: 0.18em;
  text-transform: uppercase;
  font-size: 0.78rem;
  color: ${({ theme }) => theme.colors.textPrimary};
  background: ${({ theme }) => theme.colors.accentSubtle};
  box-shadow: ${({ theme }) => theme.shadows.soft};
  cursor: pointer;
  transition: transform 0.2s ease, opacity 0.2s ease;
  &:hover {
    transform: translateY(-1px);
    opacity: 0.95;
  }
  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }
`;

const GuestButton = styled.button`
  width: 100%;
  border-radius: 999px;
  border: 1px dashed ${({ theme }) => theme.colors.borderSubtle};
  padding: 14px 18px;
  font-family: ${({ theme }) => theme.fonts.heading};
  letter-spacing: 0.18em;
  text-transform: uppercase;
  font-size: 0.75rem;
  color: ${({ theme }) => theme.colors.textPrimary};
  background: ${({ theme }) => theme.colors.surfaceRaised};
  cursor: pointer;
  transition: opacity 0.2s ease, transform 0.2s ease;
  &:hover {
    opacity: 0.95;
    transform: translateY(-1px);
  }
  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }
`;

const RememberRow = styled.label`
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 0.85rem;
  color: ${({ theme }) => theme.colors.textSecondary};
  input[type='checkbox'] {
    appearance: none;
    width: 18px;
    height: 18px;
    border-radius: 6px;
    border: 2px solid ${({ theme }) => theme.colors.borderSubtle};
    background: ${({ theme }) => theme.colors.surfaceInset};
    display: grid;
    place-items: center;
    cursor: pointer;
    transition: background 0.2s ease, border-color 0.2s ease, transform 0.1s ease;
  }

  input[type='checkbox']::after {
    content: '';
    width: 10px;
    height: 10px;
    border-radius: 3px;
    background: ${({ theme }) => theme.colors.accent};
    opacity: 0;
    transform: scale(0.4);
    transition: opacity 0.2s ease, transform 0.2s ease;
  }

  input[type='checkbox']:checked {
    background: ${({ theme }) => theme.colors.accentSubtle};
  }

  input[type='checkbox']:checked::after {
    opacity: 1;
    transform: scale(1);
  }

  input[type='checkbox']:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }
`;

const Divider = styled.div`
  height: 1px;
  margin: 10px 0;
  background: linear-gradient(90deg, transparent, ${({ theme }) => theme.colors.borderSubtle}, transparent);
`;

export function LoginPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [remember, setRemember] = useState(true);
  const authError = new URLSearchParams(location.search).get('auth_error');
  const guestEnabled = isGuestDemoEnabled();

  const loginUrl = useMemo(() => {
    const apiBase = getApiBaseUrl();
    const fromPath = (location.state as { from?: Location })?.from?.pathname ?? '/';
    const redirectTarget = `${window.location.origin}${fromPath}`;
    const params = new URLSearchParams({
      redirect: redirectTarget,
      remember_me: String(remember)
    });
    return `${apiBase}/api/auth/google/login?${params.toString()}`;
  }, [location.state, remember]);

  const handleLogin = () => {
    exitGuestMode();
    window.location.href = loginUrl;
  };

  const handleGuest = () => {
    enterGuestMode();
    navigate('/', { replace: true });
  };

  return (
    <Wrap>
      <Card>
        <Title>Life Dashboard</Title>
        <Subtitle>
          Sign in to sync your Garmin metrics, refine your nutrition plan, and keep the Monet assistant tuned to your rhythms.
        </Subtitle>
        {authError && <ErrorText>Sign-in failed. Please try again.</ErrorText>}
        <Actions>
          <GoogleButton type="button" onClick={handleLogin}>
            Continue with Google
          </GoogleButton>
          {guestEnabled ? (
            <GuestButton type="button" onClick={handleGuest}>
              Continue as Guest
            </GuestButton>
          ) : null}
          <Divider />
          <RememberRow>
            <input
              type="checkbox"
              checked={remember}
              onChange={(event) => setRemember(event.target.checked)}
            />
            Remember me on this device
          </RememberRow>
        </Actions>
      </Card>
    </Wrap>
  );
}
