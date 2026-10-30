/** `?raw` imports of the landing markup come back as a string. */
declare module "*.html?raw" {
  const html: string
  export default html
}
