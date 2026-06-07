import styled, { keyframes } from 'styled-components';
import { Card } from '../common/Card';
import { useMorningBrief } from '../../hooks/useMorningBrief';
import { reducedMotion } from '../../styles/animations';

// ── Animations ───────────────────────────────────────────────────────────────

const shimmer = keyframes`
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
`;

// ── Shell ────────────────────────────────────────────────────────────────────

const HeroCard = styled(Card)`
  background: ${({ theme }) =>
    theme.mode === 'dark'
      ? 'rgba(30, 42, 68, 0.98)'
      : 'rgba(240, 248, 255, 0.97)'};
  border-color: ${({ theme }) => theme.colors.accent}44;
  margin-bottom: clamp(10px, 1.5vh, 20px);
`;

const MetaRow = styled.div`
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 10px;
`;

const DateLabel = styled.span`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.78rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: ${({ theme }) => theme.colors.textSecondary};
`;

// ── Paragraph ─────────────────────────────────────────────────────────────────

const BriefText = styled.p`
  margin: 0 0 14px;
  font-family: ${({ theme }) => theme.fonts.body};
  font-size: clamp(0.88rem, 1.5vw, 0.97rem);
  line-height: 1.65;
  color: ${({ theme }) => theme.colors.textPrimary};
`;

// ── Chips ─────────────────────────────────────────────────────────────────────

const ChipRow = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
`;

const NavChip = styled.a`
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 12px;
  border-radius: 20px;
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  background: ${({ theme }) => theme.colors.overlay};
  color: ${({ theme }) => theme.colors.textSecondary};
  font-family: ${({ theme }) => theme.fonts.body};
  font-size: 0.76rem;
  text-decoration: none;
  transition: background 0.15s ease, border-color 0.15s ease;
  ${reducedMotion}

  &:hover {
    background: ${({ theme }) => theme.colors.overlayHover};
    border-color: ${({ theme }) => theme.colors.accent}66;
  }

  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }
`;

// Article chips share the same anchor styles as NavChip
const ArticleChipAnchor = NavChip;

// ── Skeleton ──────────────────────────────────────────────────────────────────

const SkeletonLine = styled.div<{ $w?: string }>`
  height: 14px;
  width: ${({ $w }) => $w ?? '100%'};
  border-radius: 7px;
  background: linear-gradient(
    90deg,
    ${({ theme }) => theme.colors.overlay} 25%,
    ${({ theme }) => theme.colors.overlayHover} 50%,
    ${({ theme }) => theme.colors.overlay} 75%
  );
  background-size: 200% 100%;
  animation: ${shimmer} 1.6s ease-in-out infinite;
  ${reducedMotion}
`;

const SkeletonStack = styled.div`
  display: flex;
  flex-direction: column;
  gap: 10px;
`;

function BriefSkeleton() {
  return (
    <SkeletonStack aria-busy="true" aria-label="Loading morning brief">
      <SkeletonLine $w="45%" />
      <SkeletonLine />
      <SkeletonLine $w="80%" />
      <SkeletonLine $w="60%" />
    </SkeletonStack>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function MorningBriefCard() {
  const { paragraph, sources, isReady, isPartiallyReady } = useMorningBrief();

  const today = new Date().toLocaleDateString(undefined, {
    weekday: 'long',
    month: 'short',
    day: 'numeric',
  });

  const isLoading = !isPartiallyReady && !isReady;

  if (isLoading) {
    return (
      <HeroCard>
        <MetaRow>
          <DateLabel>{today}</DateLabel>
        </MetaRow>
        <BriefSkeleton />
      </HeroCard>
    );
  }

  return (
    <HeroCard aria-label="Morning brief">
      <MetaRow>
        <DateLabel>{today}</DateLabel>
        {!isReady && (
          <DateLabel style={{ opacity: 0.6 }}>loading reads…</DateLabel>
        )}
      </MetaRow>

      {paragraph ? (
        <BriefText>{paragraph}</BriefText>
      ) : (
        <BriefText style={{ opacity: 0.6 }}>Brief unavailable — check back after data syncs.</BriefText>
      )}

      <ChipRow>
        <NavChip
          href="/body"
          aria-label="Body — navigate to body metrics"
        >
          Body · Health
        </NavChip>

        {sources[0] && (
          <ArticleChipAnchor
            href={sources[0].url}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={`Read: ${sources[0].title}`}
          >
            Read · {sources[0].title.length > 48
              ? `${sources[0].title.slice(0, 48)}…`
              : sources[0].title}
          </ArticleChipAnchor>
        )}

        {sources[1] && (
          <ArticleChipAnchor
            href={sources[1].url}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={`Read: ${sources[1].title}`}
          >
            Read · {sources[1].title.length > 48
              ? `${sources[1].title.slice(0, 48)}…`
              : sources[1].title}
          </ArticleChipAnchor>
        )}
      </ChipRow>
    </HeroCard>
  );
}
