import styled from 'styled-components';
import { Link } from 'react-router-dom';
import { reducedMotion } from '../../styles/animations';

export const CTARow = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 4px;
`;

export const CTALink = styled(Link)`
  display: inline-flex;
  align-items: center;
  padding: 7px 16px;
  min-height: 44px;
  box-sizing: border-box;
  border-radius: 999px;
  border: 1px solid ${({ theme }) => theme.colors.accent}55;
  background: ${({ theme }) => theme.colors.overlay};
  color: ${({ theme }) => theme.colors.accent};
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.74rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  text-decoration: none;
  transition: background 0.15s ease, border-color 0.15s ease;
  ${reducedMotion}

  &:hover {
    background: ${({ theme }) => theme.colors.overlayHover};
    border-color: ${({ theme }) => theme.colors.accent}99;
  }

  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }
`;

/**
 * Calendar + Projects CTAs — used by both SummaryChips (mobile) and the
 * desktop Today grid. Keeps the two in sync without duplication.
 */
export function SecondaryNavCTAs() {
  return (
    <CTARow>
      <CTALink to="/calendar" aria-label="Open calendar">
        Open calendar →
      </CTALink>
      <CTALink to="/projects" aria-label="Open board">
        Open board →
      </CTALink>
    </CTARow>
  );
}
