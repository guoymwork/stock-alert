<template>
  <div id="app-root">
    <main class="app-main">
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
  </div>
</template>

<style scoped>
#app-root {
  min-height: 100vh;
  background: var(--bg-primary);
  color: var(--text-primary);
}

.app-main {
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 16px 8px;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
