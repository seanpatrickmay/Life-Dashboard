import type { InsightResponse } from '../services/api';
import type { NewsArticle } from '../services/newsFeedService';

export interface ComposeBriefInputs {
  insight: InsightResponse | null;
  events: Array<{ summary?: string | null; start_time?: string | null }>;
  overdueTasks: string[];
  picks: NewsArticle[];
  annotations: Record<string, string>;
  isGuest?: boolean;
}

const REFLECTION = 'What would make today count?';

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  } catch {
    return '';
  }
}

/**
 * Returns the readiness tier: 'low' | 'moderate' | 'good' based on label or score.
 * Drives the cross-domain synthesis sentence.
 */
function readinessTier(insight: InsightResponse): 'low' | 'moderate' | 'good' {
  const label = (insight.readiness_label ?? '').toLowerCase();
  if (['strained', 'depleted', 'low', 'fatigued', 'poor'].some(w => label.includes(w))) return 'low';
  if (['moderate', 'fair', 'okay', 'neutral'].some(w => label.includes(w))) return 'moderate';
  if (typeof insight.readiness_score === 'number') {
    if (insight.readiness_score < 50) return 'low';
    if (insight.readiness_score < 70) return 'moderate';
  }
  return 'good';
}

/**
 * Pure function — no side effects, no network. Builds a synthesised morning brief string.
 * Segments are omitted when their data is missing.
 * Always ends with the reflection question.
 */
export function composeBrief(inputs: ComposeBriefInputs): string {
  const { insight, events, overdueTasks, picks, annotations } = inputs;

  const segments: string[] = [];

  // ── 1. Body (readiness) ────────────────────────────────────────────────────
  if (insight) {
    const score = typeof insight.readiness_score === 'number'
      ? insight.readiness_score.toFixed(0)
      : null;
    const label = insight.readiness_label ?? null;

    // Start with morning_note if present, else greeting, else narrative
    const base = insight.morning_note || insight.greeting || insight.narrative;

    let bodyLine = base || '';

    // Add sleep context if available
    if (insight.sleep_value_hours != null) {
      const sleepStr = insight.sleep_value_hours.toFixed(1);
      bodyLine = bodyLine
        ? `${bodyLine} Sleep last night: ${sleepStr}h.`
        : `Sleep last night: ${sleepStr}h.`;
    }

    // Score/label summary
    if (score && label) {
      bodyLine = bodyLine
        ? `${bodyLine} Readiness ${score}/100 (${label}).`
        : `Readiness ${score}/100 (${label}).`;
    } else if (score) {
      bodyLine = bodyLine ? `${bodyLine} Readiness ${score}/100.` : `Readiness ${score}/100.`;
    }

    if (bodyLine) segments.push(bodyLine.trim());

    // ── Cross-domain synthesis sentence ───────────────────────────────────────
    // Connects readiness level to top read when there's a meaningful pairing.
    const tier = readinessTier(insight);
    const topPick = picks[0] ?? null;
    const topAnnotation = topPick ? (annotations[topPick.id] ?? null) : null;

    if (topPick) {
      if (tier === 'low') {
        // Low readiness + relevant read → suggest gentler approach
        const connector = topAnnotation
          ? `On a recovery day, "${topPick.title}" stands out — ${topAnnotation.toLowerCase().replace(/\.$/, '')} — worth a slower read.`
          : `With recovery as the priority today, the top read — "${topPick.title}" — fits a lighter, curiosity-driven morning.`;
        segments.push(connector);
      } else if (tier === 'moderate') {
        const connector = topAnnotation
          ? `Body is mid-range today; the standout read — "${topPick.title}" — ${topAnnotation.toLowerCase().replace(/\.$/, '')}.`
          : `Body is mid-range; "${topPick.title}" is worth a look when energy allows.`;
        segments.push(connector);
      } else {
        // Good readiness — pair high energy with strong read
        const connector = topAnnotation
          ? `Readiness is solid — a good moment to dig into "${topPick.title}": ${topAnnotation.toLowerCase().replace(/\.$/, '')}.`
          : `Readiness looks good; "${topPick.title}" is today's strongest signal if you have bandwidth.`;
        segments.push(connector);
      }
    }
  }

  // ── 2. Schedule ────────────────────────────────────────────────────────────
  const todayEvents = events.filter(e => e.summary);
  if (todayEvents.length > 0) {
    const eventStrs = todayEvents
      .slice(0, 3)
      .map(e => {
        const time = e.start_time ? ` at ${formatTime(e.start_time)}` : '';
        return `${e.summary}${time}`;
      });
    const rest = todayEvents.length > 3 ? ` (+${todayEvents.length - 3} more)` : '';
    segments.push(`On the schedule: ${eventStrs.join(', ')}${rest}.`);
  }

  // ── 3. Tasks ───────────────────────────────────────────────────────────────
  if (overdueTasks.length > 0) {
    const shown = overdueTasks.slice(0, 2);
    const rest = overdueTasks.length > 2 ? ` and ${overdueTasks.length - 2} more` : '';
    segments.push(`Overdue: ${shown.join('; ')}${rest}.`);
  }

  // ── 4. Reads ───────────────────────────────────────────────────────────────
  // The top pick was already woven into the synthesis sentence above.
  // Add a second pick here if present and distinct from synthesis.
  const secondPick = picks[1] ?? null;
  if (secondPick) {
    const ann = annotations[secondPick.id];
    const readLine = ann
      ? `Also worth your attention: "${secondPick.title}" — ${ann.toLowerCase().replace(/\.$/, '')}.`
      : `Also surfaced: "${secondPick.title}".`;
    segments.push(readLine);
  }

  // ── 5. Reflection hook (always present) ───────────────────────────────────
  segments.push(REFLECTION);

  return segments.join(' ');
}

export { REFLECTION };
