<template>
  <div class="parameter-field">
    <label class="param-label">{{ param.label }}</label>

    <!-- Number Input -->
    <div v-if="param.type === 'number'" class="param-input">
      <input
        type="number"
        :value="value"
        :min="param.min"
        :max="param.max"
        :step="param.step || 'any'"
        class="input-number"
        @input="handleInput($event)"
        @change="handleChange($event)"
      />
      <span v-if="param.unit" class="param-unit">{{ param.unit }}</span>
    </div>

    <!-- Select Input -->
    <select
      v-else-if="param.type === 'select'"
      :value="value"
      class="input-select"
      @change="handleChange($event)"
    >
      <option v-for="opt in param.options" :key="opt" :value="opt">
        {{ opt }}
      </option>
    </select>

    <!-- Boolean/Toggle -->
    <div v-else-if="param.type === 'boolean'" class="param-toggle">
      <input
        :id="`toggle-${section}-${param.key}`"
        type="checkbox"
        :checked="value"
        class="toggle-input"
        @change="handleChange($event)"
      />
      <label :for="`toggle-${section}-${param.key}`" class="toggle-switch">
        <span class="toggle-thumb" />
      </label>
    </div>

    <!-- Text Input -->
    <input
      v-else-if="param.type === 'text'"
      type="text"
      :value="value"
      class="input-text"
      @input="handleInput($event)"
      @change="handleChange($event)"
    />

    <!-- Password Input -->
    <div v-else-if="param.type === 'password'" class="param-password">
      <input
        :type="showPassword ? 'text' : 'password'"
        :value="value"
        class="input-text"
        @input="handleInput($event)"
        @change="handleChange($event)"
      />
      <button
        type="button"
        class="password-toggle"
        @click="showPassword = !showPassword"
      >
        <IconEye v-if="showPassword" class="icon" />
        <IconEyeOff v-else class="icon" />
      </button>
    </div>

    <!-- Array Input (comma-separated) -->
    <input
      v-else-if="param.type === 'array'"
      type="text"
      :value="Array.isArray(value) ? value.join(', ') : value"
      class="input-text"
      placeholder="Valores separados por comas"
      @input="handleInput($event)"
      @change="handleChange($event)"
    />

    <!-- Integer Input -->
    <input
      v-else-if="param.type === 'integer'"
      type="number"
      :value="value"
      :min="param.min"
      :max="param.max"
      step="1"
      class="input-number"
      @input="handleInput($event)"
      @change="handleChange($event)"
    />

    <p v-if="param.help" class="param-help">{{ param.help }}</p>
  </div>
</template>

<script setup>
import { ref } from "vue";
import { Eye, EyeOff } from "lucide-vue-next";

const props = defineProps({
  param: {
    type: Object,
    required: true,
  },
  section: {
    type: String,
    required: true,
  },
  value: {
    required: true,
  },
});

const emit = defineEmits(["update"]);

const showPassword = ref(false);

function handleInput(event) {
  const input = event.target;
  let val = input.value;

  if (props.param.type === "number" || props.param.type === "integer") {
    val = val === "" ? null : Number(val);
  } else if (props.param.type === "array") {
    val = val
      .split(",")
      .map((v) => v.trim())
      .filter((v) => v);
  } else if (props.param.type === "boolean") {
    val = input.checked;
  }

  emit("update", val);
}

function handleChange(event) {
  const input = event.target;
  let val = input.value;

  if (props.param.type === "number" || props.param.type === "integer") {
    val = val === "" ? null : Number(val);
  } else if (props.param.type === "array") {
    val = val
      .split(",")
      .map((v) => v.trim())
      .filter((v) => v);
  } else if (props.param.type === "boolean") {
    val = input.checked;
  }

  emit("update", val);
}
</script>

<style scoped>
.parameter-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}

.param-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.param-input {
  display: flex;
  align-items: center;
  gap: var(--space-xs);
}

.input-number,
.input-select,
.input-text {
  width: 100%;
  padding: 0.5rem 0.75rem;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-family: var(--font-sans);
  font-size: 0.875rem;
  transition: all var(--transition-fast);
}

.input-number:focus,
.input-select:focus,
.input-text:focus {
  outline: none;
  border-color: var(--accent-primary);
  box-shadow: 0 0 0 3px rgba(88, 166, 255, 0.2);
}

.input-number::-webkit-outer-spin-button,
.input-number::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.param-unit {
  font-size: 0.75rem;
  color: var(--text-muted);
  white-space: nowrap;
}

/* Toggle Switch */
.param-toggle {
  display: flex;
  align-items: center;
}

.toggle-input {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
}

.toggle-switch {
  position: relative;
  width: 44px;
  height: 24px;
  background: var(--border-color);
  border-radius: var(--radius-full);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.toggle-switch::before {
  content: "";
  position: absolute;
  top: 2px;
  left: 2px;
  width: 20px;
  height: 20px;
  background: white;
  border-radius: var(--radius-full);
  transition: transform var(--transition-fast);
  box-shadow: var(--shadow-sm);
}

.toggle-input:checked + .toggle-switch {
  background: var(--accent-primary);
}

.toggle-input:checked + .toggle-switch::before {
  transform: translateX(20px);
}

.toggle-input:focus + .toggle-switch {
  box-shadow: 0 0 0 3px rgba(88, 166, 255, 0.3);
}

/* Password Toggle */
.param-password {
  display: flex;
  align-items: center;
}

.param-password .input-text {
  flex: 1;
  padding-right: 2.5rem;
}

.password-toggle {
  position: absolute;
  right: 0.75rem;
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  padding: 0.25rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  transition: color var(--transition-fast);
}

.password-toggle:hover {
  color: var(--text-primary);
}

.password-toggle .icon {
  width: 18px;
  height: 18px;
}

/* Help Text */
.param-help {
  font-size: 0.7rem;
  color: var(--text-muted);
  margin: 0;
}
</style>
