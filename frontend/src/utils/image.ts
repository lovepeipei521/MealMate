import { API_BASE } from '../constants';

const PROXIED_IMAGE_HOSTS = new Set(['i.ibb.co', 'ibb.co']);

/**
 * Route ImgBB images through the API origin.
 *
 * Some browsers/ad blockers block third-party image requests even though the
 * same URL opens correctly in a new tab. Same-origin image URLs are reliable.
 */
export function getImageDisplayUrl(src?: string | null): string | undefined {
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
    // Relative or data URLs are already safe to use as-is.
  }

  return src;
}