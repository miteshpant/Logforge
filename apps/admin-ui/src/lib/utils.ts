import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Run async work over a list with a concurrency cap (LF-258).
 *
 * `Promise.all(items.map(...))` fires every request at once. Over a tenant list
 * that is unbounded fan-out: at a few hundred tenants it is a self-inflicted
 * denial of service on the API, and it gets worse precisely as the platform
 * grows. Results come back in input order regardless of completion order.
 */
export async function mapWithConcurrency<T, R>(
  items: T[],
  limit: number,
  worker: (item: T, index: number) => Promise<R>
): Promise<R[]> {
  const results = new Array<R>(items.length)
  let cursor = 0

  const runners = Array.from({ length: Math.max(1, Math.min(limit, items.length)) }, async () => {
    while (cursor < items.length) {
      const index = cursor++
      results[index] = await worker(items[index], index)
    }
  })

  await Promise.all(runners)
  return results
}
