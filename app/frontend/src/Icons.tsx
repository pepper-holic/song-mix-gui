/** 툴바/빈 상태용 최소 스트로크 아이콘 — currentColor 상속, 외부 아이콘 라이브러리 의존 없음. */
type IconProps = { className?: string };

const base = {
  viewBox: "0 0 20 20",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.6,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

export function IconFolderOpen({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <path d="M2.5 6.5v9A1.5 1.5 0 0 0 4 17h12a1.5 1.5 0 0 0 1.5-1.5V8A1.5 1.5 0 0 0 16 6.5H9.8L8.2 4.3A1.5 1.5 0 0 0 7 3.5H4A1.5 1.5 0 0 0 2.5 5v1.5Z" />
    </svg>
  );
}

export function IconClock({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <circle cx="10" cy="10" r="7" />
      <path d="M10 6v4l2.6 2.2" />
    </svg>
  );
}

export function IconColumns({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <rect x="3" y="3.5" width="14" height="13" rx="1.5" />
      <path d="M10 3.5v13" />
    </svg>
  );
}

export function IconUndo({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <path d="M5 8H12.5A3.5 3.5 0 0 1 16 11.5v0A3.5 3.5 0 0 1 12.5 15H8" />
      <path d="M8 5 5 8l3 3" />
    </svg>
  );
}

export function IconKeyboard({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <rect x="2.5" y="5.5" width="15" height="9" rx="1.5" />
      <path d="M5.5 8.5h.01M8.5 8.5h.01M11.5 8.5h.01M14.5 8.5h.01M6 11.5h8" />
    </svg>
  );
}

export function IconLayers({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <path d="M10 3 3 6.8 10 10.6l7-3.8L10 3Z" />
      <path d="M3.5 10 10 13.6l6.5-3.6" />
      <path d="M3.5 13 10 16.6l6.5-3.6" />
    </svg>
  );
}

export function IconAdd({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <path d="M10 4v12M4 10h12" />
    </svg>
  );
}
