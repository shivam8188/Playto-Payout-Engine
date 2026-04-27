import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

const apiClient = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
})

export const getMerchants = () => apiClient.get('/merchants/')
export const getMerchant = (merchantId) => apiClient.get(`/merchants/${merchantId}/`)
export const getPayouts = (merchantId) => apiClient.get(`/merchants/${merchantId}/payouts/list/`)
export const getPayout = (payoutId) => apiClient.get(`/payouts/${payoutId}/`)
export const createPayout = (merchantId, data, idempotencyKey) =>
  apiClient.post(`/merchants/${merchantId}/payouts/`, data, {
    headers: { 'Idempotency-Key': idempotencyKey },
  })

export default apiClient
