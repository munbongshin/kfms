<template>
  <span class="language-switch" role="group" :aria-label="$t('언어')">
    <button :class="{ on: locale === 'ko' }" :aria-pressed="locale === 'ko'" @click="setLocale('ko')">한글</button>
    <button :class="{ on: locale === 'en' }" :aria-pressed="locale === 'en'" @click="setLocale('en')">EN</button>
  </span>
</template>

<script setup lang="ts">
import { locale, setLocale } from '../../i18n'
</script>

<style scoped>
.language-switch {
  display: inline-flex;
  border: 1px solid rgba(255, 255, 255, 0.55);
  border-radius: 3px;
  overflow: hidden;
}

.language-switch button {
  padding: 2px 9px;
  border: none;
  background: transparent;
  font-size: 12px;
  color: #fff;
  cursor: pointer;
}

.language-switch button.on {
  background: #fff;
  color: #1b3c74;
  font-weight: 700;
}

/* On the light sign-in page. */
.light .language-switch,
.language-switch.light {
  border-color: #b8c3d3;
}

.light .language-switch button,
.language-switch.light button {
  color: #1b3c74;
}

.light .language-switch button.on,
.language-switch.light button.on {
  background: #1b3c74;
  color: #fff;
}
</style>
