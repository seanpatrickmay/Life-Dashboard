import type { InsightResponse } from '../services/api';
import type { NewsArticle } from '../services/newsFeedService';

export interface ComposeBriefInputs {
  insight: InsightResponse | null;
  events: Array<{ summary?: string | null; start_time?: string | null }>;
  overdueTasks: string[];
  picks: NewsArticle[];
  annotations: Record<string, string>;
}

const REFLECTION = 'What would make today count?';

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  } catch {
    return '';
  }
}

const FOCUS_EVENT_RE = /deep.?work|focus|flow|writing|research|planning|review/i;

/**
 * Returns the readiness tier: 'low' | 'moderate' | 'good' based on label or score.
 * Exported so MorningBriefCard can use the same derivation without duplicating logic.
 */
export function readinessTier(insight: InsightResponse): 'low' | 'moderate' | 'good' {
  const label = (insight.readiness_label ?? '').toLowerCase();
  if (['strained', 'depleted', 'low', 'fatigued', 'poor'].some(w => label.includes(w))) return 'low';
  if (['moderate', 'fair', 'okay', 'neutral'].some(w => label.includes(w))) return 'moderate';
  if (typeof insight.readiness_score === 'number') {
    if (insight.readiness_score < 50) return 'low';
    if (insight.readiness_score < 70) return 'moderate';
  }
  return 'good';
}

// ── Synthesis fragment builders ───────────────────────────────────────────────
// Each returns a short phrase (no leading/trailing space) or null if data absent.

function sleepFragment(hours: number | null | undefined): string | null {
  if (hours == null) return null;
  return `${hours.toFixed(1)}h sleep`;
}

function scheduleFragment(
  events: Array<{ summary?: string | null; start_time?: string | null }>
): string | null {
  const named = events.filter(e => e.summary);
  if (named.length === 0) return null;
  const focusEvent = named.find(e => FOCUS_EVENT_RE.test(e.summary ?? ''));
  if (focusEvent) {
    const time = focusEvent.start_time ? ` at ${formatTime(focusEvent.start_time)}` : '';
    return `a ${(focusEvent.summary ?? '').trim()}${time}`;
  }
  if (named.length >= 4) return `${named.length} things on the calendar`;
  return null;
}

function taskFragment(overdueTasks: string[]): string | null {
  if (overdueTasks.length === 0) return null;
  if (overdueTasks.length === 1) return `"${overdueTasks[0]}" still open`;
  return `${overdueTasks.length} overdue tasks`;
}

/**
 * Builds one fluent synthesis sentence that ties the top read to at least one
 * concrete day-signal (sleep, a notable event, or overdue-task load).
 * Falls back gracefully when signals are absent.
 */
function buildSynthesisSentence(
  tier: 'low' | 'moderate' | 'good',
  topTitle: string,
  annotation: string | null,
  sleepCtx: string | null,
  scheduleCtx: string | null,
  taskCtx: string | null,
): string {
  const ann = annotation
    ? annotation.toLowerCase().replace(/\.$/, '')
    : null;

  // Pick up to two available signals (prefer sleep+schedule over sleep+task, etc.)
  const allSignals = [sleepCtx, scheduleCtx, taskCtx].filter(Boolean) as string[];
  const signals = allSignals.slice(0, 2);
  const signalPhrase = signals.length > 0 ? signals.join(' and ') : null;

  if (tier === 'good') {
    if (signalPhrase && ann) {
      return `With ${signalPhrase}, readiness is solid — a strong moment to dig into "${topTitle}": ${ann}.`;
    }
    if (signalPhrase) {
      return `With ${signalPhrase}, readiness is solid — "${topTitle}" is today's strongest read if you have the bandwidth.`;
    }
    return ann
      ? `Readiness is solid — a good moment to dig into "${topTitle}": ${ann}.`
      : `Readiness looks good; "${topTitle}" is today's strongest signal if you have bandwidth.`;
  }

  if (tier === 'moderate') {
    if (signalPhrase && ann) {
      return `A mid-range morning with ${signalPhrase} — "${topTitle}" is the standout read: ${ann}.`;
    }
    if (signalPhrase) {
      return `A mid-range morning with ${signalPhrase} — "${topTitle}" is worth squeezing in.`;
    }
    return ann
      ? `Body is mid-range today; the standout read — "${topTitle}" — ${ann}.`
      : `Body is mid-range; "${topTitle}" is worth a look when energy allows.`;
  }

  // low / recovery
  if (signalPhrase && ann) {
    return `Recovery day (${signalPhrase}) — the lighter load of "${topTitle}" suits the pace: ${ann}.`;
  }
  if (signalPhrase) {
    return `Recovery day with ${signalPhrase} — "${topTitle}" fits a lighter, curiosity-driven morning.`;
  }
  return ann
    ? `On a recovery day, "${topTitle}" stands out — ${ann} — worth a slower read.`
    : `With recovery as the priority today, the top read — "${topTitle}" — fits a lighter, curiosity-driven morning.`;
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
    // Ties the top read to concrete day-signals so it differs with each day's data.
    const tier = readinessTier(insight);
    const topPick = picks[0] ?? null;
    const topAnnotation = topPick ? (annotations[topPick.id] ?? null) : null;

    if (topPick) {
      const sCtx = sleepFragment(insight.sleep_value_hours);
      const schCtx = scheduleFragment(events);
      const tCtx = taskFragment(overdueTasks);
      const synthesis = buildSynthesisSentence(
        tier,
        topPick.title,
        topAnnotation,
        sCtx,
        schCtx,
        tCtx,
      );
      segments.push(synthesis);
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
