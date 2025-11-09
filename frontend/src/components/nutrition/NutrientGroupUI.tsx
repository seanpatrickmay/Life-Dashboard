import styled from 'styled-components';

export const GROUP_ORDER = ['macro', 'vitamin', 'mineral'] as const;
export type GroupKey = (typeof GROUP_ORDER)[number];

export const GROUP_LABELS: Record<GroupKey, string> = {
  macro: 'Macros',
  vitamin: 'Vitamins',
  mineral: 'Minerals'
};

export const GroupSection = styled.div`
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 18px;
  background: rgba(0, 0, 0, 0.18);
  overflow: hidden;
`;

export const GroupHeader = styled.button`
  width: 100%;
  padding: 12px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 0.95rem;
  font-weight: 600;
  color: ${({ theme }) => theme.colors.textPrimary};
  background: transparent;
  border: none;
  cursor: pointer;
  text-align: left;
  letter-spacing: 0.05em;
`;

export const GroupBody = styled.div<{ $expanded: boolean }>`
  display: ${({ $expanded }) => ($expanded ? 'block' : 'none')};
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  padding: ${({ $expanded }) => ($expanded ? '12px 16px 16px' : '0 16px')};
`;

export const Chevron = styled.span<{ $expanded: boolean }>`
  display: inline-block;
  transition: transform 0.2s ease;
  transform: rotate(${({ $expanded }) => ($expanded ? 90 : 0)}deg);
`;

export const GroupEmpty = styled.p`
  opacity: 0.65;
  font-size: 0.85rem;
  margin: 6px 0 0;
`;
