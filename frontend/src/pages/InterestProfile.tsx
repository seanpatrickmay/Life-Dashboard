import { useState, useMemo, useCallback } from 'react';
import styled from 'styled-components';

import { Card } from '../components/common/Card';
import {
  loadProfile,
  type InterestProfile,
} from '../services/interestProfile';
import { useNewsFeed } from '../hooks/useNewsFeed';
import { fadeUp, reducedMotion } from '../styles/animations';

/* ─── Styled components ───────────────────────── */

const Page = styled.div`
  display: flex;
  flex-direction: column;
  gap: clamp(16px, 3vw, 28px);
  max-width: 700px;
  margin: 0 auto;
  animation: ${fadeUp} 0.45s ease-out both;
  ${reducedMotion}
`;

const Title = styled.h1`
  margin: 0;
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: clamp(1.1rem, 2.2vw, 1.35rem);
  letter-spacing: 0.2em;
  text-transform: uppercase;
`;

const Subtitle = styled.p`
  margin: 0;
  font-size: 0.82rem;
  opacity: 0.5;
  line-height: 1.5;
`;

const SectionTitle = styled.h2`
  margin: 0;
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.85rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  opacity: 0.6;
`;

const NarrativeCard = styled(Card)`
  font-size: 0.85rem;
  line-height: 1.6;
  opacity: 0.7;
  font-style: italic;
`;

const TopicGrid = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
`;

const TopicPill = styled.button<{ $active: boolean }>`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.7rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  padding: 6px 14px;
  border-radius: 999px;
  border: 1px solid ${({ theme, $active }) =>
    $active ? (theme.palette?.pond?.['200'] ?? '#7ED7C4') : theme.colors.borderSubtle};
  background: ${({ theme, $active }) =>
    $active ? (theme.palette?.pond?.['200'] ?? '#7ED7C4') + '22' : 'transparent'};
  color: ${({ theme, $active }) =>
    $active ? (theme.palette?.pond?.['200'] ?? '#7ED7C4') : 'inherit'};
  cursor: pointer;
  transition: all 0.15s ease;
  opacity: ${({ $active }) => $active ? 1 : 0.5};

  &:hover {
    opacity: 1;
    border-color: ${({ theme }) => theme.palette?.pond?.['200'] ?? '#7ED7C4'};
  }
  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }
`;

const LayerSection = styled.div`
  display: flex;
  flex-direction: column;
  gap: 8px;
`;

const LayerHeader = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
`;

const LayerName = styled.span`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.72rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  opacity: 0.5;
`;

const HalfLife = styled.span`
  font-size: 0.65rem;
  opacity: 0.3;
`;

const CategoryRow = styled.div`
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 0;
`;

const CategoryLabel = styled.span`
  font-size: 0.8rem;
  min-width: 80px;
  text-transform: capitalize;
`;

const Bar = styled.div<{ $width: number; $color: string }>`
  height: 6px;
  width: ${({ $width }) => Math.max($width, 2)}%;
  max-width: 200px;
  background: ${({ $color }) => $color};
  border-radius: 3px;
  transition: width 0.3s ease;
`;

const ReadCount = styled.span`
  font-size: 0.7rem;
  opacity: 0.35;
  min-width: 40px;
  text-align: right;
`;

const SliderRow = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
`;

const SliderLabel = styled.label`
  font-size: 0.82rem;
  min-width: 120px;
`;

const Slider = styled.input`
  flex: 1;
  accent-color: ${({ theme }) => theme.palette?.pond?.['200'] ?? '#7ED7C4'};
`;

const SliderValue = styled.span`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.72rem;
  letter-spacing: 0.1em;
  min-width: 50px;
  text-align: center;
`;

const AddTopicRow = styled.div`
  display: flex;
  gap: 8px;
`;

const TopicInput = styled.input`
  flex: 1;
  font-size: 0.82rem;
  padding: 6px 12px;
  border-radius: 8px;
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  background: ${({ theme }) => theme.colors.overlay};
  color: inherit;
  font-family: inherit;

  &:focus {
    outline: 2px solid ${({ theme }) => theme.colors.focusRing};
    outline-offset: 2px;
  }
`;

const AddButton = styled.button`
  font-family: ${({ theme }) => theme.fonts.heading};
  font-size: 0.72rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  padding: 6px 16px;
  border-radius: 8px;
  border: 1px solid ${({ theme }) => theme.colors.borderSubtle};
  background: ${({ theme }) => theme.colors.overlay};
  color: inherit;
  cursor: pointer;

  &:hover {
    background: ${({ theme }) => theme.colors.overlayActive};
  }
`;

const CATEGORY_COLORS: Record<string, string> = {
  tech: 'rgba(120, 180, 255, 0.85)',
  science: 'rgba(130, 220, 180, 0.85)',
  world: 'rgba(255, 180, 120, 0.85)',
  culture: 'rgba(220, 160, 255, 0.85)',
  history: 'rgba(255, 210, 130, 0.85)',
  business: 'rgba(180, 200, 240, 0.85)',
  wikipedia: 'rgba(200, 200, 200, 0.85)',
};

const LAYER_NAMES = {
  ephemeral: { label: 'This Week', halfLife: '3-day half-life' },
  contextual: { label: 'This Month', halfLife: '21-day half-life' },
  stable: { label: 'Enduring', halfLife: '120-day half-life' },
} as const;

function getMaxReads(profile: InterestProfile): number {
  let max = 1;
  for (const layer of [profile.ephemeral, profile.contextual, profile.stable]) {
    for (const entry of Object.values(layer.categoryAffinity)) {
      if (entry.reads > max) max = entry.reads;
    }
  }
  return max;
}

export function InterestProfilePage() {
  const { profileQuery } = useNewsFeed();
  const [explorationSlots, setExplorationSlots] = useState(4);
  const [newTopic, setNewTopic] = useState('');

  const profile = useMemo(() => loadProfile(), []);
  const narrative = profileQuery.data?.narrative || '';
  const topics = profileQuery.data?.topics || [];
  const [mutedTopics, setMutedTopics] = useState<Set<string>>(new Set());
  const [boostedTopics, setBoostedTopics] = useState<Set<string>>(new Set());
  const [customTopics, setCustomTopics] = useState<string[]>([]);

  const maxReads = useMemo(() => getMaxReads(profile), [profile]);

  const toggleMute = useCallback((topic: string) => {
    setMutedTopics(prev => {
      const next = new Set(prev);
      if (next.has(topic)) {
        next.delete(topic);
      } else {
        next.add(topic);
        // Can't be both muted and boosted
        setBoostedTopics(p => { const n = new Set(p); n.delete(topic); return n; });
      }
      return next;
    });
  }, []);

  const toggleBoost = useCallback((topic: string) => {
    setBoostedTopics(prev => {
      const next = new Set(prev);
      if (next.has(topic)) {
        next.delete(topic);
      } else {
        next.add(topic);
        setMutedTopics(p => { const n = new Set(p); n.delete(topic); return n; });
      }
      return next;
    });
  }, []);

  const handleAddTopic = useCallback(() => {
    const trimmed = newTopic.trim().toLowerCase();
    if (trimmed && !customTopics.includes(trimmed) && !topics.includes(trimmed)) {
      setCustomTopics(prev => [...prev, trimmed]);
      setNewTopic('');
    }
  }, [newTopic, customTopics, topics]);

  const allTopics = [...topics, ...customTopics];

  return (
    <Page>
      <div>
        <Title data-halo="heading">Interest Profile</Title>
        <Subtitle>
          This is how the news system understands your interests. Edit topics,
          boost what matters, mute what doesn't.
        </Subtitle>
      </div>

      {/* Narrative Summary */}
      {narrative && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <SectionTitle>AI Summary</SectionTitle>
          <NarrativeCard>{narrative}</NarrativeCard>
        </div>
      )}

      {/* Topics */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <SectionTitle>Topics</SectionTitle>
        <TopicGrid>
          {allTopics.map(topic => {
            const isMuted = mutedTopics.has(topic);
            const isBoosted = boostedTopics.has(topic);
            return (
              <TopicPill
                key={topic}
                $active={!isMuted}
                onClick={() => isMuted ? toggleMute(topic) : isBoosted ? toggleBoost(topic) : toggleBoost(topic)}
                onContextMenu={(e) => { e.preventDefault(); toggleMute(topic); }}
                title={isMuted ? 'Muted — click to unmute' : isBoosted ? 'Boosted — click to remove boost' : 'Click to boost, right-click to mute'}
                style={isMuted ? { textDecoration: 'line-through', opacity: 0.25 } : isBoosted ? { borderWidth: '2px' } : undefined}
              >
                {isBoosted && '↑ '}{topic}
              </TopicPill>
            );
          })}
        </TopicGrid>
        <AddTopicRow>
          <TopicInput
            value={newTopic}
            onChange={e => setNewTopic(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleAddTopic()}
            placeholder="Add a topic..."
          />
          <AddButton onClick={handleAddTopic}>Add</AddButton>
        </AddTopicRow>
      </div>

      {/* Reading History by Layer */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <SectionTitle>Reading History</SectionTitle>
        {(['ephemeral', 'contextual', 'stable'] as const).map(layerKey => {
          const layer = profile[layerKey];
          const meta = LAYER_NAMES[layerKey];
          const categories = Object.entries(layer.categoryAffinity)
            .sort((a, b) => b[1].reads - a[1].reads);

          if (categories.length === 0) return null;

          return (
            <LayerSection key={layerKey}>
              <LayerHeader>
                <LayerName>{meta.label}</LayerName>
                <HalfLife>{meta.halfLife}</HalfLife>
              </LayerHeader>
              {categories.map(([cat, entry]) => (
                <CategoryRow key={cat}>
                  <CategoryLabel>{cat}</CategoryLabel>
                  <Bar
                    $width={(entry.reads / maxReads) * 100}
                    $color={CATEGORY_COLORS[cat] || 'rgba(200,200,200,0.85)'}
                  />
                  <ReadCount>{entry.reads} reads</ReadCount>
                </CategoryRow>
              ))}
            </LayerSection>
          );
        })}
      </div>

      {/* Exploration Slider */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <SectionTitle>Exploration</SectionTitle>
        <SliderRow>
          <SliderLabel>Discovery picks</SliderLabel>
          <Slider
            type="range"
            min={0}
            max={8}
            value={explorationSlots}
            onChange={e => setExplorationSlots(Number(e.target.value))}
          />
          <SliderValue>{explorationSlots} of 8</SliderValue>
        </SliderRow>
        <Subtitle>
          {explorationSlots === 0
            ? 'All picks based on your interests — no exploration.'
            : explorationSlots >= 6
            ? 'Heavy exploration — most picks will be from unfamiliar categories.'
            : `${explorationSlots} picks from categories you don't usually read.`}
        </Subtitle>
      </div>
    </Page>
  );
}
