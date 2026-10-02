/** Lazy chunk boundary for the 3D horizon + crash fallback to 2D. */
import { Component, type ReactNode } from 'react';
import type { FcGroup } from '../lib/api';
import Horizon3D from '../three/Horizon3D';

class SceneError extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    if (this.state.failed) {
      return (
        <p className="border border-brass/60 bg-brass/10 p-4 font-mono text-xs tracking-wider uppercase">
          3D unavailable in this browser — the 2D forecast chart above carries the same data.
        </p>
      );
    }
    return this.props.children;
  }
}

export default function HorizonSection({ group, shownModel }: { group: FcGroup; shownModel: string }) {
  const best = group.runs.find((r) => r.model === shownModel) ?? group.runs[0];
  const runs = group.runs.filter((r) => r.status === 'done');
  if (!runs.length) return null;
  return (
    <div className="mt-6">
      <h2 className="font-mono text-[11px] tracking-[0.25em] text-fog uppercase">
        Forecast horizon · 3D — {runs.length} model lanes
        {best ? ` · focused: ${best.model}` : ''}
      </h2>
      <div className="mt-2">
        <SceneError>
          <Horizon3D history={best.history} runs={runs} />
        </SceneError>
      </div>
    </div>
  );
}
