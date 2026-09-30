<template>
  <div class="database-selector">
    <el-select
      v-model="databaseStore.activeConnectionId"
      :placeholder="$t('데이터베이스 선택')"
      @change="onDatabaseChange"
      style="width: 250px"
    >
      <el-option
        v-for="conn in databaseStore.activeConnections"
        :key="conn.id"
        :label="conn.name"
        :value="conn.id"
      >
        <span style="float: left">{{ conn.name }}</span>
        <span style="float: right; color: #8492a6; font-size: 13px">
          {{ conn.host }}:{{ conn.port }}
        </span>
      </el-option>
    </el-select>

    <span v-if="databaseStore.activeConnection" class="connection-info">
      <el-tag size="small" type="success">
        {{ databaseStore.activeConnection.database }}
      </el-tag>
      <el-tag v-if="databaseStore.activeConnection.is_read_only" size="small" type="warning">
        {{ $t('읽기 전용') }}
      </el-tag>
    </span>
  </div>
</template>

<script setup lang="ts">
import { useDatabaseStore } from '../../stores/database'

const databaseStore = useDatabaseStore()

function onDatabaseChange(connectionId: number) {
  databaseStore.setActiveConnection(connectionId)
}
</script>

<style scoped>
.database-selector {
  display: flex;
  align-items: center;
  gap: 15px;
}

.connection-info {
  display: flex;
  gap: 8px;
}
</style>
