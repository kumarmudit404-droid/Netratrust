/**
 * Client-side SHA-256 of a captured image.
 *
 * This is the whole point of the capture screen: the image is hashed ON the
 * device and only the hash is ever sent. The bytes never leave.
 */
export async function sha256Hex(file: Blob): Promise<string> {
  const buf = await file.arrayBuffer()
  const digest = await crypto.subtle.digest("SHA-256", buf)
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("")
}

/** Middle-truncate a hash for display; the full value stays in the title. */
export function shortHash(hex: string, head = 8, tail = 4): string {
  return hex.length <= head + tail ? hex : `${hex.slice(0, head)}…${hex.slice(-tail)}`
}
