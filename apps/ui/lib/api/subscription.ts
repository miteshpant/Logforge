/**
 * Subscription API Client
 * 15+ endpoints for subscription management, billing, and plan administration
 * Based on: /docs/wiki/knowledge_base/devDocs/Subscription-Router-API-Documentation.md
 */

import { apiClient, ApiResponse, PaginatedResponse } from './client'

// Subscription types
export interface Subscription {
  id: string
  tenant_id: string
  plan_id: string
  plan_name: string
  plan_type: 'trial' | 'starter' | 'professional' | 'enterprise' | 'custom'
  status: 'active' | 'cancelled' | 'expired' | 'suspended' | 'past_due'
  billing_cycle: 'monthly' | 'yearly'
  current_period_start: string
  current_period_end: string
  trial_end?: string
  cancel_at_period_end: boolean
  created_at: string
  updated_at: string
}

export interface SubscriptionPlan {
  id: string
  name: string
  type: 'trial' | 'starter' | 'professional' | 'enterprise' | 'custom'
  description: string
  features: PlanFeature[]
  pricing: PlanPricing
  limits: PlanLimits
  is_public: boolean
  created_at: string
}

export interface PlanFeature {
  name: string
  description: string
  included: boolean
  limit?: number
  unit?: string
}

export interface PlanPricing {
  monthly_price: number
  yearly_price: number
  currency: string
  billing_increment: 'user' | 'gb' | 'api_call' | 'flat'
  free_tier_included: boolean
  overage_pricing?: {
    per_gb: number
    per_api_call: number
    per_user: number
  }
}

export interface PlanLimits {
  max_users: number
  max_storage_gb: number
  max_api_calls_per_month: number
  max_logs_per_day: number
  max_dashboards: number
  max_alerts: number
  retention_days: number
  features_enabled: string[]
}

export interface SubscriptionUsage {
  subscription_id: string
  period_start: string
  period_end: string
  usage_items: UsageItem[]
  total_cost: number
  overage_charges: number
  credits_applied: number
  final_amount: number
}

export interface UsageItem {
  item_type: 'users' | 'storage' | 'api_calls' | 'logs' | 'features'
  description: string
  quantity: number
  unit: string
  unit_price: number
  total_cost: number
  included_in_plan: number
  overage: number
}

export interface Invoice {
  id: string
  subscription_id: string
  tenant_id: string
  invoice_number: string
  status: 'draft' | 'open' | 'paid' | 'void' | 'overdue'
  amount_due: number
  amount_paid: number
  currency: string
  due_date: string
  paid_at?: string
  created_at: string
  line_items: InvoiceLineItem[]
  payment_method?: PaymentMethod
}

export interface InvoiceLineItem {
  description: string
  quantity: number
  unit_price: number
  total: number
  period_start?: string
  period_end?: string
}

export interface PaymentMethod {
  id: string
  type: 'credit_card' | 'bank_transfer' | 'paypal' | 'invoice'
  brand?: string
  last_four?: string
  exp_month?: number
  exp_year?: number
  is_default: boolean
}

export interface BillingAddress {
  name: string
  company?: string
  line1: string
  line2?: string
  city: string
  state: string
  postal_code: string
  country: string
}

// Subscription API client
export class SubscriptionApi {
  /**
   * Get Current Subscription
   * GET /v1/subscription/current
   */
  static async getCurrentSubscription(tenantId: string): Promise<ApiResponse<Subscription>> {
    return apiClient.get('/v1/subscription/current', {
      headers: { 'X-Customer-ID': tenantId }
    })
  }

  /**
   * List Available Plans
   * GET /v1/subscription/plans
   */
  static async getSubscriptionPlans(): Promise<ApiResponse<SubscriptionPlan[]>> {
    return apiClient.get('/v1/subscription/plans')
  }

  /**
   * Get Plan Details
   * GET /v1/subscription/plans/{plan_id}
   */
  static async getSubscriptionPlan(planId: string): Promise<ApiResponse<SubscriptionPlan>> {
    return apiClient.get(`/v1/subscription/plans/${planId}`)
  }

  /**
   * Create Subscription
   * POST /v1/subscription/create
   */
  static async createSubscription(tenantId: string, subscriptionData: {
    plan_id: string
    billing_cycle: 'monthly' | 'yearly'
    payment_method_id?: string
    trial_days?: number
    promo_code?: string
  }): Promise<ApiResponse<Subscription>> {
    return apiClient.post('/v1/subscription/create', subscriptionData, {
      headers: { 'X-Customer-ID': tenantId }
    })
  }

  /**
   * Update Subscription
   * PUT /v1/subscription/update
   */
  static async updateSubscription(tenantId: string, updates: {
    plan_id?: string
    billing_cycle?: 'monthly' | 'yearly'
    prorate?: boolean
  }): Promise<ApiResponse<Subscription>> {
    return apiClient.put('/v1/subscription/update', updates, {
      headers: { 'X-Customer-ID': tenantId }
    })
  }

  /**
   * Cancel Subscription
   * POST /v1/subscription/cancel
   */
  static async cancelSubscription(tenantId: string, options?: {
    cancel_at_period_end?: boolean
    cancellation_reason?: string
    immediate?: boolean
  }): Promise<ApiResponse<Subscription>> {
    return apiClient.post('/v1/subscription/cancel', options, {
      headers: { 'X-Customer-ID': tenantId }
    })
  }

  /**
   * Reactivate Subscription
   * POST /v1/subscription/reactivate
   */
  static async reactivateSubscription(tenantId: string): Promise<ApiResponse<Subscription>> {
    return apiClient.post('/v1/subscription/reactivate', {}, {
      headers: { 'X-Customer-ID': tenantId }
    })
  }

  /**
   * Get Subscription Usage
   * GET /v1/subscription/usage
   */
  static async getSubscriptionUsage(tenantId: string, params?: {
    period_start?: string
    period_end?: string
  }): Promise<ApiResponse<SubscriptionUsage>> {
    return apiClient.get('/v1/subscription/usage', {
      params,
      headers: { 'X-Customer-ID': tenantId }
    })
  }

  /**
   * Preview Plan Change
   * POST /v1/subscription/preview-change
   */
  static async previewPlanChange(tenantId: string, changeData: {
    new_plan_id: string
    billing_cycle?: 'monthly' | 'yearly'
    prorate?: boolean
  }): Promise<ApiResponse<{
    new_plan: SubscriptionPlan
    cost_change: number
    effective_date: string
    proration_amount: number
    next_invoice_amount: number
  }>> {
    return apiClient.post('/v1/subscription/preview-change', changeData, {
      headers: { 'X-Customer-ID': tenantId }
    })
  }

  /**
   * Get Invoices
   * GET /v1/subscription/invoices
   */
  static async getInvoices(tenantId: string, params?: {
    limit?: number
    status?: string
    page?: number
  }): Promise<PaginatedResponse<Invoice>> {
    return apiClient.getPaginated('/v1/subscription/invoices', {
      ...params,
      headers: { 'X-Customer-ID': tenantId }
    })
  }

  /**
   * Get Invoice Details
   * GET /v1/subscription/invoices/{invoice_id}
   */
  static async getInvoice(invoiceId: string): Promise<ApiResponse<Invoice>> {
    return apiClient.get(`/v1/subscription/invoices/${invoiceId}`)
  }

  /**
   * Download Invoice PDF
   * GET /v1/subscription/invoices/{invoice_id}/pdf
   */
  static async downloadInvoice(invoiceId: string): Promise<ApiResponse<{
    download_url: string
    expires_at: string
  }>> {
    return apiClient.get(`/v1/subscription/invoices/${invoiceId}/pdf`)
  }

  /**
   * Pay Invoice
   * POST /v1/subscription/invoices/{invoice_id}/pay
   */
  static async payInvoice(invoiceId: string, paymentMethodId?: string): Promise<ApiResponse<{
    payment_id: string
    status: 'succeeded' | 'failed' | 'processing'
    amount_paid: number
  }>> {
    return apiClient.post(`/v1/subscription/invoices/${invoiceId}/pay`, {
      payment_method_id: paymentMethodId
    })
  }

  /**
   * List Payment Methods
   * GET /v1/subscription/payment-methods
   */
  static async getPaymentMethods(tenantId: string): Promise<ApiResponse<PaymentMethod[]>> {
    return apiClient.get('/v1/subscription/payment-methods', {
      headers: { 'X-Customer-ID': tenantId }
    })
  }

  /**
   * Add Payment Method
   * POST /v1/subscription/payment-methods
   */
  static async addPaymentMethod(tenantId: string, paymentData: {
    type: 'credit_card' | 'bank_transfer' | 'paypal'
    token: string // Payment processor token
    make_default?: boolean
  }): Promise<ApiResponse<PaymentMethod>> {
    return apiClient.post('/v1/subscription/payment-methods', paymentData, {
      headers: { 'X-Customer-ID': tenantId }
    })
  }

  /**
   * Update Payment Method
   * PUT /v1/subscription/payment-methods/{payment_method_id}
   */
  static async updatePaymentMethod(
    paymentMethodId: string, 
    updates: {
      exp_month?: number
      exp_year?: number
      is_default?: boolean
    }
  ): Promise<ApiResponse<PaymentMethod>> {
    return apiClient.put(`/v1/subscription/payment-methods/${paymentMethodId}`, updates)
  }

  /**
   * Delete Payment Method
   * DELETE /v1/subscription/payment-methods/{payment_method_id}
   */
  static async deletePaymentMethod(paymentMethodId: string): Promise<ApiResponse<void>> {
    return apiClient.delete(`/v1/subscription/payment-methods/${paymentMethodId}`)
  }

  /**
   * Get Billing Address
   * GET /v1/subscription/billing-address
   */
  static async getBillingAddress(tenantId: string): Promise<ApiResponse<BillingAddress>> {
    return apiClient.get('/v1/subscription/billing-address', {
      headers: { 'X-Customer-ID': tenantId }
    })
  }

  /**
   * Update Billing Address
   * PUT /v1/subscription/billing-address
   */
  static async updateBillingAddress(tenantId: string, address: BillingAddress): Promise<ApiResponse<BillingAddress>> {
    return apiClient.put('/v1/subscription/billing-address', address, {
      headers: { 'X-Customer-ID': tenantId }
    })
  }

  /**
   * Apply Promo Code
   * POST /v1/subscription/promo-code
   */
  static async applyPromoCode(tenantId: string, promoCode: string): Promise<ApiResponse<{
    discount_amount: number
    discount_percentage?: number
    valid_until: string
    applied: boolean
  }>> {
    return apiClient.post('/v1/subscription/promo-code', { promo_code: promoCode }, {
      headers: { 'X-Customer-ID': tenantId }
    })
  }

  /**
   * Get Billing History
   * GET /v1/subscription/billing-history
   */
  static async getBillingHistory(tenantId: string, params?: {
    start_date?: string
    end_date?: string
    limit?: number
  }): Promise<ApiResponse<Array<{
    date: string
    description: string
    amount: number
    status: string
    invoice_id?: string
  }>>> {
    return apiClient.get('/v1/subscription/billing-history', {
      params,
      headers: { 'X-Customer-ID': tenantId }
    })
  }

  /**
   * Estimate Usage Cost
   * POST /v1/subscription/estimate-cost
   */
  static async estimateUsageCost(tenantId: string, usageData: {
    estimated_logs_per_day: number
    estimated_storage_gb: number
    estimated_users: number
    estimated_api_calls: number
  }): Promise<ApiResponse<{
    estimated_monthly_cost: number
    estimated_yearly_cost: number
    cost_breakdown: Record<string, number>
    recommended_plan: string
    overage_risk: 'low' | 'medium' | 'high'
  }>> {
    return apiClient.post('/v1/subscription/estimate-cost', usageData, {
      headers: { 'X-Customer-ID': tenantId }
    })
  }

  // Admin endpoints
  /**
   * Create Custom Plan (Admin)
   * POST /v1/subscription/admin/plans
   */
  static async createCustomPlan(planData: Omit<SubscriptionPlan, 'id' | 'created_at'>): Promise<ApiResponse<SubscriptionPlan>> {
    return apiClient.post('/v1/subscription/admin/plans', planData)
  }

  /**
   * List All Subscriptions (Admin)
   * GET /v1/subscription/admin/subscriptions
   */
  static async getAllSubscriptions(params?: {
    status?: string
    plan_type?: string
    tenant_id?: string
    page?: number
    page_size?: number
  }): Promise<PaginatedResponse<Subscription>> {
    return apiClient.getPaginated('/v1/subscription/admin/subscriptions', params)
  }

  /**
   * Update Subscription (Admin)
   * PUT /v1/subscription/admin/subscriptions/{subscription_id}
   */
  static async adminUpdateSubscription(
    subscriptionId: string, 
    updates: Partial<Subscription>
  ): Promise<ApiResponse<Subscription>> {
    return apiClient.put(`/v1/subscription/admin/subscriptions/${subscriptionId}`, updates)
  }
}

export default SubscriptionApi