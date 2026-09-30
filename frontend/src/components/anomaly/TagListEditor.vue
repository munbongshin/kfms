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
        :title="isUnknown(item) ? '현재 데이터에서 찾지 못한 이름입니다. 띄어쓰기까지 같아야 맞습니다.' : ''"
        @close="remove(item)"
      >
        {{ item }}
      </el-tag>
    </div>
    <div v-else class="empty">{{ emptyText }}</div>

    <div v-if="!disabled" class="adder">
      <el-autocomplete
        v-model="draft"
        size="small"
        :placeholder="placeholder"
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
          <small class="count">{{ item.count.toLocaleString() }}건</small>
        </template>
      </el-autocomplete>
      <el-button size="small" :disabled="!draft.trim()" @click="addOne">추가</el-button>
      <el-button size="small" @click="openBulk">일괄 추가</el-button>
      <el-popconfirm v-if="modelValue.length" title="목록을 모두 지울까요?" @confirm="emit('update:modelValue', [])">
        <template #reference><button class="link">전체 삭제</button></template>
      </el-popconfirm>
    </div>
    <div class="count-line">{{ modelValue.length }}개</div>

    <el-dialog v-model="bulkOpen" title="일괄 추가" width="480px" append-to-body>
      <p class="bulk-note">
        여러 개를 한꺼번에 붙여 넣습니다. 한 줄에 하나씩, 또는 쉼표(,) · 세미콜론(;) · 탭으로 나눠 적으면 됩니다. 엑셀에서 한 열을 복사해 붙여 넣어도 됩니다.
      </p>
      <el-input v-model="bulkText" type="textarea" :rows="8" :placeholder="placeholder" />
      <div class="preview">
        <span>새로 추가 <b>{{ preview.added.length }}</b>개</span>
        <span v-if="preview.duplicates.length">이미 있음 {{ preview.duplicates.length }}개(건너뜀)</span>
        <span v-if="preview.invalid.length" class="bad">형식 오류 {{ preview.invalid.length }}개: {{ preview.invalid.slice(0, 3).join(', ') }}{{ preview.invalid.length > 3 ? ' …' : '' }}</span>
        <span v-if="preview.unknown.length" class="warn">데이터에 없는 이름 {{ preview.unknown.length }}개</span>
      </div>
      <template #footer>
        <el-button @click="bulkOpen = false">취소</el-button>
        <el-button type="primary" :disabled="!preview.added.length" @click="addBulk">{{ preview.added.length }}개 추가</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
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
  if (!merged.added.length) ElMessage.info(`'${item}'은(는) 이미 목록에 있습니다`)
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
  ElMessage.success(`${preview.value.added.length}개를 추가했습니다`)
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
