import { API_BASE } from '../constants';

const PROXIED_IMAGE_HOSTS = new Set(['i.ibb.co', 'ibb.co']);

/**
 * Keep normal image rendering direct.
 *
 * Routing every image through the backend makes all images fail whenever the
 * server cannot reach the image host, even though most image hosts work fine
 * from the user's browser.
 */
export function getImageDisplayUrl(src?: string | null): string | undefined {
  return src || undefined;
}

/**
 * Build a same-origin fallback URL for ImgBB images.
 *
 * This is only used after a direct image request fails in the browser. It
 * handles cases where a browser or extension blocks a third-party image
 * request while the backend can still fetch it.
 */
export function getImageProxyUrl(src?: string | null): string | undefined {
  if (!src) return undefined;

  try {
    const parsed = new URL(src);
    if (
      parsed.protocol === 'https:' &&
      PROXIED_IMAGE_HOSTS.has(parsed.hostname.toLowerCase())
    ) {
      return `${API_BASE}/image-proxy?url=${encodeURIComponent(parsed.toString())}`;
    }
  } catch {
    // Relative or data URLs do not need a proxy.
  }

  return undefined;
}
