<template>
  <div class="stage-column">
    <div class="stage-header">
      <h4 class="stage-title">{{ title }}</h4>
      <span class="stage-count">{{ items.length }}</span>
    </div>
    <div class="stage-items">
      <div
        v-for="item in items"
        :key="item.hypothesis_id"
        class="stage-item clickable"
        @click="selectItem(item)"
      >
        <div class="item-name">{{ item.name }}</div>
        <div class="item-meta">
          <span class="item-type">{{ item.strategy_type }}</span>
          <span
            class="item-score"
            :class="item.validation_score >= 0.7 ? 'good' : 'low'"
            >{{ (item.validation_score * 100).toFixed(0) }}%</span
          >
        </div>
      </div>
      <div v-if="items.length === 0" class="stage-empty">—</div>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  title: String,
  items: Array,
  stage: String,
});

const emit = defineEmits(["select"]);

function selectItem(item) {
  emit("select", item);
}
</script>

<style scoped>
.stage-column {
  display: flex;
  flex-direction: column;
  background: var(--bg-tertiary);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  overflow: hidden;
  min-height: 300px;
}

.stage-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-sm) var(--space-md);
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border-color);
}

.stage-title {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
  text-transform: capitalize;
}

.stage-count {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--accent-primary);
  background: rgba(88, 166, 255, 0.1);
  padding: 2px 8px;
  border-radius: var(--radius-full);
}

.stage-items {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-sm);
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}

.stage-item {
  padding: var(--space-sm);
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  transition: all var(--transition-fast);
}

.stage-item.clickable:hover {
  border-color: var(--accent-primary);
  transform: translateX(2px);
}

.item-name {
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 4px;
}

.item-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.7rem;
}

.item-type {
  color: var(--text-secondary);
  text-transform: capitalize;
}

.item-score {
  font-family: var(--font-mono);
  font-weight: 600;
}

.item-score.good {
  color: var(--accent-success);
}
.item-score.low {
  color: var(--accent-warning);
}

.stage-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  font-size: 0.875rem;
}
</style>
