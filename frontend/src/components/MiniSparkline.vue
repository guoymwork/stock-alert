<script setup>
import { ref, watch, onMounted, nextTick } from 'vue'

const props = defineProps({
  data: { type: Array, default: () => [] },
  color: { type: String, default: '#58a6ff' },
  width: { type: Number, default: 80 },
  height: { type: Number, default: 28 },
})

const canvasRef = ref(null)

function draw() {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  const dpr = window.devicePixelRatio || 1
  const w = props.width
  const h = props.height
  canvas.width = w * dpr
  canvas.height = h * dpr
  canvas.style.width = w + 'px'
  canvas.style.height = h + 'px'
  ctx.scale(dpr, dpr)
  ctx.clearRect(0, 0, w, h)

  const values = props.data.map(d => d.close ?? d.value ?? 0).filter(v => v > 0)
  if (values.length < 2) return

  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1
  const pad = 2

  const grad = ctx.createLinearGradient(0, 0, 0, h)
  grad.addColorStop(0, props.color + '30')
  grad.addColorStop(1, props.color + '05')

  ctx.beginPath()
  values.forEach((v, i) => {
    const x = pad + (i / (values.length - 1)) * (w - pad * 2)
    const y = pad + (1 - (v - min) / range) * (h - pad * 2)
    if (i === 0) ctx.moveTo(x, y)
    else ctx.lineTo(x, y)
  })
  const lastX = pad + (w - pad * 2)
  ctx.lineTo(lastX, h)
  ctx.lineTo(pad, h)
  ctx.closePath()
  ctx.fillStyle = grad
  ctx.fill()

  ctx.beginPath()
  values.forEach((v, i) => {
    const x = pad + (i / (values.length - 1)) * (w - pad * 2)
    const y = pad + (1 - (v - min) / range) * (h - pad * 2)
    if (i === 0) ctx.moveTo(x, y)
    else ctx.lineTo(x, y)
  })
  ctx.strokeStyle = props.color
  ctx.lineWidth = 1.5
  ctx.lineJoin = 'round'
  ctx.stroke()

  const lastVal = values[values.length - 1]
  const lastY = pad + (1 - (lastVal - min) / range) * (h - pad * 2)
  ctx.beginPath()
  ctx.arc(lastX, lastY, 2, 0, Math.PI * 2)
  ctx.fillStyle = props.color
  ctx.fill()
}

watch(() => props.data, () => nextTick(draw), { deep: true })
watch(() => props.color, draw)
onMounted(() => { draw() })
</script>

<template>
  <canvas ref="canvasRef" class="mini-spark" />
</template>

<style scoped>
.mini-spark { display:block; }
</style>
