import axiosInstance from './axiosInstance';

export interface CreditPack {
  price_id: string;
  credits: number;
  label: string;
  price_display?: string | null;
}

export interface SubscriptionItem {
  stripe_subscription_id: string;
  price_id?: string | null;
  label?: string | null;
  status?: string | null;
  cancel_at_period_end: boolean;
  current_period_end?: string | null;
}

export interface SubscriptionStatus {
  has_subscription: boolean;
  status?: string | null;
  cancel_at_period_end: boolean;
  current_period_end?: string | null;
  stripe_subscription_id?: string | null;
  price_id?: string | null;
  label?: string | null;
  subscriptions: SubscriptionItem[];
}

export interface BillingInvoice {
  invoice_id: string;
  status?: string | null;
  amount_paid: number;
  amount_refunded: number;
  currency?: string | null;
  created?: string | null;
  hosted_invoice_url?: string | null;
  grant_id?: string | null;
  grant_remaining: number;
  refundable: boolean;
}

export async function listCreditPacks(): Promise<{
  enabled: boolean;
  packs: CreditPack[];
}> {
  const { data } = await axiosInstance.get('/billing/credit-packs');
  return data;
}

export async function createCheckoutSession(priceId: string): Promise<{
  url: string;
  session_id: string;
}> {
  const { data } = await axiosInstance.post('/billing/checkout-session', {
    price_id: priceId,
  });
  return data;
}

export async function getSubscriptionStatus(): Promise<SubscriptionStatus> {
  const { data } = await axiosInstance.get('/billing/subscription');
  return {
    ...data,
    subscriptions: data.subscriptions ?? [],
  };
}

export async function listMyInvoices(): Promise<BillingInvoice[]> {
  const { data } = await axiosInstance.get('/billing/invoices');
  return data.invoices ?? [];
}

export async function cancelSubscription(
  stripeSubscriptionId: string
): Promise<SubscriptionStatus> {
  const { data } = await axiosInstance.post('/billing/subscription/cancel', {
    stripe_subscription_id: stripeSubscriptionId,
  });
  return {
    ...data,
    subscriptions: data.subscriptions ?? [],
  };
}

export async function resumeSubscription(
  stripeSubscriptionId: string
): Promise<SubscriptionStatus> {
  const { data } = await axiosInstance.post('/billing/subscription/resume', {
    stripe_subscription_id: stripeSubscriptionId,
  });
  return {
    ...data,
    subscriptions: data.subscriptions ?? [],
  };
}

export async function listUserInvoices(userId: string): Promise<BillingInvoice[]> {
  const { data } = await axiosInstance.get(`/billing/users/${userId}/invoices`);
  return data.invoices ?? [];
}

export async function refundUserInvoice(
  userId: string,
  invoiceId: string,
  revokeCredits: boolean
): Promise<{
  refund_id?: string | null;
  status?: string | null;
  amount?: number | null;
  currency?: string | null;
  invoice_id: string;
  revoked_grant_id?: string | null;
}> {
  const { data } = await axiosInstance.post(`/billing/users/${userId}/refunds`, {
    invoice_id: invoiceId,
    revoke_credits: revokeCredits,
  });
  return data;
}
