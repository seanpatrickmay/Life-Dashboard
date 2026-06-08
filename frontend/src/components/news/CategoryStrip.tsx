import styled from 'styled-components';
import { PixelChip } from '../common/PixelChip';
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

const CATEGORY_ORDER: Category[] = ['tech', 'science', 'world', 'culture', 'history', 'business', 'wikipedia'];

export function CategoryStrip({ active, counts, onChange }: CategoryStripProps) {
  return (
    <Strip role="group" aria-label="Filter by category">
      <PixelChip
        aria-pressed={active === 'all'}
        active={active === 'all'}
        onClick={() => onChange('all')}
      >
        All
      </PixelChip>
      {CATEGORY_ORDER.map(cat => {
        const count = counts?.[cat];
        return (
          <PixelChip
            key={cat}
            aria-pressed={active === cat}
            active={active === cat}
            onClick={() => onChange(cat)}
          >
            {CATEGORY_LABELS[cat]}{count !== undefined ? ` (${count})` : ''}
          </PixelChip>
        );
      })}
    </Strip>
  );
}
