<template>
  <div class="restocking">
    <div class="page-header">
      <h2>Restocking</h2>
      <p>Review demand-driven restock recommendations and place a bulk order within your budget.</p>
    </div>

    <div v-if="loading" class="loading">Loading restocking recommendations...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <div class="card budget-card">
        <div class="card-header">
          <h3 class="card-title">Budget</h3>
        </div>
        <div class="budget-control">
          <input
            type="range"
            min="0"
            max="100000"
            step="1000"
            v-model.number="budget"
            class="budget-slider"
          />
          <div class="budget-amount">${{ budget.toLocaleString() }}</div>
        </div>
      </div>

      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-label">Recommended Items</div>
          <div class="stat-value">{{ rows.length }}</div>
        </div>
        <div :class="['stat-card', totalCardClass]">
          <div class="stat-label">Order Total</div>
          <div class="stat-value">${{ orderTotal.toLocaleString() }}</div>
        </div>
        <div class="stat-card info">
          <div class="stat-label">Remaining Budget</div>
          <div class="stat-value">${{ remainingBudget.toLocaleString() }}</div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">Recommendations ({{ rows.length }})</h3>
        </div>

        <div v-if="rows.length === 0" class="empty-state">
          No restocking recommendations match the current filters.
        </div>
        <div v-else class="table-container">
          <table class="restocking-table">
            <thead>
              <tr>
                <th>SKU</th>
                <th>Item Name</th>
                <th>Warehouse</th>
                <th>Category</th>
                <th>Trend</th>
                <th>Current Demand</th>
                <th>Forecasted Demand</th>
                <th>Unit Cost</th>
                <th>Quantity</th>
                <th>Line Cost</th>
                <th>Include</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in rows" :key="row.item_sku" :class="{ 'excluded-row': !row.included }">
                <td><strong>{{ row.item_sku }}</strong></td>
                <td>{{ row.item_name }}</td>
                <td>{{ row.warehouse }}</td>
                <td>{{ row.category }}</td>
                <td>
                  <span :class="['badge', row.trend]">{{ row.trend }}</span>
                </td>
                <td>{{ row.current_demand }}</td>
                <td><strong>{{ row.forecasted_demand }}</strong></td>
                <td>${{ row.unit_cost.toFixed(2) }}</td>
                <td>
                  <input
                    type="number"
                    min="0"
                    v-model.number="row.quantity"
                    class="quantity-input"
                  />
                </td>
                <td><strong>${{ (row.quantity * row.unit_cost).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }}</strong></td>
                <td>
                  <input type="checkbox" v-model="row.included" class="include-checkbox" />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="place-order-section">
        <div v-if="successMessage" class="success-banner">{{ successMessage }}</div>
        <div v-if="submitError" class="error">{{ submitError }}</div>
        <button
          class="place-order-btn"
          :disabled="includedRows.length === 0 || submitting"
          @click="placeOrder"
        >
          {{ submitting ? 'Placing Order...' : 'Place Order' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, watch, onMounted } from 'vue'
import { api } from '../api'
import { useFilters } from '../composables/useFilters'

export default {
  name: 'Restocking',
  setup() {
    const loading = ref(true)
    const error = ref(null)
    const recommendations = ref([])
    const rows = ref([])
    const budget = ref(20000)

    const submitting = ref(false)
    const submitError = ref(null)
    const successMessage = ref(null)

    const { selectedLocation, selectedCategory, getCurrentFilters } = useFilters()

    // Greedily walk the urgency-sorted recommendations, marking rows included
    // while the running total stays within budget.
    const buildRows = () => {
      let runningTotal = 0
      rows.value = recommendations.value.map(rec => {
        let included = false
        if (runningTotal + rec.suggested_cost <= budget.value) {
          included = true
          runningTotal += rec.suggested_cost
        }
        return {
          ...rec,
          quantity: rec.suggested_quantity,
          included
        }
      })
    }

    const loadRecommendations = async () => {
      try {
        loading.value = true
        error.value = null
        const filters = getCurrentFilters()
        recommendations.value = await api.getRestockingRecommendations(filters)
        buildRows()
      } catch (err) {
        error.value = 'Failed to load restocking recommendations: ' + err.message
      } finally {
        loading.value = false
      }
    }

    // Filter changes require a fresh network call
    watch([selectedLocation, selectedCategory], loadRecommendations)

    // Budget changes only require a client-side recompute of the greedy fill
    watch(budget, buildRows)

    const includedRows = computed(() => rows.value.filter(r => r.included))

    const orderTotal = computed(() => {
      return includedRows.value.reduce((sum, r) => sum + (r.quantity * r.unit_cost), 0)
    })

    const remainingBudget = computed(() => budget.value - orderTotal.value)

    const totalCardClass = computed(() => {
      if (orderTotal.value > budget.value) return 'danger'
      if (budget.value > 0 && orderTotal.value >= budget.value * 0.9) return 'warning'
      return ''
    })

    const placeOrder = async () => {
      submitError.value = null
      successMessage.value = null
      submitting.value = true
      try {
        const payload = {
          items: includedRows.value.map(r => ({
            sku: r.item_sku,
            name: r.item_name,
            quantity: r.quantity,
            unit_cost: r.unit_cost
          })),
          warehouse: selectedLocation.value !== 'all' ? selectedLocation.value : undefined
        }
        const order = await api.submitRestockOrder(payload)
        successMessage.value = `Order ${order.order_number} placed successfully. It will appear in the Orders tab.`
        await loadRecommendations()
      } catch (err) {
        submitError.value = 'Failed to submit restock order: ' + err.message
      } finally {
        submitting.value = false
      }
    }

    onMounted(loadRecommendations)

    return {
      loading,
      error,
      rows,
      budget,
      includedRows,
      orderTotal,
      remainingBudget,
      totalCardClass,
      submitting,
      submitError,
      successMessage,
      placeOrder
    }
  }
}
</script>

<style scoped>
.budget-card {
  margin-bottom: 1.5rem;
}

.budget-control {
  display: flex;
  align-items: center;
  gap: 1.5rem;
}

.budget-slider {
  flex: 1;
  -webkit-appearance: none;
  appearance: none;
  height: 6px;
  border-radius: 3px;
  background: #e2e8f0;
  outline: none;
  cursor: pointer;
}

.budget-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #2563eb;
  border: 2px solid white;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
  cursor: pointer;
  transition: background 0.2s;
}

.budget-slider::-webkit-slider-thumb:hover {
  background: #1d4ed8;
}

.budget-slider::-moz-range-thumb {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #2563eb;
  border: 2px solid white;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
  cursor: pointer;
  transition: background 0.2s;
}

.budget-slider::-moz-range-thumb:hover {
  background: #1d4ed8;
}

.budget-slider::-moz-range-progress {
  background: #3b82f6;
  height: 6px;
  border-radius: 3px;
}

.budget-amount {
  font-size: 1.5rem;
  font-weight: 700;
  color: #0f172a;
  min-width: 130px;
  text-align: right;
}

.restocking-table {
  table-layout: fixed;
  width: 100%;
}

.excluded-row {
  opacity: 0.5;
}

.quantity-input {
  width: 80px;
  padding: 0.375rem 0.5rem;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  font-size: 0.875rem;
  color: #0f172a;
}

.quantity-input:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.include-checkbox {
  width: 18px;
  height: 18px;
  cursor: pointer;
  accent-color: #2563eb;
}

.empty-state {
  text-align: center;
  padding: 3rem;
  color: #64748b;
  font-size: 0.938rem;
}

.place-order-section {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 1rem;
}

.success-banner {
  background: #d1fae5;
  color: #065f46;
  border: 1px solid #a7f3d0;
  padding: 1rem;
  border-radius: 8px;
  font-size: 0.938rem;
  width: 100%;
}

.place-order-btn {
  padding: 0.75rem 1.75rem;
  background: #2563eb;
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 0.938rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}

.place-order-btn:hover:not(:disabled) {
  background: #1d4ed8;
}

.place-order-btn:disabled {
  background: #cbd5e1;
  cursor: not-allowed;
}
</style>
