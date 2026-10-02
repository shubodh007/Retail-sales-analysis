/** ECharts null-share bar. Single chart primitive for Phase 1. */
import { useEffect, useRef } from 'react';
import * as echarts from 'echarts/core';
import { BarChart } from 'echarts/charts';
import { GridComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';

echarts.use([BarChart, GridComponent, CanvasRenderer]);

export function NullBar({ data }: { data: Record<string, number> }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const chart = echarts.init(el, undefined, { renderer: 'canvas' });
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);
    chart.setOption({
      animation: !reduce,
      grid: { left: 8, right: 8, top: 8, bottom: 8, containLabel: true },
      xAxis: {
        type: 'value',
        max: 1,
        axisLabel: { formatter: (v: number) => `${Math.round(v * 100)}%`, color: '#4d555c', fontFamily: 'monospace' },
        splitLine: { lineStyle: { color: '#e7e2d7' } },
      },
      yAxis: {
        type: 'category',
        data: entries.map(([k]) => k),
        axisLabel: { color: '#101112', fontFamily: 'monospace', fontSize: 11 },
        axisLine: { show: false },
        axisTick: { show: false },
      },
      series: [
        {
          type: 'bar',
          data: entries.map(([, v]) => ({
            value: v,
            itemStyle: { color: v > 0.05 ? '#e76f2f' : '#71816f' },
          })),
          barWidth: 14,
          label: {
            show: true,
            position: 'right',
            formatter: (p: { value: number }) => `${(p.value * 100).toFixed(1)}%`,
            color: '#4d555c',
            fontFamily: 'monospace',
            fontSize: 11,
          },
        },
      ],
    });
    const ro = new ResizeObserver(() => chart.resize());
    ro.observe(el);
    return () => {
      ro.disconnect();
      chart.dispose();
    };
  }, [data]);

  return <div ref={ref} style={{ height: Math.max(120, Object.keys(data).length * 34) }} role="img" aria-label="Null share per column" />;
}
