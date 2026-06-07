import styled from 'styled-components';
import { CATEGORY_LABELS, type Category } from '../../services/newsFeedService';

export type CategoryFilter = Category | 'all';

interface CategoryStripProps {
  active: CategoryFilter;
  counts?: Partial<Record<Category, number>>;
  onChange: (cat: CategoryFilter) => void;
}

const Strip = styled.div`
  display: flex;
  gap: 6px;
  overflow-x: auto;
  scrollbar-width: none;
  -ms-overflow-style: none;
  &::-webkit-scrollbar { display: none; }
  padding-bottom: 2px;
`;

const Pill = styled.button<{ $active: boolean }>`
  flex-shrink: 0;
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.68rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  padding: 5px 12px;
  border-radius: 999px;
  border: 1px solid ${({ theme, $active }) =>
    $active ? (theme.palette?.pond?.['200'] ?? '#7ED7C4') : theme.colors.borderSubtle};
  background: ${({ theme, $active }) =>
    $active ? (theme.palette?.pond?.['200'] ?? '#7ED7C4') + '22' : 'transparent'};
  color: ${({ theme, $active }) =>
    $active ? (theme.palette?.pond?.['200'] ?? '#7ED7C4') : 'inherit'};
  cursor: pointer;
  opacity: ${({ $active }) => ($active ? 1 : 0.55)};
  transition: all 0.15s ease;

  &:hover {
    opacity: 1;
    border-color: ${({ theme }) => theme.palette?.pond?.['200'] ?? '#7ED7C4'};
  }

  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }
`;

const CATEGORY_ORDER: Category[] = ['tech', 'science', 'world', 'culture', 'history', 'business', 'wikipedia'];

export function CategoryStrip({ active, counts, onChange }: CategoryStripProps) {
  return (
    <Strip role="group" aria-label="Filter by category">
      <Pill
        aria-pressed={active === 'all'}
        $active={active === 'all'}
        onClick={() => onChange('all')}
      >
        All
      </Pill>
      {CATEGORY_ORDER.map(cat => {
        const count = counts?.[cat];
        return (
          <Pill
            key={cat}
            aria-pressed={active === cat}
            $active={active === cat}
            onClick={() => onChange(cat)}
          >
            {CATEGORY_LABELS[cat]}{count !== undefined ? ` (${count})` : ''}
          </Pill>
        );
      })}
    </Strip>
  );
}
