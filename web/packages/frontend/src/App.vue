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

const chartMinHeartRate = 60
const chartMaxHeartRate = 90
const chartMinHeartRateInterval = 5

const connected = ref(false)
const data = reactive<[number, number][]>([])
const curr = computed(() => {
  const minT = Date.now() - chartTimeWindow
  const minTPlus = minT - chartTimeWindowPlus
  const rate = data.length ? data[data.length - 1][1] : 0
  let minRate: number = 0
  let maxRate: number = 0
  for (const d of data) {
    if (d[0] < minT) continue
    if (!minRate || d[1] < minRate) minRate = d[1]
    if (!maxRate || d[1] > maxRate) maxRate = d[1]
  }
  return { minT, minTPlus, rate, minRate, maxRate }
})
const currRateDisplay = computed(() => (connected ? curr.value.rate : 0) || '--')

const ws = createWs(
  import.meta.env.VITE_API_URL || window.location.href.replace(/^http/, 'ws'),
  '/api/v1/ws',
  {},
)

ws.addEventListener('message', (e) => {
  const {
    detail: { data: msg },
  } = e
  if ('connected' in msg) {
    connected.value = msg.connected
  } else {
    data.push([msg.t * 1000, msg.r])
    const { minTPlus } = curr.value
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
    top: 16,
    bottom: 16,
    outerBoundsMode: 'same',
    outerBoundsContain: 'axisLabel',
  },
  textStyle: {
    fontFamily: '"HarmonyOS Sans SC", sans-serif',
  },
  xAxis: {
    type: 'time',
    min: () => curr.value.minT,
    minInterval: 1000,
    splitNumber: chartTimeAxisSplit,
    axisLabel: {
      showMinLabel: true,
      alignMinLabel: 'left',
      showMaxLabel: true,
      alignMaxLabel: 'right',
      formatter: {
        minute: '{H}:{mm}:{ss}',
        second: '{H}:{mm}:{ss}',
        millisecond: '{H}:{mm}:{ss}',
      },
      color: 'white',
    },
    axisLine: {
      lineStyle: { color: 'white' },
    },
  },
  yAxis: {
    type: 'value',
    min: () => Math.min(curr.value.minRate, chartMinHeartRate),
    max: () => Math.max(curr.value.maxRate, chartMaxHeartRate),
    minInterval: chartMinHeartRateInterval,
    axisLabel: { color: 'white' },
    axisLine: {
      show: true,
      lineStyle: { color: 'white' },
    },
    axisTick: { show: true },
    splitLine: {
      lineStyle: {
        type: 'dashed',
        color: 'rgba(156, 163, 175, 1)',
      },
    },
    minorSplitLine: {
      // show: true,
      lineStyle: {
        color: 'rgba(156, 163, 175, 0.6)',
      },
    },
  },
  series: [
    {
      type: 'line',
      smooth: true,
      symbol: 'none',
      color: '#fe251b',
      areaStyle: {
        opacity: 0.7,
        color: '#c51104',
      },
      lineStyle: { width: 4 },
      markLine: {
        data: [
          {
            yAxis: 0,
            label: {
              formatter: 'Min {c}',
              position: 'insideStartTop',
              distance: [20, 0],
            },
          },
          {
            yAxis: 0,
            label: {
              formatter: 'Max {c}',
              position: 'insideEndTop',
              distance: [20, 2],
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
          color: '#fffa',
        },
      },
    },
  ],
} satisfies EChartsOption)
onMounted(() => {
  chartRef.value?.setOption(chartOptions)
})
watch(curr, (newCurr) => {
  if (data.length === 0) return
  const markLine = chartOptions.series[0].markLine
  markLine.data[0].yAxis = newCurr.minRate
  markLine.data[1].yAxis = newCurr.maxRate
  chartRef.value?.setOption({
    series: [{ data, markLine }],
  } satisfies EChartsOption)
})

const heartRef = ref<InstanceType<typeof Icon>>()
const heartAnimation = ref<Animation | null>(null)
const heartAnimFrames = [
  { offset: 0, easing: 'ease-out', transform: 'scale(1)' },
  { offset: 0.35, easing: 'ease-in', transform: 'scale(0.9375)', opacity: 0.9 },
  { offset: 1, easing: 'ease-out', transform: 'scale(1)' },
] as Keyframe[]
onMounted(() => {
  const el = heartRef.value!.$el! as SVGElement
  heartAnimation.value = el.animate(heartAnimFrames, {
    duration: 1000,
    iterations: Infinity,
  })
  heartAnimation.value.pause()
})
watch(curr, (newCurr) => {
  if (!heartAnimation.value) return
  if (newCurr.rate > 0) {
    heartAnimation.value.playbackRate = newCurr.rate / 60
    heartAnimation.value.play()
  } else {
    heartAnimation.value.pause()
  }
})
</script>

<template>
  <div class="main" w="432px" h="172px" flex relative>
    <div
      v-if="!connected"
      absolute
      w="inherit"
      h="inherit"
      p="16px"
      flex
      items="center"
      justify="center"
      z="1"
    >
      <span font="bold" rd="xl" p="2" bg="gray-7 op-90" text="white center">
        Lost connection to device or WebSocket server
      </span>
    </div>
    <div
      flex="~ 1"
      :class="connected ? '' : 'filter-grayscale-100'"
      transition="~ duration-500"
      w="inherit"
      h="inherit"
    >
      <div
        m="l-8px r-0px y-16px"
        w="80px"
        overflow="hidden"
        flex="~ col"
        items="center"
        justify="center"
        gap-2
      >
        <Icon
          ref="heartRef"
          icon="el:heart"
          w="56px"
          h="56px"
          color="#fe251b"
          drop-shadow="[0_0_6px_#c51104]"
        />
        <span text-4xl color="#fe251b" font="bold" text-shadow="lg color-[#c51104]">
          {{ currRateDisplay }}
        </span>
      </div>
      <VChart flex="1" ref="chartRef" manual-update></VChart>
    </div>
  </div>
</template>

<style scoped>
.main {
  font-family: 'HarmonyOS Sans SC', sans-serif;
}
</style>
