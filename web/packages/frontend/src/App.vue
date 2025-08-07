<script setup lang="ts">
import { Icon } from '@iconify/vue'
import { createWs } from 'ble-hrs-server-api'
import type { EChartsOption } from 'echarts'
import { LineChart } from 'echarts/charts'
import { GridComponent, MarkLineComponent } from 'echarts/components'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import VChart from 'vue-echarts'

use([GridComponent, MarkLineComponent, LineChart, CanvasRenderer])

const chartTimeWindow = 60000
const chartTimeWindowPlus = 3000
const chartTimeAxisSplit = 3

const chartMinHeartRate = 50
const chartMaxHeartRate = 90

const connected = ref(false)
const data = reactive([] as [number, number][])
const currHeartRate = computed(() => {
  if (!connected.value || data.length === 0) return 0
  return data[data.length - 1][1]
})

const getMinT = () => Date.now() - chartTimeWindow

const ws = createWs('ws://127.0.0.1:11642', '/api/v1/ws', {})

ws.addEventListener('message', (e) => {
  const {
    detail: { data: msg },
  } = e
  if ('connected' in msg) {
    connected.value = msg.connected
  } else {
    data.push([msg.t * 1000, msg.r])
    const minTPlus = getMinT() - chartTimeWindowPlus
    const outDatedIndex = data.findIndex((d) => d[0] < minTPlus)
    if (outDatedIndex > 0) data.splice(0, outDatedIndex)
  }
})
ws.addEventListener('close', () => {
  connected.value = false
})

onMounted(() => {
  ws.start()
})

onUnmounted(() => {
  ws.stop()
})

const chartRef = ref<InstanceType<typeof VChart>>()
const chartOptions = reactive({
  grid: {
    left: 0,
    right: 16,
    top: 8,
    bottom: 16,
    outerBoundsMode: 'same',
    outerBoundsContain: 'axisLabel',
  },
  textStyle: {
    fontFamily: '"HarmonyOS Sans SC", sans-serif',
  },
  xAxis: {
    type: 'time',
    min: getMinT,
    splitNumber: chartTimeAxisSplit,
    axisLabel: {
      showMinLabel: true,
      alignMinLabel: 'left',
      showMaxLabel: true,
      alignMaxLabel: 'right',
      formatter: {
        second: '{H}:{mm}:{ss}',
        millisecond: '{H}:{mm}:{ss}',
      },
      color: 'white',
    },
    axisLine: {
      lineStyle: {
        color: 'white',
      },
    },
  },
  yAxis: {
    type: 'value',
    min: ({ min }) => Math.min(min, chartMinHeartRate),
    max: ({ max }) => Math.max(max, chartMaxHeartRate),
    minInterval: 1,
    splitLine: {
      lineStyle: { color: 'rgba(156, 163, 175, 1)' },
    },
    minorSplitLine: {
      show: true,
      lineStyle: { color: 'rgba(156, 163, 175, 0.3)' },
    },
    axisLabel: {
      color: 'white',
    },
  },
  series: [
    {
      type: 'line',
      smooth: true,
      color: '#fe251b',
      symbol: 'circle',
      symbolSize: 4,
      areaStyle: {
        opacity: 0.4,
      },
      markLine: {
        data: [
          {
            yAxis: 0,
            label: {
              formatter: 'Min {c}',
              position: 'insideStartTop',
              distance: [25, 4],
            },
          },
          {
            yAxis: 0,
            label: {
              formatter: 'Max {c}',
              position: 'insideStartBottom',
              distance: [80, 6],
            },
          },
        ],
        symbol: 'none',
        label: {
          color: 'white',
          // textBorderColor: 'black',
          // textBorderWidth: 2,
          fontSize: 14,
        },
        lineStyle: {
          type: 'solid',
          color: '#c51104',
        },
      },
    },
  ],
} satisfies EChartsOption)
onMounted(() => {
  chartRef.value?.setOption(chartOptions)
})
watch(data, (newData) => {
  if (newData.length === 0) return

  const minT = getMinT()
  let minRate: number | undefined
  let maxRate: number | undefined
  for (const d of newData) {
    if (d[0] < minT) continue
    if (!minRate || d[1] < minRate) minRate = d[1]
    if (!maxRate || d[1] > maxRate) maxRate = d[1]
  }

  const markLine = chartOptions.series[0].markLine
  markLine.data[0].yAxis = minRate ?? 0
  markLine.data[1].yAxis = maxRate ?? 0

  chartRef.value?.setOption({
    series: [{ data, markLine }],
  } satisfies EChartsOption)
})

const heartRef = ref<InstanceType<typeof Icon>>()
const heartAnimation = ref<Animation | null>(null)
const heartAnimFrames = [
  { transform: 'scale(1)', easing: 'ease-in' },
  { transform: 'scale(0.925)', opacity: 0.925, easing: 'ease-out' },
  { transform: 'scale(1)', easing: 'ease-in' },
] as Keyframe[]
onMounted(() => {
  const el = heartRef.value!.$el! as SVGElement
  heartAnimation.value = el.animate(heartAnimFrames, {
    duration: 1000,
    iterations: Infinity,
  })
  heartAnimation.value.pause()
})
watch([connected, currHeartRate], ([newConnected, newCurrHeartRate]) => {
  if (!heartAnimation.value) return
  const shouldStart = newConnected && newCurrHeartRate > 0
  if (shouldStart) {
    heartAnimation.value.playbackRate = newCurrHeartRate / 60
    heartAnimation.value.play()
  } else {
    heartAnimation.value.pause()
  }
})
</script>

<template>
  <div class="main" w="432px" h="164px" flex relative>
    <div
      v-if="!connected"
      absolute
      w="inherit"
      h="inherit"
      p="x-16px t-8px b-16px"
      flex
      items="center"
      justify="center"
      z-1
    >
      <span font-bold rd-xl p-2 bg-gray-7 bg-op-90 text-white>
        Lost connection to device or WebSocket server
      </span>
    </div>
    <div
      flex="~ 1"
      :class="connected ? '' : 'filter-grayscale-100'"
      transition="~ duration-500"
    >
      <div
        w="64px"
        m="l-16px r-8px t-8px b-16px"
        flex="~ col"
        items="center"
        justify="center"
        gap-2
        drop-shadow="lg color-#fe251b44"
      >
        <Icon ref="heartRef" icon="el:heart" w="64px" h="64px" color="#fe251b" />
        <span
          text-3xl
          color="#fe251b"
          font="medium"
          text-stroke="2 white"
          paint-order-sfm
        >
          {{ currHeartRate || '--' }}
        </span>
      </div>
      <VChart ref="chartRef" manual-update></VChart>
    </div>
  </div>
</template>

<style scoped>
.main {
  font-family: 'HarmonyOS Sans SC', sans-serif;
}
</style>
