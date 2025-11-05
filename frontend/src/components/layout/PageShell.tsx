import { PropsWithChildren } from 'react';
import styled from 'styled-components';
import { Link, useLocation } from 'react-router-dom';

const Frame = styled.div`
  padding: 32px;
  max-width: 1200px;
  margin: 0 auto;
`;

const Nav = styled.nav`
  display: flex;
  gap: 16px;
  margin-bottom: 32px;

  a {
    font-family: ${({ theme }) => theme.fonts.heading};
    font-size: 0.85rem;
    text-transform: uppercase;
    color: ${({ theme }) => theme.colors.nightNavy};
    opacity: 0.6;
    text-decoration: none;

    &.active {
      opacity: 1;
      color: ${({ theme }) => theme.colors.lilyLilac};
    }
  }
`;

const Background = styled.div`
  background: linear-gradient(135deg, rgba(126, 200, 227, 0.4), rgba(162, 138, 214, 0.4));
  border-radius: 32px;
  padding: 24px;
  box-shadow: ${({ theme }) => theme.shadows.soft};
`;

export function PageShell({ children }: PropsWithChildren) {
  const { pathname } = useLocation();
  return (
    <Frame>
      <Nav>
        <Link className={pathname === '/' ? 'active' : ''} to="/">
          Dashboard
        </Link>
        <Link className={pathname.startsWith('/insights') ? 'active' : ''} to="/insights">
          Insights
        </Link>
        <Link className={pathname.startsWith('/settings') ? 'active' : ''} to="/settings">
          Settings
        </Link>
      </Nav>
      <Background>{children}</Background>
    </Frame>
  );
}
