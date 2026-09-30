import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import App from './App.vue'
import { t, th } from './i18n'
import router from './router'
import './style.css'

const app = createApp(App)

// Register Element Plus icons
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(createPinia())
app.use(router)
// Element Plus's own texts follow the language through <el-config-provider> in App.vue.
app.use(ElementPlus)
// Screens write $t('한글 문구') in templates.
app.config.globalProperties.$t = t
app.config.globalProperties.$th = th

app.mount('#app')
