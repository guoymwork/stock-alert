<script setup>
defineEmits(['add'])
defineProps({
  marquee: { type: String, default: '' }
})
</script>

<template>
  <header class="app-header">
    <div class="header-inner">
      <router-link to="/" class="header-brand">
        <span class="header-icon">📈</span>
        <h1 class="header-title">股票预警系统</h1>
      </router-link>
      <div class="header-actions">
        <slot name="actions" />
      </div>
    </div>
    <Transition name="marquee-in">
      <div v-if="marquee" class="marquee-bar">
        <div class="marquee-track">
          <span class="marquee-text">{{ marquee }}</span>
          <span class="marquee-text">{{ marquee }}</span>
        </div>
      </div>
    </Transition>
  </header>
</template>

<style scoped>
.app-header {
  position: sticky; top: 0; z-index: 100;
  background: var(--bg-card); border-bottom: 1px solid var(--border-default);
  backdrop-filter: blur(12px);
}
.header-inner {
  max-width: 1400px; margin: 0 auto;
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 16px;
}
.header-brand { display: flex; align-items: center; gap: 10px; text-decoration: none; color: inherit; }
.header-brand:hover { text-decoration: none; }
.header-icon { font-size: 22px; line-height: 1; }
.header-title { font-size: 17px; font-weight: 600; color: var(--text-primary); letter-spacing: -0.02em; }
.header-actions { display: flex; align-items: center; gap: 6px; }

.marquee-bar {
  overflow: hidden;
  background: linear-gradient(90deg, rgba(248,81,73,0.08), rgba(210,153,34,0.12), rgba(248,81,73,0.08));
  border-top: 1px solid rgba(248,81,73,0.15);
  height: 26px;
  line-height: 26px;
}
.marquee-track {
  display: flex;
  white-space: nowrap;
  animation: marquee-scroll 25s linear infinite;
}
.marquee-text {
  flex-shrink: 0;
  padding: 0 60px;
  font-size: 12px;
  font-weight: 500;
  color: var(--accent-orange);
}
@keyframes marquee-scroll {
  0% { transform: translateX(100%); }
  100% { transform: translateX(-100%); }
}
.marquee-in-enter-active { transition: all .3s ease; }
.marquee-in-leave-active { transition: all .2s ease; }
.marquee-in-enter-from, .marquee-in-leave-to { opacity: 0; height: 0; }

@media (max-width: 480px) { .header-title { font-size: 14px; } }
</style>
