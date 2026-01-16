import { useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import type { Location } from 'react-router-dom';
import styled from 'styled-components';
import { palette } from '../theme/monetTheme';
import { enterGuestMode, exitGuestMode, isGuestDemoEnabled } from '../demo/guest/guestMode';

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
  background: rgba(12, 20, 40, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.12);
  box-shadow: 0 24px 60px rgba(4, 10, 24, 0.4);
  backdrop-filter: blur(10px);
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
  color: rgba(255, 175, 175, 0.95);
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
  border: 1px solid rgba(255, 255, 255, 0.2);
  padding: 14px 18px;
  font-family: ${({ theme }) => theme.fonts.heading};
  letter-spacing: 0.18em;
  text-transform: uppercase;
  font-size: 0.78rem;
  color: ${({ theme }) => theme.colors.textPrimary};
  background: linear-gradient(120deg, rgba(77, 160, 255, 0.25), rgba(240, 210, 140, 0.2));
  box-shadow: 0 10px 30px rgba(17, 33, 70, 0.4);
  cursor: pointer;
  transition: transform 0.2s ease, opacity 0.2s ease;
  &:hover {
    transform: translateY(-1px);
    opacity: 0.95;
  }
`;

const GuestButton = styled.button`
  width: 100%;
  border-radius: 999px;
  border: 1px dashed rgba(255, 255, 255, 0.25);
  padding: 14px 18px;
  font-family: ${({ theme }) => theme.fonts.heading};
  letter-spacing: 0.18em;
  text-transform: uppercase;
  font-size: 0.75rem;
  color: ${({ theme }) => theme.colors.textPrimary};
  background: rgba(16, 22, 36, 0.5);
  cursor: pointer;
  transition: opacity 0.2s ease, transform 0.2s ease;
  &:hover {
    opacity: 0.95;
    transform: translateY(-1px);
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
    border: 2px solid ${palette.bloom['300']};
    background: rgba(8, 14, 28, 0.6);
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
    background: ${palette.bloom['300']};
    opacity: 0;
    transform: scale(0.4);
    transition: opacity 0.2s ease, transform 0.2s ease;
  }

  input[type='checkbox']:checked {
    background: rgba(77, 160, 255, 0.25);
  }

  input[type='checkbox']:checked::after {
    opacity: 1;
    transform: scale(1);
  }

  input[type='checkbox']:focus-visible {
    outline: 2px solid rgba(240, 210, 140, 0.7);
    outline-offset: 2px;
  }
`;

const Divider = styled.div`
  height: 1px;
  margin: 10px 0;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.15), transparent);
`;

export function LoginPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [remember, setRemember] = useState(true);
  const authError = new URLSearchParams(location.search).get('auth_error');
  const guestEnabled = isGuestDemoEnabled();

  const loginUrl = useMemo(() => {
    const apiBase = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';
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
