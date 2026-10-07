/** Tree-shaken ECharts primitives. No full-echarts import anywhere. */
import { useEffect, useRef } from 'react';
import * as echarts from 'echarts/core';
import { BarChart, LineChart, PieChart } from 'echarts/charts';
import { GraphicComponent, GridComponent, LegendComponent, TooltipComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';

echarts.use([BarChart, LineChart, PieChart, GraphicComponent, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer]);

const AXIS = { color: '#64727b', fontFamily: 'Inter, system-ui, sans-serif', fontSize: 11 };
const SPLIT = { lineStyle: { color: '#e7e0d8', type: 'dashed' } };

function useChart(ref: React.RefObject<HTMLDivElement | null>, option: object, deps: unknown[]) {
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const chart = echarts.init(el, undefined, { renderer: 'canvas' });
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    chart.setOption({ ...option, animation: !reduce });
    const ro = new ResizeObserver(() => chart.resize());
    ro.observe(el);
    return () => {
      ro.disconnect();
      chart.dispose();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}

export function TrendChart({
  dates,
  series,
  height = 300,
}: {
  dates: string[];
  series: { name: string; values: number[]; color: string; kind?: 'line' | 'bar'; yAxis?: number }[];
  height?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useChart(
    ref,
    {
      grid: { left: 8, right: 8, top: 36, bottom: 8, containLabel: true },
      tooltip: { trigger: 'axis', valueFormatter: (v: number) => (typeof v === 'number' ? v.toLocaleString('en-US', { maximumFractionDigits: 0 }) : v) },
      legend: { top: 0, right: 0, textStyle: { ...AXIS, fontSize: 10 }, itemWidth: 14 },
      xAxis: { type: 'category', data: dates, axisLabel: { ...AXIS, hideOverlap: true }, axisLine: { lineStyle: { color: '#e7e0d8' } } },
      yAxis: [
        { type: 'value', axisLabel: AXIS, splitLine: SPLIT },
        { type: 'value', axisLabel: { ...AXIS, show: series.some((s) => s.yAxis === 1) }, splitLine: { show: false } },
      ],
      series: series.map((s) => ({
        name: s.name,
        type: s.kind ?? 'line',
        data: s.values,
        yAxisIndex: s.yAxis ?? 0,
        showSymbol: false,
        lineStyle: { width: 2, color: s.color },
        itemStyle: { color: s.color },
        emphasis: { focus: 'series' },
      })),
    },
    [dates.join(','), JSON.stringify(series.map((s) => s.values))],
  );
  return <div ref={ref} style={{ height }} role="img" aria-label="Time trend" />;
}

/** Forecast chart: history (neutral) + forecast (safety) + interval band. */
export function BandChart({
  history,
  validation,
  forecast,
  height = 340,
}: {
  history: { date: string; v: number }[];
  validation: { date: string; actual: number; predicted: number }[];
  forecast: { date: string; v: number; lo: number | null; hi: number | null }[];
  height?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const dates = [...history.map((h) => h.date), ...forecast.map((f) => f.date)];
  const hVals = history.map((h) => h.v);
  const fVals = [...new Array(history.length).fill(null), ...forecast.map((f) => f.v)];
  const loVals = [...new Array(history.length).fill(null), ...forecast.map((f) => f.lo)];
  const hiVals = [...new Array(history.length).fill(null), ...forecast.map((f) => f.hi)];
  const valDates = validation.map((v) => v.date);
  const valVals = validation.map((v) => v.predicted);
  useChart(
    ref,
    {
      grid: { left: 8, right: 8, top: 36, bottom: 8, containLabel: true },
      tooltip: {
        trigger: 'axis',
        valueFormatter: (v: number) =>
          typeof v === 'number' ? `£${v.toLocaleString('en-US', { maximumFractionDigits: 0 })}` : v,
      },
      legend: { top: 0, right: 0, textStyle: { ...AXIS, fontSize: 10 }, itemWidth: 14, data: ['History', 'Validation fit', 'Forecast'] },
      xAxis: {
        type: 'category', data: dates,
        axisLabel: { ...AXIS, hideOverlap: true }, axisLine: { lineStyle: { color: '#e7e0d8' } },
      },
      yAxis: { type: 'value', axisLabel: AXIS, splitLine: SPLIT },
      series: [
        { name: 'History', type: 'line', data: [...hVals, ...new Array(forecast.length).fill(null)], showSymbol: false, lineStyle: { width: 2, color: '#5b9fb3' }, itemStyle: { color: '#5b9fb3' } },
        { name: 'Lower', type: 'line', data: loVals, showSymbol: false, lineStyle: { width: 0, opacity: 0 }, stack: 'band', silent: true },
        {
          name: 'Interval', type: 'line',
          data: hiVals.map((h, i) => (h == null || loVals[i] == null ? null : (h as number) - (loVals[i] as number))),
          showSymbol: false, lineStyle: { width: 0, opacity: 0 }, stack: 'band', silent: true,
          areaStyle: { color: 'rgba(139,107,158,0.16)' },
        },
        { name: 'Validation fit', type: 'line', data: dates.map((d) => { const i = valDates.indexOf(d); return i >= 0 ? valVals[i] : null; }), showSymbol: false, lineStyle: { width: 1.5, type: 'dashed', color: '#e8c66a' }, itemStyle: { color: '#e8c66a' } },
        { name: 'Forecast', type: 'line', data: fVals, showSymbol: false, lineStyle: { width: 2.5, color: '#8b6b9e' }, itemStyle: { color: '#8b6b9e' } },
      ],
    },
    [dates.join(','), JSON.stringify(fVals)],
  );
  return <div ref={ref} style={{ height }} role="img" aria-label="History and forecast with interval" />;
}

export function RankBar({
  rows,
  height,
  format = (v: number) => v.toLocaleString('en-US', { maximumFractionDigits: 0 }),
}: {
  rows: { label: string; value: number; color?: string }[];
  height?: number;
  format?: (v: number) => string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const compact = (v: number) =>
    v >= 1_000_000 ? `£${(v / 1_000_000).toFixed(1)}M` : v >= 1000 ? `£${(v / 1000).toFixed(0)}k` : `£${v.toFixed(0)}`;
  useChart(
    ref,
    {
      grid: { left: 8, right: 64, top: 8, bottom: 8, containLabel: true },
      xAxis: {
        type: 'value',
        splitNumber: 4,
        axisLabel: { ...AXIS, hideOverlap: true, formatter: compact },
        splitLine: SPLIT,
      },
      yAxis: {
        type: 'category',
        data: rows.map((r) => r.label),
        axisLabel: { color: '#24313a', fontFamily: 'Inter, system-ui, sans-serif', fontSize: 11 },
        axisLine: { show: false },
        axisTick: { show: false },
      },
      series: [
        {
          type: 'bar',
          data: rows.map((r) => ({ value: r.value, itemStyle: { color: r.color ?? '#5b9fb3' } })),
          barWidth: 14,
          label: { show: true, position: 'right', formatter: (p: { value: number }) => format(p.value), ...AXIS },
        },
      ],
    },
    [JSON.stringify(rows)],
  );
  return (
    <div ref={ref} style={{ height: height ?? Math.max(120, rows.length * 34) }} role="img" aria-label="Ranked values" />
  );
}


export function DonutChart({
  rows,
  height = 220,
  centerLabel = 'Revenue',
}: {
  rows: { label: string; value: number; color?: string }[];
  height?: number;
  centerLabel?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useChart(ref, {
    tooltip: { trigger: 'item', valueFormatter: (v: number) => `£${Number(v).toLocaleString('en-US', { maximumFractionDigits: 0 })}` },
    legend: { bottom: 0, left: 'center', itemWidth: 10, itemHeight: 8, textStyle: { ...AXIS, fontSize: 9 } },
    series: [{
      type: 'pie', radius: ['48%', '70%'], center: ['50%', '43%'],
      avoidLabelOverlap: true,
      itemStyle: { borderColor: '#fff', borderWidth: 3 },
      label: { show: false },
      data: rows.map((r) => ({ name: r.label, value: r.value, itemStyle: { color: r.color } })),
    }],
    graphic: [{ type: 'text', left: 'center', top: '35%', style: { text: centerLabel, fill: '#64727b', fontSize: 10, fontWeight: 700 } }],
  }, [JSON.stringify(rows)]);
  return <div ref={ref} style={{ height }} role="img" aria-label={`${centerLabel} mix`} />;
}
