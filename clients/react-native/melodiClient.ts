// Minimal TypeScript client for the Melodi AI API. Pair it with context.ts, which turns the
// phone's location into coarse labels (city, weather, activity) before anything is sent.
import type { Moment } from './context';

export type Taste = {
  top_artists?: string[];
  languages?: string[];
  liked_video_ids?: string[];
  recent_video_ids?: string[];
};

export type PlannedTrack = {
  video_id: string;
  title: string;
  artists: string[];
  album?: string | null;
  duration_seconds?: number | null;
  thumbnail?: string | null;
  why?: string | null;
};

export type PlanResponse = {
  title: string;
  description: string;
  tracks: PlannedTrack[];
  sources: { playlist_id: string; title: string; category: string }[];
  usage: { model: string; input_tokens: number; output_tokens: number; llm_calls: number; seconds: number };
};

export type MelodiConfig = {
  serverUrl: string; // e.g. http://my-mac.local:8787
  token?: string; // must match MELODI_APP_TOKEN on the server, if set
};

export async function planMix(
  config: MelodiConfig,
  moment: Moment,
  choice: { mood?: string; description?: string; taste?: Taste; size?: number } = {},
): Promise<PlanResponse> {
  const res = await fetch(`${config.serverUrl.replace(/\/$/, '')}/v1/plan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(config.token ? { 'X-Melodi-Token': config.token } : {}) },
    body: JSON.stringify({
      size: choice.size ?? 25,
      context: {
        local_time: moment.localTime,
        daypart: moment.daypart,
        weather: moment.weather,
        activity: moment.activity,
        city: moment.city,
        country_code: moment.countryCode,
        mood: choice.mood,
        description: choice.description?.trim() || undefined,
        taste: choice.taste ?? {},
      },
    }),
  });
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new Error(body?.detail ?? `Melodi AI error ${res.status}`);
  return body as PlanResponse;
}
