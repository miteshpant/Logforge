'use client'

import { useMemo } from 'react'
import { Line } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  ChartOptions
} from 'chart.js'
import type { MetricDataPoint, StreamConfig } from '@/app/observability/metrics/live/page'

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
)

interface LiveMetricsChartProps {
  dataPoints: MetricDataPoint[]
  config: StreamConfig
  isStreaming: boolean
}

export default function LiveMetricsChart({
  dataPoints,
  config,
  isStreaming
}: LiveMetricsChartProps) {
  // Group data by metric
  const chartData = useMemo(() => {
    const datasets = config.metrics.map((metric, metricIdx) => {
      return config.services.map((service, serviceIdx) => {
        const points = dataPoints
          .filter(d => d.metric_name === metric && d.service === service)
          .slice(-60) // Last 60 data points

        const colors = [
          '#3b82f6', // blue
          '#10b981', // emerald
          '#f59e0b', // amber
          '#ef4444', // red
          '#8b5cf6', // violet
          '#ec4899', // pink
          '#14b8a6', // teal
          '#f97316'  // orange
        ]

        const color = colors[(metricIdx * config.services.length + serviceIdx) % colors.length]

        return {
          label: `${service} - ${metric}`,
          data: points.map(p => ({ x: p.timestamp, y: p.value })),
          borderColor: color,
          backgroundColor: color + '20',
          borderWidth: 2,
          tension: 0.4,
          pointRadius: 0,
          pointHoverRadius: 4
        }
      })
    }).flat()

    return { datasets }
  }, [dataPoints, config])

  const options: ChartOptions<'line'> = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    interaction: {
      mode: 'nearest',
      axis: 'x',
      intersect: false
    },
    plugins: {
      legend: {
        display: true,
        position: 'top',
        labels: {
          color: '#e2e8f0',
          padding: 15,
          font: { size: 11 }
        }
      },
      tooltip: {
        enabled: true,
        backgroundColor: 'rgba(15, 23, 42, 0.9)',
        titleColor: '#e2e8f0',
        bodyColor: '#cbd5e1',
        borderColor: '#475569',
        borderWidth: 1,
        padding: 12,
        displayColors: true,
        callbacks: {
          title: (items) => {
            if (items[0]) {
              return new Date(items[0].parsed.x).toLocaleTimeString()
            }
            return ''
          },
          label: (item) => {
            const value = item.parsed.y.toFixed(2)
            return `${item.dataset.label}: ${value}`
          }
        }
      }
    },
    scales: {
      x: {
        type: 'linear',
        ticks: {
          color: '#94a3b8',
          callback: (value) => {
            const date = new Date(value as number)
            return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
          }
        },
        grid: {
          color: '#334155',
          drawTicks: false
        },
        border: {
          color: '#475569'
        }
      },
      y: {
        beginAtZero: true,
        ticks: {
          color: '#94a3b8'
        },
        grid: {
          color: '#334155',
          drawTicks: false
        },
        border: {
          color: '#475569'
        }
      }
    }
  }

  if (!isStreaming && dataPoints.length === 0) {
    return (
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-6 h-[500px] flex items-center justify-center">
        <div className="text-center text-slate-400">
          <p className="text-lg">Configure and start streaming to see live metrics</p>
          <p className="text-sm mt-2">Select services, metrics, and click "Start Streaming"</p>
        </div>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 gap-6">
      {config.metrics.map(metric => (
        <div
          key={metric}
          className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-6"
        >
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-white capitalize">
              {metric.replace('_', ' ')}
            </h3>
            {isStreaming && (
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse"></div>
                <span className="text-xs text-emerald-400">Live</span>
              </div>
            )}
          </div>

          <div className="h-[300px]">
            <Line
              data={{
                datasets: chartData.datasets.filter(d => d.label.includes(metric))
              }}
              options={options}
            />
          </div>
        </div>
      ))}
    </div>
  )
}
