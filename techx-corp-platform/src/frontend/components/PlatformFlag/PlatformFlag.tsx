const { NEXT_PUBLIC_PLATFORM = 'local' } = typeof window !== 'undefined' ? window.ENV : {};
const PlatformFlag = () => (
  <span className="rounded bg-muted px-2 py-0.5 text-xs font-mono text-muted-foreground">{NEXT_PUBLIC_PLATFORM}</span>
);
export default PlatformFlag;
