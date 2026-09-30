<template>
  <div class="tag-list">
    <div v-if="modelValue.length" class="tags">
      <el-tag
        v-for="item in modelValue"
        :key="item"
        :closable="!disabled"
        :type="isUnknown(item) ? 'warning' : 'info'"
        effect="plain"
        size="small"
        :title="isUnknown(item) ? $t('현재 데이터에서 찾지 못한 이름입니다. 띄어쓰기까지 같아야 맞습니다.') : ''"
        @close="remove(item)"
      >
        {{ item }}
      </el-tag>
    </div>
    <div v-else class="empty">{{ $t(emptyText) }}</div>

    <div v-if="!disabled" class="adder">
      <el-autocomplete
        v-model="draft"
        size="small"
        :placeholder="$t(placeholder)"
        :fetch-suggestions="suggest"
        value-key="name"
        :trigger-on-focus="false"
        clearable
        style="width: 260px"
        @select="pick"
        @keyup.enter="addOne"
      >
        <template #default="{ item }">
          <span>{{ item.name }}</span>
          <small class="count">{{ $t('{n}건', { n: item.count.toLocaleString() }) }}</small>
        </template>
      </el-autocomplete>
      <el-button size="small" :disabled="!draft.trim()" @click="addOne">{{ $t('추가') }}</el-button>
      <el-button size="small" @click="openBulk">{{ $t('일괄 추가') }}</el-button>
      <el-popconfirm v-if="modelValue.length" :title="$t('목록을 모두 지울까요?')" @confirm="emit('update:modelValue', [])">
        <template #reference><button class="link">{{ $t('전체 삭제') }}</button></template>
      </el-popconfirm>
    </div>
    <div class="count-line">{{ $t('{n}개', { n: modelValue.length }) }}</div>

    <el-dialog v-model="bulkOpen" :title="$t('일괄 추가')" width="480px" append-to-body>
      <p class="bulk-note">
        {{ $t('여러 개를 한꺼번에 붙여 넣습니다. 한 줄에 하나씩, 또는 쉼표(,) · 세미콜론(;) · 탭으로 나눠 적으면 됩니다. 엑셀에서 한 열을 복사해 붙여 넣어도 됩니다.') }}
      </p>
      <el-input v-model="bulkText" type="textarea" :rows="8" :placeholder="$t(placeholder)" />
      <div class="preview">
        <span v-html="$th('새로 추가 <b>{n}</b>개', { n: preview.added.length })"></span>
        <span v-if="preview.duplicates.length">{{ $t('이미 있음 {n}개(건너뜀)', { n: preview.duplicates.length }) }}</span>
        <span v-if="preview.invalid.length" class="bad">{{ $t('형식 오류 {n}개: {items}', { n: preview.invalid.length, items: preview.invalid.slice(0, 3).join(', ') + (preview.invalid.length > 3 ? ' …' : '') }) }}</span>
        <span v-if="preview.unknown.length" class="warn">{{ $t('데이터에 없는 이름 {n}개', { n: preview.unknown.length }) }}</span>
      </div>
      <template #footer>
        <el-button @click="bulkOpen = false">{{ $t('취소') }}</el-button>
        <el-button type="primary" :disabled="!preview.added.length" @click="addBulk">{{ $t('{n}개 추가', { n: preview.added.length }) }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { t } from '../../i18n'
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { mergeItems, parseItems } from '../../utils/listInput'

export interface Suggestion {
  name: string
  count: number
}

const props = withDefaults(
  defineProps<{
    modelValue: string[]
    disabled?: boolean
    placeholder?: string
    emptyText?: string
    /** Names that exist in the data: offered while typing, and used to flag names that match nothing. */
    suggestions?: Suggestion[]
    /** Returns a message when the item is not acceptable, else ''. */
    validate?: (item: string) => string
  }>(),
  { placeholder: '한 개씩 입력하고 Enter', emptyText: '아직 없습니다', suggestions: () => [] }
)
const emit = defineEmits<{ 'update:modelValue': [value: string[]] }>()

const draft = ref('')
const bulkOpen = ref(false)
const bulkText = ref('')

const known = computed(() => new Set(props.suggestions.map((s) => s.name)))
const isUnknown = (item: string) => props.suggestions.length > 0 && !known.value.has(item)

function suggest(query: string, cb: (items: Suggestion[]) => void) {
  const q = query.trim().toLowerCase()
  const have = new Set(props.modelValue)
  cb(
    props.suggestions
      .filter((s) => !have.has(s.name) && (!q || s.name.toLowerCase().includes(q)))
      .slice(0, 30)
  )
}

function add(items: string[]) {
  const merged = mergeItems(props.modelValue, items)
  if (merged.added.length) emit('update:modelValue', merged.list)
  return merged
}

function reject(item: string) {
  return props.validate ? props.validate(item) : ''
}

function addOne() {
  const item = draft.value.trim()
  if (!item) return
  const problem = reject(item)
  if (problem) {
    ElMessage.warning(problem)
    return
  }
  const merged = add([item])
  if (!merged.added.length) ElMessage.info(t("'{item}'은(는) 이미 목록에 있습니다", { item }))
  draft.value = ''
}

/** A picked suggestion is added straight away. */
function pick(item: Suggestion) {
  add([item.name])
  draft.value = ''
}

function remove(item: string) {
  emit('update:modelValue', props.modelValue.filter((x) => x !== item))
}

function openBulk() {
  bulkText.value = ''
  bulkOpen.value = true
}

const preview = computed(() => {
  const parsed = parseItems(bulkText.value)
  const valid = parsed.filter((i) => !reject(i))
  const merged = mergeItems(props.modelValue, valid)
  return {
    added: merged.added,
    duplicates: merged.duplicates,
    invalid: parsed.filter((i) => reject(i)),
    unknown: merged.added.filter(isUnknown),
  }
})

function addBulk() {
  add(preview.value.added)
  ElMessage.success(t('{n}개를 추가했습니다', { n: preview.value.added.length }))
  bulkOpen.value = false
}
</script>

<style scoped>
.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  max-height: 150px;
  overflow-y: auto;
  padding: 6px;
  border: 1px solid #dcdfe6;
  border-radius: 3px;
  background: #fff;
}

.empty {
  padding: 6px 8px;
  border: 1px dashed #d3dae3;
  border-radius: 3px;
  font-size: 12px;
  color: #8a94a3;
}

.adder {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}

.count-line {
  margin-top: 4px;
  font-size: 12px;
  color: #8a94a3;
}

.count {
  margin-left: 8px;
  color: #8a94a3;
}

.link {
  padding: 0;
  border: none;
  background: none;
  font-size: 12px;
  color: #b42318;
  text-decoration: underline;
  cursor: pointer;
}

.bulk-note {
  margin: 0 0 8px;
  font-size: 13px;
  line-height: 1.6;
  color: #475467;
}

.preview {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 8px;
  font-size: 12.5px;
  color: #475467;
}

.preview .bad {
  color: #b42318;
}

.preview .warn {
  color: #b54708;
}
</style>
