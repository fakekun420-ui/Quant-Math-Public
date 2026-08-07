<template>
  <div ref="containerRef" class="multi-select">
    <div
      class="multi-select-trigger"
      :class="{ open: isOpen, focused: focused }"
      tabindex="0"
      @click="toggleDropdown"
      @keydown="handleKeydown"
    >
      <div v-if="modelValue.length > 0" class="selected-tags">
        <span v-for="item in modelValue" :key="item" class="tag">
          {{ item }}
          <button
            type="button"
            class="tag-remove"
            @click.stop="removeItem(item)"
          >
            <IconX class="icon" />
          </button>
        </span>
      </div>
      <span v-if="modelValue.length === 0" class="placeholder">
        {{ placeholder }}
      </span>
      <IconChevronDown class="dropdown-icon" :class="{ rotated: isOpen }" />
    </div>

    <div v-show="isOpen" class="multi-select-dropdown">
      <div v-if="options.length > 10" class="dropdown-search">
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Buscar..."
          class="search-input"
          @click.stop
        />
      </div>
      <div ref="optionsRef" class="dropdown-options">
        <div
          v-for="option in filteredOptions"
          :key="option"
          class="option"
          :class="{
            selected: modelValue.includes(option),
            hovered: hoveredIndex === option,
          }"
          @click="selectOption(option)"
          @mouseenter="hoveredIndex = option"
          @mouseleave="hoveredIndex = null"
        >
          <span v-if="modelValue.includes(option)" class="option-check">
            <IconCheck class="icon" />
          </span>
          <span class="option-label">{{ option }}</span>
        </div>
        <div v-if="filteredOptions.length === 0" class="no-options">
          No se encontraron opciones
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from "vue";
import { ChevronDown, X, Check } from "lucide-vue-next";

const props = defineProps({
  modelValue: {
    type: Array,
    required: true,
  },
  options: {
    type: Array,
    required: true,
  },
  placeholder: {
    type: String,
    default: "Seleccionar...",
  },
});

const emit = defineEmits(["update:modelValue"]);

const containerRef = ref(null);
const optionsRef = ref(null);
const isOpen = ref(false);
const focused = ref(false);
const searchQuery = ref("");
const hoveredIndex = ref(null);

const filteredOptions = computed(() => {
  if (!searchQuery.value) return props.options;
  const query = searchQuery.value.toLowerCase();
  return props.options.filter((opt) => opt.toLowerCase().includes(query));
});

function toggleDropdown() {
  if (focused.value) {
    isOpen.value = !isOpen.value;
    if (isOpen.value) {
      searchQuery.value = "";
      nextTick(() => {
        if (optionsRef.value) optionsRef.value.scrollTop = 0;
      });
    }
  }
  focused.value = true;
}

function closeDropdown() {
  isOpen.value = false;
  focused.value = false;
  searchQuery.value = "";
  hoveredIndex.value = null;
}

function selectOption(option) {
  if (props.modelValue.includes(option)) {
    removeItem(option);
  } else {
    emit("update:modelValue", [...props.modelValue, option]);
  }
}

function removeItem(item) {
  emit(
    "update:modelValue",
    props.modelValue.filter((v) => v !== item),
  );
}

function handleKeydown(event) {
  if (!isOpen.value) return;

  const visibleOptions = filteredOptions.value;
  const currentIndex = hoveredIndex.value
    ? visibleOptions.indexOf(hoveredIndex.value)
    : -1;

  switch (event.key) {
    case "ArrowDown": {
      event.preventDefault();
      const nextIndex = Math.min(currentIndex + 1, visibleOptions.length - 1);
      hoveredIndex.value = visibleOptions[nextIndex];
      scrollToOption(nextIndex);
      break;
    }
    case "ArrowUp": {
      event.preventDefault();
      const prevIndex = Math.max(currentIndex - 1, 0);
      hoveredIndex.value = visibleOptions[prevIndex];
      scrollToOption(prevIndex);
      break;
    }
    case "Enter": {
      if (hoveredIndex.value) {
        event.preventDefault();
        selectOption(hoveredIndex.value);
      }
      break;
    }
    case "Escape":
      closeDropdown();
      break;
  }
}

function scrollToOption(index) {
  if (optionsRef.value) {
    const optionEl = optionsRef.value.children[index];
    if (optionEl) optionEl.scrollIntoView({ block: "nearest" });
  }
}

function handleClickOutside(event) {
  if (containerRef.value && !containerRef.value.contains(event.target)) {
    closeDropdown();
  }
}

onMounted(() => {
  document.addEventListener("click", handleClickOutside);
});

onUnmounted(() => {
  document.removeEventListener("click", handleClickOutside);
});
</script>

<style scoped>
.multi-select {
  position: relative;
  width: 100%;
}

.multi-select-trigger {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: 0.5rem 0.75rem;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
  min-height: 40px;
  flex-wrap: wrap;
}

.multi-select-trigger:hover,
.multi-select-trigger.focused {
  border-color: var(--accent-primary);
}

.multi-select-trigger.open {
  border-color: var(--accent-primary);
  box-shadow: 0 0 0 3px rgba(88, 166, 255, 0.2);
}

.selected-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-xs);
  flex: 1;
  min-width: 0;
}

.tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px 2px 6px;
  background: rgba(88, 166, 255, 0.15);
  border: 1px solid rgba(88, 166, 255, 0.3);
  border-radius: var(--radius-sm);
  font-size: 0.75rem;
  color: var(--accent-primary);
}

.tag-remove {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  background: none;
  border: none;
  color: var(--accent-primary);
  cursor: pointer;
  border-radius: var(--radius-full);
  padding: 0;
}

.tag-remove:hover {
  background: rgba(88, 166, 255, 0.2);
}

.tag-remove .icon {
  width: 10px;
  height: 10px;
}

.placeholder {
  color: var(--text-muted);
  font-size: 0.875rem;
  flex: 1;
}

.dropdown-icon {
  width: 18px;
  height: 18px;
  color: var(--text-muted);
  flex-shrink: 0;
  transition: transform var(--transition-fast);
}

.dropdown-icon.rotated {
  transform: rotate(180deg);
}

.multi-select-dropdown {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  z-index: 100;
  max-height: 300px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.dropdown-search {
  padding: var(--space-sm);
  border-bottom: 1px solid var(--border-color);
}

.search-input {
  width: 100%;
  padding: 0.5rem 0.75rem;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-size: 0.875rem;
}

.search-input:focus {
  outline: none;
  border-color: var(--accent-primary);
}

.dropdown-options {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-xs);
}

.option {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: 0.5rem 0.75rem;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background var(--transition-fast);
  font-size: 0.875rem;
}

.option:hover,
.option.hovered {
  background: var(--bg-tertiary);
}

.option.selected {
  background: rgba(88, 166, 255, 0.1);
  color: var(--accent-primary);
}

.option-check {
  width: 16px;
  height: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--accent-primary);
}

.option-check .icon {
  width: 14px;
  height: 14px;
}

.no-options {
  padding: var(--space-md);
  text-align: center;
  color: var(--text-muted);
  font-size: 0.875rem;
}
</style>
