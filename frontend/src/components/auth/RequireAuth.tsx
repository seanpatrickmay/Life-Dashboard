import { Navigate, Outlet, useLocation } from 'react-router-dom';
import styled from 'styled-components';

import { useAuth } from '../../hooks/useAuth';

const LoadingShell = styled.div`
  padding: 40px;
  text-align: center;
  color: ${({ theme }) => theme.colors.textPrimary};
  font-family: ${({ theme }) => theme.fonts.heading};
  letter-spacing: 0.2em;
  text-transform: uppercase;
`;

export function RequireAuth() {
  const location = useLocation();
  const { data, isLoading, isError } = useAuth();

  if (isLoading) {
    return <LoadingShell>Loading...</LoadingShell>;
  }

  if (isError || !data?.user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <Outlet />;
}
