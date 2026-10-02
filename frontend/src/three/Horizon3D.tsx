/** Forecast Horizon: X=time, Y=revenue, Z=model lane. Data only, no decoration.
 * Lazy-loaded route chunk — three.js never enters the initial bundle.
 */
import { useLayoutEffect, useMemo, useRef, useState } from 'react';
import { Canvas } from '@react-three/fiber';
import { Html, OrbitControls } from '@react-three/drei';
import * as THREE from 'three';
import type { FcRun } from '../lib/api';

const LANE_COLORS: Record<string, string> = {
  arima: '#e76f2f',
  prophet: '#d9b44a',
  rf: '#71816f',
  xgb: '#17191c',
};

const H = 8; // scene height units
const LANE_GAP = 4;

export interface LaneInput {
  model: string;
  forecast: { date: string; v: number; lo: number | null; hi: number | null }[];
  visible: boolean;
}

/** Continuous polyline via segment pairs (lineSegments draws independent pairs). */
function line(points: [number, number, number][], color: string) {
  const pairs: [number, number, number][] = [];
  for (let i = 0; i + 1 < points.length; i++) pairs.push(points[i], points[i + 1]);
  const g = new THREE.BufferGeometry().setFromPoints(pairs.map((p) => new THREE.Vector3(...p)));
  return (
    <lineSegments geometry={g}>
      <lineBasicMaterial color={color} />
    </lineSegments>
  );
}

function ribbon(xs: number[], lo: number[], hi: number[], z: number, color: string) {
  const verts: number[] = [];
  const idx: number[] = [];
  for (let i = 0; i < xs.length; i++) {
    verts.push(xs[i], lo[i], z, xs[i], hi[i], z);
    if (i > 0) {
      const b = i * 2;
      idx.push(b - 2, b - 1, b, b - 1, b + 1, b);
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3));
  g.setIndex(idx);
  g.computeVertexNormals();
  return (
    <mesh geometry={g}>
      <meshBasicMaterial color={color} transparent opacity={0.14} side={THREE.DoubleSide} depthWrite={false} />
    </mesh>
  );
}

function Points({
  lane, xs, vals, z, onHover,
}: {
  lane: string;
  xs: number[];
  vals: { date: string; v: number }[];
  z: number;
  onHover: (h: { model: string; date: string; v: number; x: number; y: number; z: number } | null) => void;
}) {
  return (
    <group>
      {xs.map((x, i) => (
        <mesh
          key={i}
          position={[x, vals[i].v, z]}
          onPointerOver={(e) => { e.stopPropagation(); onHover({ model: lane, date: vals[i].date, v: vals[i].v, x, y: vals[i].v, z }); }}
          onPointerOut={() => onHover(null)}
        >
          <sphereGeometry args={[0.09, 8, 8]} />
          <meshBasicMaterial color={LANE_COLORS[lane] ?? '#e76f2f'} />
        </mesh>
      ))}
    </group>
  );
}

function Scene({ history, lanes }: { history: { date: string; v: number }[]; lanes: LaneInput[] }) {
  const [hover, setHover] = useState<{ model: string; date: string; v: number; x: number; y: number; z: number } | null>(null);
  const maxV = useMemo(() => Math.max(...history.map((h) => h.v), ...lanes.flatMap((l) => l.forecast.map((f) => f.hi ?? f.v)), 1), [history, lanes]);
  const sc = (v: number) => (v / maxV) * H;

  const stride = Math.max(1, Math.floor(history.length / 400));
  const hx = history.filter((_, i) => i % stride === 0);
  // Normalize X so the scene reads ~40 x 8 x lanes instead of 600 x 8 x 16.
  const total = history.length + Math.max(...lanes.map((l) => l.forecast.length), 0);
  const XU = 40 / Math.max(total, 1);
  const xn = (i: number) => i * XU;
  const histLine = hx.map((h, i): [number, number, number] => [xn(i * stride), sc(h.v), 0]);
  const xEnd = xn(history.length);

  const lanesOn = lanes.filter((l) => l.visible);
  return (
    <>
      <gridHelper args={[44, 11, '#788087', '#e7e2d7']} position={[20, -0.01, (lanes.length * LANE_GAP) / 2]} />
      {line(histLine, '#788087')}
      {lanesOn.map((l, li) => {
        const z = (li + 1) * LANE_GAP;
        const xs = l.forecast.map((_, i) => xn(history.length + i));
        const ys = l.forecast.map((f) => sc(f.v));
        const pts = xs.map((x, i): [number, number, number] => [x, ys[i], z]);
        const bridge: [number, number, number][] = [[xn(history.length - 1), sc(history[history.length - 1].v), 0], [xs[0], ys[0], z]];
        const hasBand = l.forecast.every((f) => f.lo != null && f.hi != null);
        return (
          <group key={l.model}>
            {line(bridge, LANE_COLORS[l.model] ?? '#e76f2f')}
            {line(pts, LANE_COLORS[l.model] ?? '#e76f2f')}
            {hasBand && ribbon(xs, l.forecast.map((f) => sc(f.lo as number)), l.forecast.map((f) => sc(f.hi as number)), z, LANE_COLORS[l.model] ?? '#e76f2f')}
            <Points lane={l.model} xs={xs} vals={l.forecast.map((f) => ({ date: f.date, v: sc(f.v) }))} z={z} onHover={setHover} />
          </group>
        );
      })}
      {hover && (
        <Html position={[hover.x, hover.y + 0.4, hover.z]} center>
          <div className="border border-ink bg-paper px-2 py-1 font-mono text-[11px] whitespace-nowrap">
            {hover.model} · {hover.date} · £{(hover.v / H) * maxV < 1000 ? ((hover.v / H) * maxV).toFixed(0) : `${(((hover.v / H) * maxV) / 1000).toFixed(1)}k`}
          </div>
        </Html>
      )}
      <OrbitControls makeDefault target={[xEnd / 2, H / 2, (lanesOn.length * LANE_GAP) / 2]} />
    </>
  );
}

function Rig({ lanes }: { xEnd: number; lanes: number; maxH: number }) {
  const ref = useRef<THREE.PerspectiveCamera>(null);
  useLayoutEffect(() => {
    ref.current?.position.set(8, 14, 34 + lanes * LANE_GAP);
  }, [lanes]);
  return <perspectiveCamera ref={ref} />;
}

function webglAvailable() {
  try {
    const c = document.createElement('canvas');
    return !!(c.getContext('webgl2') || c.getContext('webgl'));
  } catch {
    return false;
  }
}

export default function Horizon3D({ history, runs }: { history: FcRun['history']; runs: FcRun[] }) {
  const lanes: LaneInput[] = runs.map((r) => ({
    model: r.model,
    forecast: r.forecast.map((f) => ({ date: f.date, v: f.predicted, lo: f.lower, hi: f.upper })),
    visible: true,
  }));
  const [vis, setVis] = useState<Record<string, boolean>>(Object.fromEntries(lanes.map((l) => [l.model, true])));
  const [viewKey, setViewKey] = useState(0);
  const shown = lanes.map((l) => ({ ...l, visible: vis[l.model] ?? true }));
  const [failed] = useState(() => (typeof window === 'undefined' ? false : !webglAvailable()));
  if (failed) return null; // parent renders the 2D fallback instead
  const hist = history.map((h) => ({ date: h.date, v: h.actual }));
  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center gap-2" role="group" aria-label="Model lanes">
        {lanes.map((l) => (
          <button
            key={l.model}
            onClick={() => setVis((v) => ({ ...v, [l.model]: !(v[l.model] ?? true) }))}
            aria-pressed={vis[l.model] ?? true}
            className="flex items-center gap-2 border border-ink/25 px-2 py-1 font-mono text-[11px] tracking-wider uppercase"
          >
            <span className="inline-block h-2.5 w-2.5" style={{ background: LANE_COLORS[l.model] }} aria-hidden />
            {l.model}
          </button>
        ))}
        <button
          onClick={() => setViewKey((k) => k + 1)}
          className="ml-auto border border-ink/25 px-2 py-1 font-mono text-[11px] tracking-wider uppercase hover:bg-bone"
        >
          Reset view
        </button>
      </div>
      <div className="mb-2 flex flex-wrap gap-x-4 gap-y-1 font-mono text-[11px] tracking-wider text-fog uppercase" aria-label="Orientation legend">
        <span>X = time</span>
        <span>Y = revenue</span>
        <span>Z = model lane</span>
        <span className="flex items-center gap-1"><span className="inline-block h-0.5 w-4 bg-steel" aria-hidden /> history</span>
        <span className="flex items-center gap-1"><span className="inline-block h-0.5 w-4 bg-safety" aria-hidden /> forecast</span>
        <span className="flex items-center gap-1"><span className="inline-block h-2 w-4 bg-safety/20" aria-hidden /> prediction interval</span>
      </div>
      <div className="border border-ink/15" style={{ height: 460 }} role="img" aria-label="3D forecast horizon: time on X, revenue on Y, one lane per model">
        <Canvas key={viewKey} onCreated={({ gl }) => gl.setClearColor('#f3f0e8')} camera={{ fov: 45, near: 0.1, far: 5000 }}>
          <color attach="background" args={['#f3f0e8']} />
          <Rig xEnd={hist.length} lanes={shown.filter((l) => l.visible).length} maxH={H} />
          <Scene history={hist} lanes={shown} />
        </Canvas>
      </div>
      <p className="mt-1 font-mono text-[11px] tracking-wider text-fog uppercase">
        Drag to orbit · scroll to zoom · hover points to inspect · X=time · Y=revenue · Z=model lane
      </p>
    </div>
  );
}
