/**
 * TuneDrawer — Interest Profile controls absorbed into the Read tab.
 * - Inits from getBoostedTopics()/getMutedTopics()/getExplorationSlots()
 * - Saves on toggle (persisted to localStorage)
 * - On close: invalidates NEWS_CURATED_KEY so feed re-ranks without network
 * - Mobile = bottom sheet (≥85vh); desktop = right slide-in panel
 * - Visible one-tap controls: [+ boost] [✕ mute] per topic (wireframe R3)
 */
import { useState, useCallback, useEffect, useRef } from 'react';
import styled, { keyframes } from 'styled-components';
import { reducedMotion } from '../../styles/animations';
import { pixelPanel } from '../../theme/surfaces';
import { PixelButton } from '../common/PixelButton';
import { PixelField } from '../common/PixelField';
import { useQueryClient } from '@tanstack/react-query';
import {
  getBoostedTopics,
  saveBoostedTopics,
  getMutedTopics,
  saveMutedTopics,
  getExplorationSlots,
  saveExplorationSlots,
  loadProfile,
} from '../../services/interestProfile';
import { NEWS_CURATED_KEY } from '../../hooks/useNewsFeed';
import { useNewsFeed } from '../../hooks/useNewsFeed';

/* ─── Styled ─────────────────────────────────────── */

const slideUp = keyframes`
  from { transform: translateY(100%); opacity: 0; }
  to   { transform: translateY(0);    opacity: 1; }
`;

const slideIn = keyframes`
  from { transform: translateX(100%); opacity: 0; }
  to   { transform: translateX(0);    opacity: 1; }
`;

const Backdrop = styled.div`
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  z-index: 200;
  display: flex;
  align-items: flex-end;
  justify-content: flex-end;

  @media (min-width: 700px) {
    align-items: stretch;
  }
`;

const Panel = styled.div`
  ${pixelPanel}
  border-top-left-radius: ${({ theme }) => theme.radii.pixel};
  border-top-right-radius: ${({ theme }) => theme.radii.pixel};
  border-bottom-left-radius: 0;
  border-bottom-right-radius: 0;
  padding: 20px 20px 32px;
  width: 100%;
  max-height: 90vh;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
  animation: ${slideUp} 0.25s ease-out both;

  @media (min-width: 700px) {
    width: 380px;
    max-height: 100vh;
    border-radius: ${({ theme }) => theme.radii.pixel};
    border-right: none;
    animation: ${slideIn} 0.25s ease-out both;
  }

  ${reducedMotion}

  scrollbar-width: thin;
  scrollbar-color: ${({ theme }) => theme.colors.scrollThumb} transparent;
`;

const Header = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
`;

const Title = styled.h2`
  margin: 0;
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: clamp(1rem, 1.8vw, 1.2rem);
  letter-spacing: 0.15em;
  text-transform: uppercase;
`;

const CloseBtn = styled.button`
  background: none;
  border: none;
  cursor: pointer;
  color: inherit;
  font-size: 1.2rem;
  opacity: 0.5;
  line-height: 1;
  padding: 4px;
  &:hover { opacity: 1; }
  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }
`;

const SectionTitle = styled.div`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.7rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  opacity: 0.5;
`;

const TopicGrid = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
`;

const TopicChip = styled.div<{ $muted: boolean }>`
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px 4px 10px;
  border-radius: 999px;
  border: 1px solid ${({ theme, $muted }) =>
    $muted ? theme.colors.borderSubtle : theme.colors.borderSubtle};
  background: ${({ theme, $muted }) =>
    $muted ? 'transparent' : theme.colors.overlay};
  font-size: 0.72rem;
  opacity: ${({ $muted }) => ($muted ? 0.35 : 1)};
  text-decoration: ${({ $muted }) => ($muted ? 'line-through' : 'none')};
`;

const ChipLabel = styled.span`
  line-height: 1;
`;

const ChipAction = styled.button<{ $variant: 'boost' | 'mute'; $active?: boolean }>`
  background: none;
  border: 1px solid ${({ theme, $active, $variant }) =>
    $active
      ? $variant === 'boost'
        ? theme.palette?.pond?.['200'] ?? '#7ED7C4'
        : 'rgba(255,100,100,0.6)'
      : theme.colors.borderSubtle};
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.58rem;
  padding: 1px 4px;
  color: ${({ theme, $active, $variant }) =>
    $active
      ? $variant === 'boost'
        ? theme.palette?.pond?.['200'] ?? '#7ED7C4'
        : 'rgba(255,120,120,0.9)'
      : 'inherit'};
  opacity: ${({ $active }) => ($active ? 1 : 0.45)};
  line-height: 1.4;
  transition: all 0.12s ease;
  ${reducedMotion}
  &:hover { opacity: 1; }
  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }
`;

const AddRow = styled.div`
  display: flex;
  gap: 8px;
`;

const AddInput = styled(PixelField)`
  flex: 1;
  font-size: 0.8rem;
  padding: 6px 10px;
`;

const AddBtn = styled(PixelButton).attrs({ variant: 'secondary' })`
  font-size: 0.68rem;
  letter-spacing: 0.08em;
  padding: 6px 14px;
`;

const SliderRow = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
`;

const SliderLabel = styled.label`
  font-size: 0.8rem;
  min-width: 110px;
  opacity: 0.7;
`;

const Slider = styled.input`
  flex: 1;
  accent-color: ${({ theme }) => theme.palette?.pond?.['200'] ?? '#7ED7C4'};
`;

const SliderValue = styled.span`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.7rem;
  letter-spacing: 0.08em;
  min-width: 45px;
  text-align: center;
`;

const SliderDesc = styled.p`
  margin: 0;
  font-size: 0.75rem;
  opacity: 0.4;
  line-height: 1.5;
`;

const HistorySection = styled.div`
  display: flex;
  flex-direction: column;
  gap: 12px;
`;

const LayerName = styled.span`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.65rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  opacity: 0.45;
`;

const CategoryRow = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 2px 0;
`;

const CategoryLabel = styled.span`
  font-size: 0.75rem;
  min-width: 72px;
  text-transform: capitalize;
  opacity: 0.8;
`;

const Bar = styled.div<{ $width: number; $color: string }>`
  height: 5px;
  width: ${({ $width }) => Math.max($width, 2)}%;
  max-width: 160px;
  background: ${({ $color }) => $color};
  border-radius: 3px;
`;

const ReadCount = styled.span`
  font-size: 0.65rem;
  opacity: 0.3;
  min-width: 36px;
  text-align: right;
`;

const ClearBtn = styled(PixelButton).attrs({ variant: 'ghost' })`
  font-size: 0.65rem;
  letter-spacing: 0.08em;
  padding: 6px 14px;
  align-self: flex-start;
  opacity: 0.55;
  &:hover:not(:disabled) { opacity: 1; }
`;

const CATEGORY_COLORS: Record<string, string> = {
  tech: 'rgba(120, 180, 255, 0.7)',
  science: 'rgba(130, 220, 180, 0.7)',
  world: 'rgba(255, 180, 120, 0.7)',
  culture: 'rgba(220, 160, 255, 0.7)',
  history: 'rgba(255, 210, 130, 0.7)',
  business: 'rgba(180, 200, 240, 0.7)',
  wikipedia: 'rgba(200, 200, 200, 0.7)',
};

const LAYER_NAMES = {
  ephemeral: { label: 'This Week', halfLife: '3-day half-life' },
  contextual: { label: 'This Month', halfLife: '21-day half-life' },
  stable: { label: 'Enduring', halfLife: '120-day half-life' },
} as const;

/* ─── Component ──────────────────────────────────── */

interface TuneDrawerProps {
  onClose: () => void;
  /** All topics from profile summary — shown alongside custom additions */
  profileTopics?: string[];
}

const FOCUSABLE = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(', ');

export function TuneDrawer({ onClose, profileTopics = [] }: TuneDrawerProps) {
  const queryClient = useQueryClient();
  const { profileQuery } = useNewsFeed();
  const panelRef = useRef<HTMLDivElement>(null);
  const closeBtnRef = useRef<HTMLButtonElement>(null);
  const previousFocusRef = useRef<Element | null>(null);

  // Init from persistent storage
  const [boostedTopics, setBoostedTopics] = useState<Set<string>>(
    () => new Set(getBoostedTopics()),
  );
  const [mutedTopics, setMutedTopics] = useState<Set<string>>(
    () => new Set(getMutedTopics()),
  );
  const [explorationSlots, setExplorationSlots] = useState<number>(getExplorationSlots);
  const [customTopics, setCustomTopics] = useState<string[]>([]);
  const [newTopic, setNewTopic] = useState('');

  const allTopics = [...(profileQuery.data?.topics ?? profileTopics), ...customTopics];
  const profile = loadProfile();

  const maxReads = (() => {
    let max = 1;
    for (const layer of [profile.ephemeral, profile.contextual, profile.stable]) {
      for (const entry of Object.values(layer.categoryAffinity)) {
        if (entry.reads > max) max = entry.reads;
      }
    }
    return max;
  })();

  const handleClose = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: NEWS_CURATED_KEY });
    onClose();
  }, [queryClient, onClose]);

  // Move focus into dialog on open; restore on close
  useEffect(() => {
    previousFocusRef.current = document.activeElement;
    const firstFocusable = closeBtnRef.current ??
      panelRef.current?.querySelector<HTMLElement>(FOCUSABLE) ?? null;
    firstFocusable?.focus();

    return () => {
      (previousFocusRef.current as HTMLElement | null)?.focus?.();
    };
  }, []);

  // Close on Escape; trap Tab/Shift+Tab inside panel
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        handleClose();
        return;
      }
      if (e.key !== 'Tab' || !panelRef.current) return;

      const focusable = Array.from(
        panelRef.current.querySelectorAll<HTMLElement>(FOCUSABLE),
      ).filter(el => !el.closest('[disabled]'));

      if (focusable.length === 0) { e.preventDefault(); return; }

      const first = focusable[0];
      const last = focusable[focusable.length - 1];

      if (e.shiftKey) {
        if (document.activeElement === first) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [handleClose]);

  const toggleBoost = useCallback((topic: string) => {
    setBoostedTopics(prev => {
      const next = new Set(prev);
      if (next.has(topic)) {
        next.delete(topic);
      } else {
        next.add(topic);
        // Cross-clear: remove from muted and persist immediately
        setMutedTopics(p => {
          const n = new Set(p);
          if (n.has(topic)) {
            n.delete(topic);
            saveMutedTopics([...n]);
          }
          return n;
        });
      }
      saveBoostedTopics([...next]);
      return next;
    });
  }, []);

  const toggleMute = useCallback((topic: string) => {
    setMutedTopics(prev => {
      const next = new Set(prev);
      if (next.has(topic)) {
        next.delete(topic);
      } else {
        next.add(topic);
        // Cross-clear: remove from boosted and persist immediately
        setBoostedTopics(p => {
          const n = new Set(p);
          if (n.has(topic)) {
            n.delete(topic);
            saveBoostedTopics([...n]);
          }
          return n;
        });
      }
      saveMutedTopics([...next]);
      return next;
    });
  }, []);

  const handleAddTopic = useCallback(() => {
    const trimmed = newTopic.trim().toLowerCase();
    if (trimmed && !customTopics.includes(trimmed) && !allTopics.includes(trimmed)) {
      setCustomTopics(prev => [...prev, trimmed]);
      setNewTopic('');
    }
  }, [newTopic, customTopics, allTopics]);

  const handleExplorationChange = (v: number) => {
    setExplorationSlots(v);
    saveExplorationSlots(v);
  };

  const handleClearOverrides = () => {
    setBoostedTopics(new Set());
    setMutedTopics(new Set());
    saveBoostedTopics([]);
    saveMutedTopics([]);
  };

  return (
    <Backdrop onClick={e => { if (e.target === e.currentTarget) handleClose(); }}>
      <Panel ref={panelRef} role="dialog" aria-modal="true" aria-label="Tune your feed">
        <Header>
          <Title>Tune your feed</Title>
          <CloseBtn ref={closeBtnRef} onClick={handleClose} aria-label="Close">✕</CloseBtn>
        </Header>

        {/* Topics */}
        {allTopics.length > 0 && (
          <div>
            <SectionTitle>Topics</SectionTitle>
            <div style={{ marginTop: 10 }}>
              <div style={{ marginBottom: 6, fontSize: '0.62rem', opacity: 0.35, letterSpacing: '0.06em' }}>
                + boost · ✕ mute · strikethrough = muted
              </div>
              <TopicGrid>
                {allTopics.map(topic => {
                  const isMuted = mutedTopics.has(topic);
                  const isBoosted = boostedTopics.has(topic);
                  return (
                    <TopicChip key={topic} $muted={isMuted}>
                      <ChipAction
                        $variant="boost"
                        $active={isBoosted}
                        onClick={() => toggleBoost(topic)}
                        aria-label={isBoosted ? `Remove boost from ${topic}` : `Boost ${topic}`}
                        aria-pressed={isBoosted}
                      >
                        +
                      </ChipAction>
                      <ChipLabel>{topic}</ChipLabel>
                      <ChipAction
                        $variant="mute"
                        $active={isMuted}
                        onClick={() => toggleMute(topic)}
                        aria-label={isMuted ? `Unmute ${topic}` : `Mute ${topic}`}
                        aria-pressed={isMuted}
                      >
                        ✕
                      </ChipAction>
                    </TopicChip>
                  );
                })}
              </TopicGrid>
            </div>

            <AddRow style={{ marginTop: 10 }}>
              <AddInput
                value={newTopic}
                onChange={e => setNewTopic(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleAddTopic()}
                placeholder="+ add a topic…"
                aria-label="Add a topic"
              />
              <AddBtn onClick={handleAddTopic}>Add</AddBtn>
            </AddRow>
          </div>
        )}

        {/* Exploration slider */}
        <div>
          <SectionTitle>Exploration</SectionTitle>
          <SliderRow style={{ marginTop: 10 }}>
            <SliderLabel htmlFor="tune-exploration">Discovery picks</SliderLabel>
            <Slider
              id="tune-exploration"
              type="range"
              min={0}
              max={8}
              value={explorationSlots}
              onChange={e => handleExplorationChange(Number(e.target.value))}
              aria-label="Exploration slots"
            />
            <SliderValue>{explorationSlots}/8</SliderValue>
          </SliderRow>
          <SliderDesc style={{ marginTop: 6 }}>
            {explorationSlots === 0
              ? 'All picks based on your interests.'
              : explorationSlots >= 6
              ? 'Heavy exploration — most picks from unfamiliar categories.'
              : `${explorationSlots} picks from categories you don't usually read.`}
          </SliderDesc>
        </div>

        {/* Reading history */}
        <HistorySection>
          <SectionTitle>Reading History</SectionTitle>
          {(['ephemeral', 'contextual', 'stable'] as const).map(layerKey => {
            const layer = profile[layerKey];
            const meta = LAYER_NAMES[layerKey];
            const categories = Object.entries(layer.categoryAffinity)
              .sort((a, b) => b[1].reads - a[1].reads);

            if (categories.length === 0) return null;

            return (
              <div key={layerKey} style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <LayerName>{meta.label} <span style={{ opacity: 0.4, fontSize: '0.58rem' }}>({meta.halfLife})</span></LayerName>
                {categories.map(([cat, entry]) => (
                  <CategoryRow key={cat}>
                    <CategoryLabel>{cat}</CategoryLabel>
                    <Bar
                      $width={(entry.reads / maxReads) * 100}
                      $color={CATEGORY_COLORS[cat] || 'rgba(200,200,200,0.7)'}
                    />
                    <ReadCount>{entry.reads}r</ReadCount>
                  </CategoryRow>
                ))}
              </div>
            );
          })}
        </HistorySection>

        <ClearBtn onClick={handleClearOverrides} aria-label="Clear all boost and mute overrides">
          Clear all overrides
        </ClearBtn>
      </Panel>
    </Backdrop>
  );
}
