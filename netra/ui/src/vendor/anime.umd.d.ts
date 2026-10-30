/**
 * Types for the vendored UMD bundle, which TypeScript cannot read under
 * `allowJs: false`.
 *
 * `unknown` is honest here. The bundle's real export shape depends on which
 * UMD branch the bundler sends it down, so `anime.ts` is what narrows it - at
 * runtime, with a predicate, having checked both branches.
 */

declare const bundle: unknown
export default bundle
