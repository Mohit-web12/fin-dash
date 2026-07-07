import { useEffect, useRef, useState } from "react";

// Analog instrument dial: 270° sweep starting at 135° (bottom-left),
// matching a classic automotive gauge layout.
const START_DEG = 135;
const SPAN_DEG = 270;
const CX = 86;
const CY = 86;
const ARC_R = 68;
const FACE_R = 54;
const NEEDLE_LEN = 62;
const TICKS = Array.from({ length: 11 }, (_, i) => i); // 0..10, major every 5th

function polar(cx, cy, r, deg) {
  const rad = (deg * Math.PI) / 180;
  return [cx + r * Math.cos(rad), cy + r * Math.sin(rad)];
}

function arcPath(cx, cy, r, a0, a1) {
  const [x0, y0] = polar(cx, cy, r, a0);
  const [x1, y1] = polar(cx, cy, r, a1);
  const large = a1 - a0 > 180 ? 1 : 0;
  return `M ${x0.toFixed(2)} ${y0.toFixed(2)} A ${r} ${r} 0 ${large} 1 ${x1.toFixed(2)} ${y1.toFixed(2)}`;
}

function easeOutCubic(x) {
  return 1 - Math.pow(1 - x, 3);
}

const money = (n) => `${n < 0 ? "-" : ""}$${Math.round(Math.abs(n)).toLocaleString()}`;

export default function Gauge({ label, value, max, sub, accent = "var(--accent)", format = money }) {
  const fraction = Math.min(Math.max(value, 0) / Math.max(max, 1), 1);
  const [drawn, setDrawn] = useState(0);
  const frameRef = useRef(null);

  useEffect(() => {
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduceMotion) {
      setDrawn(fraction);
      return undefined;
    }
    const start = performance.now();
    const duration = 900;
    function step(now) {
      const p = Math.min((now - start) / duration, 1);
      setDrawn(easeOutCubic(p) * fraction);
      if (p < 1) frameRef.current = requestAnimationFrame(step);
    }
    frameRef.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frameRef.current);
  }, [fraction]);

  const [needleX, needleY] = polar(CX, CY, NEEDLE_LEN, START_DEG + drawn * SPAN_DEG);
  const displayValue = format(value);

  return (
    <div className="gauge-card">
      <svg
        className="gauge-dial"
        viewBox="0 0 172 172"
        role="img"
        aria-label={`${label} gauge, ${displayValue}${sub ? `, ${sub}` : ""}`}
      >
        {/* thin brass bezel — a hairline, not a glossy ring */}
        <circle cx={CX} cy={CY} r={80} fill="none" stroke="var(--brass)" strokeWidth="1.5" opacity="0.8" />
        <circle cx={CX} cy={CY} r={76} fill="var(--surface-2)" />
        <circle cx={CX} cy={CY} r={FACE_R} fill="var(--dial-face)" />

        {TICKS.map((i) => {
          const deg = START_DEG + (i / 10) * SPAN_DEG;
          const major = i % 5 === 0;
          const outer = polar(CX, CY, ARC_R + 4, deg);
          const inner = polar(CX, CY, ARC_R - (major ? 9 : 4), deg);
          return (
            <line
              key={i}
              x1={outer[0]}
              y1={outer[1]}
              x2={inner[0]}
              y2={inner[1]}
              stroke="var(--brass)"
              strokeOpacity={major ? 1 : 0.4}
              strokeWidth={major ? 2 : 1.2}
              strokeLinecap="round"
            />
          );
        })}

        <path
          d={arcPath(CX, CY, ARC_R, START_DEG, START_DEG + SPAN_DEG)}
          fill="none"
          stroke="rgba(0,0,0,0.3)"
          strokeWidth="6"
          strokeLinecap="round"
        />
        <path
          d={arcPath(CX, CY, ARC_R, START_DEG, START_DEG + drawn * SPAN_DEG)}
          fill="none"
          stroke={accent}
          strokeWidth="6"
          strokeLinecap="round"
        />

        <line x1={CX} y1={CY} x2={needleX} y2={needleY} stroke="var(--dial-ink)" strokeWidth="3" strokeLinecap="round" />
        <circle cx={CX} cy={CY} r="7" fill="var(--brass)" stroke="var(--dial-ink)" strokeWidth="1" />
        <circle cx={CX} cy={CY} r="2.5" fill="var(--dial-ink)" />
      </svg>
      <div className="gauge-value">{displayValue}</div>
      <div className="gauge-label">{label}</div>
      {sub && <div className="gauge-sub">{sub}</div>}
    </div>
  );
}
