// Types for the custom matchers registered with expect.extend() in
// tests/fixtures/index.ts. Without this, TypeScript does not know they exist.
export {}

declare global {
  namespace PlaywrightTest {
    interface Matchers<R, T = unknown> {
      toBeSuccessfulApiResponse(): R
      toHaveEnterpriseStyles(): Promise<R>
      toBeRealData(): R
    }
  }
}
