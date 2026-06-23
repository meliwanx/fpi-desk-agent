interface FpiAgentLogoProps {
  size?: number;
  className?: string;
}

export function FpiAgentLogo({ size = 20, className }: FpiAgentLogoProps) {
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src="/favicon.svg"
      width={size}
      height={size}
      alt="fpi-agent"
      className={className}
      style={{ width: size, height: size }}
    />
  );
}
