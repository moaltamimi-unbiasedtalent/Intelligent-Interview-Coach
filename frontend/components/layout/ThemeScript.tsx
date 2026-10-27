/**
 * Applies the stored theme before first paint to avoid a flash of the wrong theme.
 * Runs inline in <head>; falls back silently to system preference when unset.
 */
export function ThemeScript({ nonce }: { nonce?: string }) {
  const js = `(function(){try{var t=localStorage.getItem('iic-theme');if(t==='dark'||t==='light'){document.documentElement.setAttribute('data-theme',t);}}catch(e){}})();`;
  return <script nonce={nonce} dangerouslySetInnerHTML={{ __html: js }} />;
}
