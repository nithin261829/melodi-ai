// Senses the listening moment for Melodi AI. Everything is turned into coarse labels on the phone
// ("light rain, 24°C", "driving", "Hyderabad"): GPS coordinates are only used locally and for the
// weather lookup (rounded to ~1 km), and never sent to the Melodi server.
import * as Location from 'expo-location';

export type Activity = 'still' | 'walking' | 'driving';

export type Moment = {
  localTime: string; // ISO 8601 with UTC offset
  daypart: string;
  weather?: string;
  activity?: Activity;
  city?: string;
  countryCode?: string;
};

export async function senseMoment(): Promise<Moment> {
  const now = new Date();
  const moment: Moment = { localTime: isoWithOffset(now), daypart: daypart(now) };

  const { status } = await Location.requestForegroundPermissionsAsync();
  if (status !== 'granted') return moment;

  const position =
    (await Location.getLastKnownPositionAsync({ maxAge: 5 * 60_000, requiredAccuracy: 1000 })) ??
    (await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced }));
  const { latitude, longitude, speed } = position.coords;

  moment.activity = activityFromSpeed(speed);
  const [place, weather] = await Promise.all([
    Location.reverseGeocodeAsync({ latitude, longitude }).then((r) => r[0]).catch(() => undefined),
    fetchWeather(latitude, longitude).catch(() => undefined),
  ]);
  moment.city = place?.city ?? place?.subregion ?? place?.region ?? undefined;
  moment.countryCode = place?.isoCountryCode ?? undefined;
  if (weather) {
    moment.weather = weather.summary;
    moment.daypart = daypart(now, weather.sunrise, weather.sunset);
  }
  return moment;
}

function activityFromSpeed(metersPerSecond: number | null): Activity | undefined {
  if (metersPerSecond == null || metersPerSecond < 0) return undefined; // iOS reports -1 when unknown
  if (metersPerSecond >= 6) return 'driving'; // ~22 km/h and up
  if (metersPerSecond >= 0.7) return 'walking';
  return 'still';
}

/** Time of day in the words a DJ would use; "golden hour" needs today's sunset. */
export function daypart(now: Date, sunrise?: Date, sunset?: Date): string {
  if (sunset && now < sunset && sunset.getTime() - now.getTime() <= 60 * 60_000) return 'golden hour';
  if (sunrise && now < sunrise && sunrise.getTime() - now.getTime() <= 45 * 60_000) return 'just before sunrise';
  const h = now.getHours();
  if (h < 5) return 'late night';
  if (h < 8) return 'early morning';
  if (h < 12) return 'morning';
  if (h < 17) return 'afternoon';
  if (h < 21) return 'evening';
  return 'night';
}

// Open-Meteo: free, no API key. Coordinates are rounded to two decimals (~1 km) before sending.
async function fetchWeather(lat: number, lon: number) {
  const url =
    `https://api.open-meteo.com/v1/forecast?latitude=${lat.toFixed(2)}&longitude=${lon.toFixed(2)}` +
    '&current=temperature_2m,weather_code&daily=sunrise,sunset&timezone=auto&forecast_days=1';
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Weather ${res.status}`);
  const data = await res.json();
  const offset = data.utc_offset_seconds as number;
  return {
    summary: `${describeWeatherCode(data.current.weather_code)}, ${Math.round(data.current.temperature_2m)}°C`,
    sunrise: fromLocalIso(data.daily.sunrise[0], offset),
    sunset: fromLocalIso(data.daily.sunset[0], offset),
  };
}

// Open-Meteo returns local times without an offset ("2026-10-28T17:52"); attach it before parsing.
function fromLocalIso(local: string, offsetSeconds: number): Date {
  const sign = offsetSeconds >= 0 ? '+' : '-';
  const abs = Math.abs(offsetSeconds);
  const hh = String(Math.floor(abs / 3600)).padStart(2, '0');
  const mm = String(Math.floor((abs % 3600) / 60)).padStart(2, '0');
  return new Date(`${local}:00${sign}${hh}:${mm}`);
}

// WMO weather interpretation codes, as documented by Open-Meteo.
function describeWeatherCode(code: number): string {
  if (code === 0) return 'clear sky';
  if (code <= 2) return 'partly cloudy';
  if (code === 3) return 'overcast';
  if (code === 45 || code === 48) return 'foggy';
  if (code >= 51 && code <= 57) return 'drizzle';
  if (code === 61 || code === 80) return 'light rain';
  if (code === 63 || code === 81) return 'rain';
  if (code === 65 || code === 82) return 'heavy rain';
  if (code === 66 || code === 67) return 'freezing rain';
  if ((code >= 71 && code <= 77) || code === 85 || code === 86) return 'snow';
  if (code >= 95) return 'thunderstorm';
  return 'mild weather';
}

function isoWithOffset(d: Date): string {
  const off = -d.getTimezoneOffset();
  const sign = off >= 0 ? '+' : '-';
  const pad = (n: number) => String(Math.floor(Math.abs(n))).padStart(2, '0');
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:00` +
    `${sign}${pad(off / 60)}:${pad(off % 60)}`
  );
}
